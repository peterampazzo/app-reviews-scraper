"""API clients for scraping different app stores

The app_store_scraper library for Apple app store defines a client object 
that is used to send requests and recieve app info. The client is created 
with an app ID and language and then various get_*() methods are called. 
The AppleClient class below is a very lightweight wrapper around the client
for convenience. 

For the play store, we have two different libraries (play_scraper and 
google_play_scraper), and both of them work in a purely procedural way 
(i.e, no client object). Each call to get_*() contains the app's ID and
language. Thus, for the sake of simplicity and consistency, the GoogleClient 
class below merges code from the two libraries together and behaves like 
the AppleClient class. This means we can then use the same scraper code 
for both app stores. 

"""

import sys
import os
import json
from datetime import datetime, timezone
import time
import importlib
from unittest.mock import patch

from .transport import Transport
from .storage import StorageBudgetExceeded
from .apple_compat import CompatibleAppStore

import google_play_scraper
import play_scraper
import requests
from .config import load_app_config

from .constants import PLAY_STORE_COUNTRY

config = load_app_config()


class GoogleClient:
    def __init__(self, app_id: str, language: str, raw_dir=None, country=PLAY_STORE_COUNTRY):
        """
        Client for querying the play store

        Args:
            app_id: as a dotted string, eg com.facebook.katana
            language: two letter language code
        """

        self.app_id = app_id
        self.language = language
        self.country = country
        self.transport = Transport(raw_dir)
        self.stop_reason = None

    def app_exists(self) -> bool:
        """Boolean test if this client's (app,language) pair exists"""

        try:
            self.details = self.get_details()
            return True
        except google_play_scraper.exceptions.NotFoundError:
            return False
        except requests.HTTPError as exc:
            if exc.response.status_code == 404:
                return False
            raise

    def get_details(self) -> dict:
        """Return app's details as JSON dict"""

        # The upstream app() helper silently retries a 404 without gl=country.
        # Use its parser directly so an availability check really tests this country.
        module = importlib.import_module('google_play_scraper.features.app')
        url = module.Formats.Detail.build(self.app_id, lang=self.language, country=self.country)
        response = self.transport.request('GET', url)
        details = module.parse_dom(dom=response.text, app_id=self.app_id, url=url)
        if not details.get('title'):
            raise ValueError('Google detail response has no app title; availability is unknown')
        return details

    def get_similar(self) -> list:
        """Return similar apps as list of IDs"""

        return play_scraper.similar(
            self.app_id, hl=self.language, gl=self.country
        )

    def get_reviews(self, count=sys.maxsize) -> list:
        """Return app's reviews as JSON"""
        # The public reviews() helper catches every error and treats it as EOF.
        # Reuse its fetcher/parser directly so failures are retried and reported.
        module = importlib.import_module('google_play_scraper.features.reviews')
        url = module.Formats.Reviews.build(lang=self.language, country=self.country)
        token, result, seen_tokens, number = None, [], set(), 0

        def post(url, data, headers):
            response = self.transport.request('POST', url, data=data, headers=headers)
            if 'com.google.play.gateway.proto.PlayGatewayError' in response.text:
                raise RuntimeError('Google Play gateway error')
            post.last_body = response.text
            return response.text

        while True:
            for attempt in range(4):
                try:
                    with patch.object(module, 'post', post):
                        try:
                            items, next_token = module._fetch_review_items(
                                url, self.app_id, google_play_scraper.Sort.NEWEST.value,
                                min(module.MAX_COUNT_EACH_FETCH, count - len(result)), None, None, token)
                        except TypeError:
                            # Google encodes no reviews as null; upstream calls len(None).
                            envelope = json.loads(module.Regex.REVIEWS.findall(post.last_body)[0])
                            payload = json.loads(envelope[0][2])
                            if len(payload) >= 2 and payload[0] is None and payload[1] is None:
                                items, next_token = [], None
                            else:
                                raise
                    break
                except StorageBudgetExceeded:
                    raise
                except Exception:
                    if attempt == 3:
                        raise
                    time.sleep(10 * 2 ** attempt)
            records = [{k: spec.extract_content(item)
                        for k, spec in module.ElementSpecs.Review.items()} for item in items]
            # Upstream uses naive local datetime.fromtimestamp; preserve UTC explicitly.
            for record, item in zip(records, items):
                record['at'] = datetime.fromtimestamp(item[5][0], timezone.utc)
                if record.get('repliedAt') is not None:
                    record['repliedAt'] = datetime.fromtimestamp(item[7][2][0], timezone.utc)
            number += 1
            self.transport.page(number, records, next_token)
            result.extend(records)
            if next_token is None or isinstance(next_token, list):
                self.stop_reason = 'no_continuation_token'
                break
            if not records:
                raise RuntimeError('Google empty page with continuation; coverage incomplete')
            if next_token in seen_tokens:
                raise RuntimeError('Google repeated continuation token; coverage incomplete')
            seen_tokens.add(next_token)
            if len(result) >= count:
                self.stop_reason = 'requested_count'
                break
            token = next_token
            time.sleep(config.get('app.sleep.google_store', 3))
        return result


class AppleClient:
    def __init__(self, app_name: str, app_id: int, country: str, raw_dir=None):
        """
        Client for querying the app store

        Args:
            app_name: app name as string
            app_id: integer app ID code
            language: two letter language code
        """

        self.transport = Transport(raw_dir)
        self.client = CompatibleAppStore(
            app_name=app_name, app_id=app_id, country=country, transport=self.transport
        )

    def app_exists(self) -> bool:
        """Boolean test if this client's (app,language) pair exists"""

        try:
            self.transport.request("GET", self.client.url)
            return True
        except requests.HTTPError as exc:
            if exc.response.status_code == 404:
                return False
            raise

    def get_details(self) -> dict:
        """Return app's details as JSON dict"""

        self.client.get_details()
        return self.client.details

    def get_similar(self) -> list:
        """Return similar apps as list of IDs"""

        self.client.get_similar()
        return self.client.similar

    def get_reviews(self, count=sys.maxsize) -> list:
        """Return app's reviews as JSON"""

        self.client.review(
            how_many=count, retry_after=10, sleep=float(os.environ.get('APPLE_SLEEP', config.get("app.sleep.apple_store")))
        )
        self.stop_reason = self.client.stop_reason
        return self.client.reviews
