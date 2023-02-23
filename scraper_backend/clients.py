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

import app_store_scraper
import google_play_scraper
import play_scraper
import requests
from pyhocon import ConfigFactory

from .constants import PLAY_STORE_COUNTRY

config = ConfigFactory.parse_file("app.conf")


class GoogleClient:
    def __init__(self, app_id: str, language: str):
        """
        Client for querying the play store

        Args:
            app_id: as a dotted string, eg com.facebook.katana
            language: two letter language code
        """

        self.app_id = app_id
        self.language = language

    def app_exists(self) -> bool:
        """Boolean test if this client's (app,language) pair exists"""

        try:
            self.get_details()
            return True
        except google_play_scraper.exceptions.NotFoundError:
            return False

    def get_details(self) -> dict:
        """Return app's details as JSON dict"""

        return google_play_scraper.app(
            self.app_id, lang=self.language, country=PLAY_STORE_COUNTRY
        )

    def get_similar(self) -> list:
        """Return similar apps as list of IDs"""

        return play_scraper.similar(
            self.app_id, hl=self.language, gl=PLAY_STORE_COUNTRY
        )

    def get_reviews(self) -> list:
        """Return app's reviews as JSON"""
        return google_play_scraper.reviews_all(
            self.app_id,
            sleep_milliseconds=config.get("app.sleep.play_store"),
            lang=self.language,
            country=PLAY_STORE_COUNTRY,
        )


class AppleClient:
    def __init__(self, app_name: str, app_id: int, country: str):
        """
        Client for querying the app store

        Args:
            app_name: app name as string
            app_id: integer app ID code
            language: two letter language code
        """

        self.client = app_store_scraper.AppStore(
            app_name=app_name, app_id=app_id, country=country
        )

    def app_exists(self) -> bool:
        """Boolean test if this client's (app,language) pair exists"""

        if requests.get(self.client.url).status_code >= 400:
            return False
        else:
            return True

    def get_details(self) -> dict:
        """Return app's details as JSON dict"""

        self.client.get_details()
        return self.client.details

    def get_similar(self) -> list:
        """Return similar apps as list of IDs"""

        self.client.get_similar()
        return self.client.similar

    def get_reviews(self) -> list:
        """Return app's reviews as JSON"""

        self.client.review(
            retry_after=10, sleep=config.get("app.sleep.apple_store")
        )
        return self.client.reviews
