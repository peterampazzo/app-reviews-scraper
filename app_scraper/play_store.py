import os
import pandas as pd
import time
import itertools
import argparse
import logging
from pyhocon import ConfigFactory
import google_play_scraper
import play_scraper
from app_scraper.utils import (
    create_app_folders,
    set_logging,
    load_apps,
    get_directories,
    save_json,
)
from app_scraper.constants import PLAY_STORE_LANGUAGES, PLAY_STORE_COUNTRY


def run():
    config = ConfigFactory.parse_file("app.conf")
    set_logging(config)

    parser = argparse.ArgumentParser(description="Query Google Play Store.")
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
        x[config.get("project_schema.play_store")]
        for x in profile[config.get("project_schema.list_apps")]
        if x[config.get("project_schema.play_store")] != None
    ]

    directories = get_directories(
        root=config.get("location.main"),
        store=config.get("location.play_store"),
        project=project,
    )
    create_app_folders(
        apps=apps,
        directories=directories,
        details=args.details,
        similar=args.similar,
        reviews=args.reviews,
        dashed=True,
    )

    logging.info(f"Running {project} with {len(apps)} on Google Play Store.")
    for app, language in itertools.product(apps, PLAY_STORE_LANGUAGES):
        try:
            logging.info(f"Querying {app['id']} on language {language}.")

            app_name_dashed = app["id"].replace(".", "-")

            if args.details:
                details = google_play_scraper.app(
                    app["id"], lang=language, country=PLAY_STORE_COUNTRY
                )
                save_json(
                    f"{directories['details']}/{app_name_dashed}/{language}.json", details
                )
                logging.debug("Completed details.")

            if args.similar:
                similar = play_scraper.similar(
                    app_id=app["id"], detailed=False, hl=language, gl=PLAY_STORE_COUNTRY
                )
                save_json(
                    f"{directories['similar']}/{app_name_dashed}/{language}.json", similar
                )
                logging.debug("Completed similar.")

            if args.reviews:
                result = google_play_scraper.reviews_all(
                    app["id"],
                    sleep_milliseconds=config.get("app.sleep.play_store"),  # defaults to 0
                    lang=language,
                    country=PLAY_STORE_COUNTRY,
                    sort=google_play_scraper.Sort.MOST_RELEVANT,  # defaults to Sort.MOST_RELEVANT
                    filter_score_with=None,
                )

                if result != []:
                    df = pd.DataFrame(result)
                    df["language"] = language
                    df.to_csv(
                        os.path.join(
                            directories["reviews"], app_name_dashed, f"{language}.csv"
                        )
                    )
                    logging.debug(f"Completed reviews, {len(result)} fetched.")
                else:
                    logging.debug("No reviwes fetched.")

            time.sleep(config.get("app.sleep.loop"))
        except Exception as error:
            logging.error(f"App: {app['id']} - Language: {language}.")
            logging.error(f"Error: {error}")
    logging.info("Completed.")