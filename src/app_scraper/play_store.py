import os
import pandas as pd
import json
import time
from google_play_scraper import app, Sort, reviews_all
from utils import *
from constants import PLAY_STORE_LANGUAGES as LANGUAGES
from constants import PLAY_STORE_COUNTRY as COUNTRY

def play_store_app(project, application):
    print(f"App: {application}")

    try:
        appDetails = app(
            application,
            lang="en",
            country="us"
        )

        with open(f"data/{project}/play-store/details/{application}.json", 'w') as f:
            json.dump(appDetails, f)

        del appDetails["histogram"]
        del appDetails["screenshots"]
        del appDetails["comments"]
        if "supportedDevices" in appDetails:
            del appDetails["supportedDevices"]

        df = pd.DataFrame(appDetails, index=[0])
        print("Downloaded \n")
        return df

    except Exception as e:
        print(f"Error: {e} \n")


def play_store_reviews(project, app):
    path = f"data/{project}/play-store/reviews/{app}/"
    create_folders([path])
    for lang in LANGUAGES:
        print(lang)
        result = reviews_all(
            app,
            sleep_milliseconds=1200,  # defaults to 0
            lang=lang,
            country=COUNTRY,
            sort=Sort.MOST_RELEVANT,  # defaults to Sort.MOST_RELEVANT
            filter_score_with=None
        )

        if result != []:
            df = pd.DataFrame(result)
            df.to_csv(f"data/{project}/play-store/reviews/{app}/{COUNTRY}-{lang}.csv")

def play_store_similar(project, app):
    # for country in LANGUAGES:
    os.system(f"node extra/play-store-similar {project} {app}")
    time.sleep(0.001)

