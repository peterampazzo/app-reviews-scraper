import os
import glob
import json
import re
import pandas as pd
from constants import FOLDERS

def create_folders(paths: list) -> None:
    for p in paths:
        if not os.path.exists(p):
            os.makedirs(p)

def init_project(project):
    create_folders([
         f"data/{project}",
         f"data/{project}/app-store",
         f"data/{project}/play-store"
         ])

    for f in FOLDERS:
        create_folders([
            f"data/{project}/app-store/{f}", 
            f"data/{project}/play-store/{f}"
            ])

def load_apps(filename: str) -> dict:
    with open(f"data/apps/{filename}.json") as f:
        apps = json.load(f)

    return apps


def merge_reviews(appslist):

    # android
    project_folder = f"data/{appslist.project}/play-store/reviews"

    for subdir, dirs, files in os.walk(project_folder):
        files = [f for f in files if not f[0] == '.']
        dirs[:] = [d for d in dirs if not d[0] == '.']

        print(f"Found directory: {subdir}")
        reviews = pd.DataFrame()
        for fname in files:
            print(f"\t {fname}")
            df = pd.read_csv(f"{subdir}/{fname}")

            language = re.search('\-([^\.]+)\.', fname).group(1)

            df['lang'] = language
            reviews = reviews.append(df)

        reviews.to_csv(f"{subdir}/reviews.csv")

    # ios
    # TODO


def app_store_details_merge(appslist):
    project_folder = f"data/{appslist.project}/app-store/details"
    for subdir, dirs, files in os.walk(project_folder):
        apps = pd.DataFrame()
        for fname in files:
            if fname != "apps.csv":
                print(fname)

                with open(f"{subdir}/{fname}") as f:
                    data = json.load(f)

                del data["genres"]
                del data["genreIds"]
                del data["screenshots"]
                del data["languages"]
                del data["supportedDevices"]
                del data["ipadScreenshots"]
                del data["appletvScreenshots"]

                df = pd.DataFrame(data, index=[0])
                apps = apps.append(df)

        apps.to_csv(f"{subdir}/apps.csv")

def play_store_country(filename):
    return re.search("\-([^\.]+)\.", filename).group(1)

def app_store_country(filename):
    return re.search("(.+?)(\.[^.]*$|$)", filename).group(1)
