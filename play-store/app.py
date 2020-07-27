import os
import pandas as pd
import json
from google_play_scraper import Sort, reviews_all

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

with open('apps-list.json') as f:
    appsList = json.load(f)

for selectedApp in appsList:
    print("App: %s" % selectedApp["id"])

    appPath = "reviews/" + selectedApp["id"] + "/"
    if not os.path.exists(appPath):
        os.makedirs(appPath)

    for l in LANGUAGES:

        print("Language: %s" % l)
        # print("Language: %s" % l)

        result = reviews_all(
            selectedApp["id"],
            sleep_milliseconds=1200,  # defaults to 0
            lang=l,
            country=COUNTRY,
            sort=Sort.MOST_RELEVANT,  # defaults to Sort.MOST_RELEVANT
            filter_score_with=None
        )

        if result != []:
            df = pd.DataFrame(result)
            df.to_csv("reviews/%s/%s-%s.csv" %
                      (selectedApp["id"], COUNTRY, l))
