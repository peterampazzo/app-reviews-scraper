"""Script for scraping app stores"""

import argparse
import itertools
import logging
import os.path as op
import sys
import time

import enlighten
import pandas as pd
import schedule
from pyhocon import ConfigFactory

from scraper_backend import constants, utils
from scraper_backend.clients import AppleClient, GoogleClient


def run(
    app_list: str,
    app_store_name: str,
    reviews: bool = False,
    details: bool = False,
    similar: bool = False,
    refresh_weeks=None,
    review_count=None,
):
    """Main scraper function. See __main__ argparse below for args"""

    if not any([reviews, details, similar]):
        raise RuntimeError("At least one of [reviews,details,similar] must be set.")

    # Internally, we use "app" to refer to Apple and "play" for Google,
    # as encoded in the constants file
    store = constants.STORE_NAMES[app_store_name]

    # Load store-specific configuration and app lists
    config = ConfigFactory.parse_file("app.conf")
    utils.set_logging(config)
    profile = utils.load_apps(app_list)
    project = profile[config.get("project_schema.project_name")]
    apps = [
        x[config.get(f"project_schema.{store}_store")]
        for x in profile[config.get("project_schema.list_apps")]
        if x[config.get(f"project_schema.{store}_store")] != None
    ]
    if refresh_weeks is None:
        refresh_weeks = config.get("app").get("refresh_weeks")
    else:
        refresh_weeks = float(refresh_weeks)

    if review_count is None:
        review_count = config.get("app").get("review_count")
    else:
        review_count = int(review_count)
    if review_count == -1:
        review_count = sys.maxsize

    # Play store apps don't have an explicit name but this code requires that,
    # so we just use the ID as name
    if store == "play":
        for a in apps:
            a["name"] = a["id"]

    # Generate output directories and create them
    directories = utils.get_directories(
        root=config.get("location.main"),
        store=config.get(f"location.{store}_store"),
        project=project,
    )
    utils.create_app_folders(
        apps=apps,
        directories=directories,
        details=details,
        similar=similar,
        reviews=reviews,
        dashed=(store == "play"),
    )

    # Subtle difference here. For Apple, we loop over (app, country) pairs.
    # For Google, we loop over (app, language) pairs
    if store == "app":
        iterpairs = itertools.product(apps, constants.APP_STORE_COUNTRIES)
    elif store == "play":
        iterpairs = itertools.product(apps, constants.PLAY_STORE_LANGUAGES)
    iterpairs = list(iterpairs)
    logging.info(f"Running {project} with {len(apps)} on {store} store.")

    # To enable status reporting via ping. See utils.send_healthcheck() to
    # enter the correct ping URL.
    if config.get("healthcheck") != "":
        schedule.every(5).minutes.do(utils.send_healthcheck)
        utils.launch_background_task()

    # Progress bar
    manager = enlighten.get_manager()
    pbar = manager.counter(
        total=len(iterpairs), desc="(app, locale) pairs", unit="pairs"
    )

    # Ready to do the scraping....
    for app, locale in iterpairs:
        try:
            # Create a client for sending off queries
            logging.info(f"Querying {app['name']} on {locale}.")
            if store == "app":
                client = AppleClient(
                    app_name=app["name"], app_id=app["id"], country=locale
                )
                app_dirname = app["id"]
            else:
                client = GoogleClient(app_id=app["id"], language=locale)
                app_dirname = app["id"].replace(".", "-")

            # Does this app exist for this country/language?
            if not client.app_exists():
                logging.info(f"{app['name']} does not exist for {locale} - skip")
                continue

            # Fetch app details
            dpath = op.join(directories["details"], app_dirname, f"{locale}.json")
            if details and utils.file_needs_update(dpath, refresh_weeks):
                dets = client.get_details()
                utils.save_json(dpath, dets)
                logging.debug("Completed details.")
            else:
                logging.debug("Details did not need update")

            # Fetch similar apps
            spath = op.join(directories["similar"], app_dirname, f"{locale}.json")
            if similar and utils.file_needs_update(spath, refresh_weeks):
                sim = client.get_similar()
                utils.save_json(spath, sim)
                logging.debug("Completed similar.")
            else:
                logging.debug("Similar did not need update")

            # Fetch app reviews
            rpath = op.join(directories["reviews"], app_dirname, f"{locale}.csv")
            if reviews and utils.file_needs_update(rpath, refresh_weeks):
                rev = client.get_reviews(review_count)
                if len(rev):
                    logging.debug(f"Fetched {len(rev)} reviews.")
                    df = pd.DataFrame(rev)
                    if store == "app":
                        df["country"] = locale
                    else:
                        df["language"] = locale
                    df.to_csv(rpath)
                    logging.debug("Completed reviews.")
                else:
                    logging.debug("No reviews fetched.")
            else:
                logging.debug("Reviews did not need update")

        except Exception as e:
            logging.error("Uncaught exception, continue to next. " + str(e))
            continue

        # Sleep at end of (app, locale) pair to avoid hitting API request limits
        finally:
            time.sleep(config.get("app.sleep.loop"))
            pbar.update()

    logging.info("Process completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query an app store.")
    parser.add_argument(
        "--list",
        type=str,
        dest="app_list",
        required=True,
        help="path to JSON file containing apps to query",
    )
    parser.add_argument(
        "--store",
        type=str,
        choices=["apple", "google"],
        required=True,
        dest="app_store_name",
        help="which app store to query, apple (App Store) or google (Play Store)",
    )
    parser.add_argument("--reviews", action="store_true", help="fetch app reviews")
    parser.add_argument("--details", action="store_true", help="fetch app details")
    parser.add_argument("--similar", action="store_true", help="fetch similar apps")
    parser.add_argument(
        "--refresh",
        type=float,
        dest="refresh_weeks",
        help="refresh past results older than N weeks from now (default set in app.conf)",
    )
    parser.add_argument(
        "--review-count",
        type=int,
        help="fetch a maximum of N reviews (default set in app.conf). Set -1 for all reviews.",
    )

    # cmd = "--list data/apps/example.json --store apple --details --similar --reviews".split()
    run(**vars(parser.parse_args()))
