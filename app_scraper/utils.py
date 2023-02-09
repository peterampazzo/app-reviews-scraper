import os
import sys
import glob
import json
import re
import pandas as pd
from app_scraper.constants import FOLDERS
import logging


def set_logging(config):
    logging.basicConfig(
        level=logging.getLevelName(config.get("app.logging_level")),
        format="[%(asctime)s] - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    for logger in config.get("app.logger"):
        logging.getLogger(logger).setLevel(
            logging.getLevelName(config.get("app.logging_level_modules"))
        )


def create_folder(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def create_app_folders(
    apps: list,
    directories: dict,
    details: bool,
    similar: bool,
    reviews: bool,
    dashed: bool = False,
):
    for app in apps:
        app_name = app["id"].replace(".", "-") if dashed else app["id"]
        if details:
            create_folder(f"{directories['details']}/{app_name}")
        if similar:
            create_folder(f"{directories['similar']}/{app_name}")
        if reviews:
            create_folder(f"{directories['reviews']}/{app_name}")


def get_directories(root, store, project):
    main_dir = os.path.join(root, project, store)
    directories = {
        "details": os.path.join(main_dir, "details"),
        "similar": os.path.join(main_dir, "similar"),
        "reviews": os.path.join(main_dir, "reviews"),
    }
    return directories


def load_apps(filename: str) -> dict:
    try:
        with open(filename) as f:
            apps = json.load(f)

        return apps
    except FileNotFoundError:
        logging.error(f"{filename} doesn't exist.")


def save_json(filename: str, content) -> None:
    with open(filename, "w") as f:
        json.dump(content, f)


def merge_reviews(appslist):

    # android
    project_folder = f"data/{appslist.project}/play-store/reviews"

    for subdir, dirs, files in os.walk(project_folder):
        files = [f for f in files if not f[0] == "."]
        dirs[:] = [d for d in dirs if not d[0] == "."]

        print(f"Found directory: {subdir}")
        reviews = pd.DataFrame()
        for fname in files:
            print(f"\t {fname}")
            df = pd.read_csv(f"{subdir}/{fname}")

            language = re.search("\-([^\.]+)\.", fname).group(1)

            df["lang"] = language
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
