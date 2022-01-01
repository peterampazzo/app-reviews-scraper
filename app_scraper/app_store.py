import os
import sys
import argparse
from pyhocon import ConfigFactory
import pandas as pd
import time
from app_store_scraper import AppStore
import itertools
from app_scraper.utils import (
    load_apps,
    save_json,
    create_app_folders,
    get_directories,
    set_logging,
)
from app_scraper.constants import APP_STORE_COUNTRIES, APP_STORE_REVIEWS_COLUMNS
import logging


def run():
    config = ConfigFactory.parse_file("app.conf")
    set_logging(config)

    parser = argparse.ArgumentParser(description="Query Apple App Store.")
    parser.add_argument("list", type=str, help="")
    parser.add_argument("--reviews", action="store_true", help="Query reviews")
    parser.add_argument("--details", action="store_true", help="Query details")
    parser.add_argument("--similar", action="store_true", help="Query similar")
    args = parser.parse_args()

    if all([args.reviews, args.details, args.similar]):
        # If none option are chosen, break.
        logging.error("None option.")
        return

    profile = load_apps(args.list)
    project = profile[config.get("project_schema.project_name")]
    apps = [
        x[config.get("project_schema.app_store")]
        for x in profile[config.get("project_schema.list_apps")]
        if x[config.get("project_schema.app_store")] != None
    ]

    directories = get_directories(
        root=config.get("location.main"),
        store=config.get("location.app_store"),
        project=project,
    )
    create_app_folders(
        apps=apps,
        directories=directories,
        details=args.details,
        similar=args.similar,
        reviews=args.reviews,
    )

    for app, country in itertools.product(apps, APP_STORE_COUNTRIES):
        logging.info(f"Running {app['id']} on country {country}.")
        client = AppStore(app_name=app["name"], app_id=app["id"], country=country)

        if args.details:
            client.get_details()
            save_json(
                f"{directories['details']}/{app['id']}/{country}.json", client.details
            )

        if args.similar:
            client.get_similar()
            save_json(
                f"{directories['similar']}/{app['id']}/{country}.json", client.similar
            )

        if args.reviews:
            client.review(sleep=config.get("app.apple_store.sleep"))
            if client.reviews_count != 0:
                df = pd.DataFrame(client.reviews, columns=APP_STORE_REVIEWS_COLUMNS)
                df["country"] = country
                df.to_csv(
                    os.path.join(directories["reviews"], app["id"], f"{country}.csv")
                )

        time.sleep(config.get("app.apple_store.sleep"))
