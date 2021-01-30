import os
import pandas as pd
import json
from google_play_scraper import app, Sort, reviews_all
from utils import *

# Languages codes https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes
# Countries codes https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes

LANGUAGES = [
    "af", "am", "bg", "ca", "zh-HK", "zh-CN", "hr", "cs", "da",
    "nl", "en", "et", "fil", "fi", "fr", "de", "el", "he", "hi",
    "hu", "is", "id", "it", "ja", "ko", "lv", "lt", "ms", "no",
    "pl", "pt", "ro", "ru", "sr", "sk", "sl", "es", "sw", "sv",
    "th", "tr", "uk", "vi", "zu"
]
COUNTRY = "us"


def play_store_app(project, app):
    print(app)
    appDetails = app(
        app,
        lang="en",
        country="us"
    )

    del appDetails["histogram"]
    del appDetails["screenshots"]
    del appDetails["comments"]

    df = pd.DataFrame(appDetails, index=[0])
    return df


def play_store_reviews(project, app):
    path = "reviews/" + project + "/" + app + "/"
    create_folder(path)
    for l in LANGUAGES:
        result = reviews_all(
            app,
            sleep_milliseconds=1200,  # defaults to 0
            lang=l,
            country=COUNTRY,
            sort=Sort.MOST_RELEVANT,  # defaults to Sort.MOST_RELEVANT
            filter_score_with=None
        )

        if result != []:
            df = pd.DataFrame(result)
            df.to_csv("reviews/%s/%s/%s-%s.csv" %
                      (project, app, COUNTRY, l))
