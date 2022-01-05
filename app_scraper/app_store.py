import os
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

    if not any([args.reviews, args.details, args.similar]):
        # If none option are chosen, break.
        logging.error("None option.")
        exit(1)

    profile = load_apps(os.path.join(config.get("location.input"), f"{args.list}.json"))
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

    logging.info(f"Running {project} with {len(apps)} on Apple App Store.")
    for app, country in itertools.product(apps, APP_STORE_COUNTRIES):
        logging.info(f"Querying {app['name']} on country {country}.")
        client = AppStore(app_name=app["name"], app_id=app["id"], country=country)

        if args.details:
            client.get_details()
            save_json(
                f"{directories['details']}/{app['id']}/{country}.json", client.details
            )
            logging.debug("Completed details.")

        if args.similar:
            client.get_similar()
            save_json(
                f"{directories['similar']}/{app['id']}/{country}.json", client.similar
            )
            logging.debug("Completed similar.")

        if args.reviews:
            client.review(sleep=config.get("app.sleep.apple_store"), retry_after=10)
            if client.reviews_count != 0:
                logging.debug(f"Fetched {str(client.reviews_count)} reviews.")
                df = pd.DataFrame(client.reviews, columns=APP_STORE_REVIEWS_COLUMNS)
                df["country"] = country
                df.to_csv(
                    os.path.join(directories["reviews"], app["id"], f"{country}.csv")
                )
                logging.debug("Completed reviews.")
            else:
                logging.debug("No reviwes fetched.")

        time.sleep(config.get("app.sleep.loop"))
    logging.info("Process completed.")
