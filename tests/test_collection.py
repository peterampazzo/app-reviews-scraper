import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scraper_backend.clients import GoogleClient
from scraper_backend.apple_compat import CompatibleAppStore
from scraper_backend.transport import Transport
from prepare_dataset import deduplicate


class Response:
    def __init__(self, payload):
        self.payload = payload
    def json(self):
        return self.payload


class CollectionTests(unittest.TestCase):
    def test_apple_resume_preserves_prior_records_and_requests_next_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path(tmp) / 'previous'
            previous.mkdir()
            (previous / 'page-000001.json').write_text(json.dumps({
                'records': [{'reviewId': 'old', 'review': 'Already saved'}],
                'continuation': '/v1/catalog/us/apps/1/reviews?offset=20'}))
            transport = Transport(Path(tmp) / 'new')
            client = CompatibleAppStore(country='us', app_name='x', app_id=1, transport=transport)
            self.assertEqual(client.resume_from(previous), 20)
            with patch.object(transport, 'request', return_value=Response({
                    'data': [{'id': 'new', 'attributes': {'review': 'New page'}}]})) as fetch:
                client.review(sleep=0)
            self.assertEqual(fetch.call_args.kwargs['params']['offset'], 20)
            self.assertEqual([r['reviewId'] for r in client.reviews], ['old', 'new'])
            archived = json.loads((Path(tmp) / 'new' / 'page-000001.json').read_text())
            self.assertEqual([r['reviewId'] for r in archived['records']], ['new'])

    def test_apple_ids_pagination_and_raw_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = Transport(Path(tmp) / 'raw')
            responses = [Response({'data': [{'id': '1', 'type': 'user-reviews',
                'attributes': {'review': 'First', 'date': '2020-01-01T00:00:00Z'}}],
                'next': '/v1/catalog/us/apps/1/reviews?offset=20'}),
                Response({'data': [{'id': '2', 'type': 'user-reviews',
                'attributes': {'review': 'Second', 'date': '2019-01-01T00:00:00Z'}}]})]
            with patch.object(transport, 'request', side_effect=responses) as fetch:
                client = CompatibleAppStore(country='us', app_name='x', app_id=1, transport=transport)
                client.review(sleep=0)
            self.assertEqual([r['reviewId'] for r in client.reviews], ['1', '2'])
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(client.stop_reason, 'no_next_link')
            self.assertEqual(len(list((Path(tmp)/'raw').glob('page-*.json'))), 2)

    def test_apple_failure_preserves_previous_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = Transport(Path(tmp)/'raw')
            first = Response({'data': [{'id': '1', 'attributes': {'review': 'Saved'}}],
                              'next': '/v1/catalog/us/apps/1/reviews?offset=20'})
            with patch.object(transport, 'request', side_effect=[first, RuntimeError('network')]):
                client = CompatibleAppStore(country='us', app_name='x', app_id=1, transport=transport)
                with self.assertRaisesRegex(RuntimeError, 'network'):
                    client.review(sleep=0)
            self.assertTrue((Path(tmp)/'raw'/'page-000001.json').exists())

    def test_google_continuation_until_exhaustion(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = GoogleClient('example', 'en', raw_dir=Path(tmp)/'raw')
            # Empty records with a next token is an error, not false completion.
            with patch('google_play_scraper.features.reviews._fetch_review_items', return_value=([], 'next')):
                with self.assertRaisesRegex(RuntimeError, 'empty page with continuation'):
                    client.get_reviews()
            self.assertTrue((Path(tmp)/'raw'/'page-000001.json').exists())

    def test_google_two_pages_and_utc(self):
        def item(identifier):
            return [identifier, ['author'], 5, None, 'text', [1577836800], 0, None, None, None, '1.0']
        with tempfile.TemporaryDirectory() as tmp:
            client = GoogleClient('example', 'en', raw_dir=Path(tmp)/'raw')
            with patch('google_play_scraper.features.reviews._fetch_review_items', side_effect=[([item('a')], 'next'), ([item('b')], None)]) as fetch, patch('scraper_backend.clients.time.sleep'):
                records = client.get_reviews()
            self.assertEqual([r['reviewId'] for r in records], ['a', 'b'])
            self.assertEqual(fetch.call_args_list[1].args[-1], 'next')
            self.assertEqual(records[0]['at'].isoformat(), '2020-01-01T00:00:00+00:00')
            self.assertEqual(client.stop_reason, 'no_continuation_token')

    def test_google_null_empty_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = GoogleClient('example', 'af', raw_dir=Path(tmp)/'raw')
            body = ")]}'\n\n" + json.dumps([['wrb.fr', 'oCPfdb', json.dumps([None, None, [[None, [[1800], None, [72000]]]]]), None, None, None, 'generic']])
            response = type('R', (), {'text': body})()
            with patch.object(client.transport, 'request', return_value=response):
                self.assertEqual(client.get_reviews(), [])
            self.assertEqual(client.stop_reason, 'no_continuation_token')

    def test_google_transport_errors_not_false_exhaustion(self):
        client = GoogleClient('example', 'en')
        with patch('google_play_scraper.features.reviews._fetch_review_items', side_effect=RuntimeError('failed')), patch('scraper_backend.clients.time.sleep'):
            with self.assertRaisesRegex(RuntimeError, 'failed'):
                client.get_reviews()
        self.assertIsNone(client.stop_reason)

    def test_dedup_platform_scope_latest_edit_and_missing_ids(self):
        base = dict(platform='apple', app_id='1', review_id='same', review_date='2020-01-01T00:00:00Z',
            retrieved_at='2026-01-01T00:00:00Z', source_file='a', source_row=0, source_record_json='{}',
            query_country='us', query_language='en-GB')
        rows = [base, dict(base, review_date='2021-01-01T00:00:00Z', query_country='gb'),
                dict(base, platform='google'), dict(base, review_id=None), dict(base, review_id=None)]
        result = deduplicate(rows)
        self.assertEqual(len(result), 4)
        merged = next(r for r in result if r['platform']=='apple' and r['review_id']=='same')
        self.assertEqual(merged['observation_count'], 2)
        self.assertEqual(merged['review_date'], '2021-01-01T00:00:00Z')
        self.assertEqual(json.loads(merged['observed_query_countries']), ['gb','us'])


if __name__ == '__main__':
    unittest.main()
