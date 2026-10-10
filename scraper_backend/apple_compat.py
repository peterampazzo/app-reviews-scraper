"""Small compatibility subclass of the original peterampazzo AppStore client.

Apple's 2026 website proxies the same catalog API under /api/apps/.
Reuse its app identity, request parameters and offset parser; preserve IDs and
raise failures instead of the upstream library's silent partial-success return.
"""
import sys
import time
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from app_store_scraper import AppStore


class CompatibleAppStore(AppStore):
    _request_host = 'apps.apple.com'
    _request_path = 'api/apps/v1/catalog/{country}/apps/{app_id}/reviews'

    def __init__(self, *args, transport, **kwargs):
        self.transport = transport
        self.stop_reason = None
        super().__init__(*args, **kwargs)
        self._request_headers.pop('Authorization', None)

    def _token(self):
        # Current public website uses its same-origin proxy, with no client JWT.
        return None

    def _get(self, url, headers=None, params=None, **kwargs):
        self._response = self.transport.request('GET', url, headers=headers, params=params)

    def resume_from(self, directory):
        """Restore archived pages and continue at the server's saved next offset."""
        pages = sorted(Path(directory).glob('page-*.json'))
        if not pages:
            return 0
        records = []
        for page in pages:
            payload = json.loads(page.read_text())
            records.extend(payload['records'])
        continuation = payload.get('continuation')
        if not continuation:
            raise ValueError('Cannot resume an exhausted query; refresh it explicitly instead')
        offset = int(parse_qs(urlparse(continuation).query)['offset'][0])
        self.reviews = records
        self.reviews_count = len(records)
        self._request_offset = offset
        self._request_params['offset'] = offset
        return offset

    def review(self, how_many=sys.maxsize, after=None, sleep=3, retry_after=10):
        seen_offsets = set()
        number = 0
        while True:
            if self._request_offset in seen_offsets:
                raise RuntimeError('Apple repeated pagination offset')
            seen_offsets.add(self._request_offset)
            self._get(self._request_url, headers=self._request_headers, params=self._request_params)
            payload = self._response.json()
            if not isinstance(payload.get('data'), list):
                raise RuntimeError(f'Apple response lacks review data: {list(payload)}')
            records = []
            for item in payload['data']:
                records.append(dict(item['attributes'], reviewId=item['id'],
                                    resourceType=item.get('type'), resourceMetadata={
                                        k: v for k, v in item.items() if k not in ('id', 'type', 'attributes')}))
            number += 1
            self.transport.page(number, records, payload.get('next'))
            self.reviews.extend(records)
            self.reviews_count = len(self.reviews)
            self._parse_next()
            if self._request_offset is None:
                self.stop_reason = 'no_next_link'
                break
            if not records:
                raise RuntimeError('Apple empty page with continuation; coverage incomplete')
            if self.reviews_count >= how_many:
                self.stop_reason = 'requested_count'
                break
            time.sleep(sleep)
