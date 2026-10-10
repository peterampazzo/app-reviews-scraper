import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scraper_backend.storage import write_bytes, save_review_csv, StorageBudgetExceeded
from scraper_backend.clients import GoogleClient
import requests
import json
from dating_project import summary, make_plans, write_csv, atomic_json


class ProjectTests(unittest.TestCase):
    def test_plans_and_summary_preserve_failed_apps_and_count_unique_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = {'apps': [dict(app='Pairs', tier='core', category='regional',
                                    android={'id':'test'}, ios={'id':'1'})]}
            rows = [dict(app='Pairs', store=store, id=identifier, country_used=country,
                         exists=exists, error=error) for store,identifier,country,exists,error in [
                         ('google','test','jp','True',''), ('apple','1','us','False','missing'),
                         ('apple','1','jp','True','')]]
            write_csv(root/'id_check.csv', rows)
            atomic_json(root/'play_countries.json', {'test':'jp'})
            plans = make_plans(root, profile)
            self.assertEqual(plans[('core','primary','google')]['test'][0]['country'], 'jp')
            self.assertEqual(plans[('core','primary','apple')]['1'][0]['country'], 'jp')
            run = root/'dating2026/raw/run/google'
            atomic_json(run/'run.json', dict(platform='google', queries=[
                dict(app_id='test', country='jp', locale='en')]))
            atomic_json(run/'test/jp-en/page-000001.json', dict(records=[
                dict(reviewId='one', at='2020-01-01T00:00:00Z'),
                dict(reviewId='one', at='2020-01-01T00:00:00Z')]))
            summary(root, profile)
            with (root/'scrape_summary.csv').open() as handle:
                result = list(csv.DictReader(handle))
            self.assertEqual(len(result), 2)
            self.assertIn('missing', result[0]['errors'])
            self.assertEqual(result[1]['number_of_reviews'], '1')
            self.assertEqual(result[1]['raw_review_observations'], '2')

    def test_budget_preserves_existing_file_and_stops_other_writes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
                'DATA_BUDGET_ROOT': tmp, 'DATA_BUDGET_BYTES': '100'}):
            target = Path(tmp)/'raw'
            write_bytes(target, b'a'*60)
            with self.assertRaises(StorageBudgetExceeded):
                write_bytes(target, b'b'*50, append=True)
            self.assertEqual(target.read_bytes(), b'a'*60)
            with self.assertRaises(StorageBudgetExceeded):
                write_bytes(Path(tmp)/'other', b'c')

    def test_csv_raw_fields_provenance_and_empty_completion(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'DATA_BUDGET_ROOT': ''}):
            target = Path(tmp)/'reviews.csv'
            record = {'reviewId': 'a', 'content': 'hello,\nworld', 'replyContent': 'Thanks'}
            provenance = dict(query_country='jp', query_language='en', scrape_date='2026-10-02')
            save_review_csv(target, [record], provenance)
            with target.open(newline='') as handle:
                self.assertEqual(list(csv.DictReader(handle)), [dict(record, **provenance)])
            save_review_csv(target, [], provenance)
            self.assertTrue(target.exists())
            self.assertFalse(target.with_suffix('.csv.part').exists())
            with target.open(newline='') as handle:
                self.assertEqual(list(csv.DictReader(handle)), [])

    def test_google_missing_country_does_not_retry_without_country(self):
        client = GoogleClient('example', 'en', country='jp')
        response = requests.Response()
        response.status_code = 404
        with patch.object(client.transport, 'request', side_effect=requests.HTTPError(response=response)) as fetch:
            self.assertFalse(client.app_exists())
        self.assertEqual(fetch.call_count, 1)
        self.assertIn('gl=jp', fetch.call_args.args[1])
