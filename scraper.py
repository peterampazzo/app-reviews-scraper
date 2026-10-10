"""Script for scraping app stores"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
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
from scraper_backend.storage import StorageBudgetExceeded, check_budget, save_review_csv


def run(
    app_list: str,
    app_store_name: str,
    reviews: bool = False,
    details: bool = False,
    similar: bool = False,
    refresh_weeks=None,
    review_count=None,
    locales=None,
    countries=None,
    resume_apple_from=None,
    tier=None,
    app_ids=None,
    locale_plan=None,
    country_map=None,
):
    """Main scraper function. See __main__ argparse below for args"""

    if not any([reviews, details, similar]):
        raise RuntimeError("At least one of [reviews,details,similar] must be set.")
    if resume_apple_from and app_store_name != 'apple':
        raise ValueError('--resume-apple-from is only supported for Apple')

    # Internally, we use "app" to refer to Apple and "play" for Google,
    # as encoded in the constants file
    store = constants.STORE_NAMES[app_store_name]

    # Load store-specific configuration and app lists
    config = ConfigFactory.parse_file("app.conf")
    utils.set_logging(config)
    profile = utils.load_apps(app_list)
    project = profile[config.get("project_schema.project_name")]
    entries = [x for x in profile[config.get("project_schema.list_apps")]
               if tier is None or x.get('tier') == tier]
    apps = [
        x[config.get(f"project_schema.{store}_store")]
        for x in entries
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

    # Accept the documented string schema and the original object schema.
    apps = [dict(a) if isinstance(a, dict) else {"id": str(a), "name": str(a)} for a in apps]
    for a in apps:
        a["id"] = str(a["id"])
        a.setdefault("name", a["id"])
    if app_ids is not None:
        apps = [a for a in apps if a['id'] in app_ids]

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
    if locale_plan:
        plan = json.loads(Path(locale_plan).read_text())
        iterpairs = [(app, q['language'] if store=='play' else q['country'], q['country'])
                     for app in apps for q in plan.get(app['id'], [])]
    else:
        overrides = json.loads(Path(country_map).read_text()) if country_map else {}
        choices = locales or (constants.APP_STORE_COUNTRIES if store=='app' else constants.PLAY_STORE_LANGUAGES)
        iterpairs = [(app, locale, country) for app in apps for locale in choices
                     for country in ([locale] if store=='app' else countries or
                                     [overrides.get(app['id'], app.get('country', constants.PLAY_STORE_COUNTRY))])]
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    run_dir = Path(config.get('location.main')) / project / 'raw' / run_id / app_store_name
    run_dir.mkdir(parents=True)
    (run_dir / 'run.json').write_text(json.dumps(dict(
        run_id=run_id, platform=app_store_name, review_count=review_count, reviews=reviews,
        resume_apple_from=resume_apple_from,
        queries=[dict(app_id=a['id'], locale=l, country=c) for a,l,c in iterpairs],
        started_at=datetime.now(timezone.utc).isoformat()), indent=2))
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
    failures = 0
    for app, locale, country in iterpairs:
        check_budget()
        locale_key = locale if store == 'app' else f'{country}-{locale}'
        query_dir = run_dir / app['id'] / locale_key
        status = dict(app_id=app['id'], locale=locale, query_country=country,
                      platform=app_store_name, started_at=datetime.now(timezone.utc).isoformat())
        client = None
        try:
            # Create a client for sending off queries
            logging.info(f"Querying {app['name']} on {locale}.")
            if store == "app":
                client = AppleClient(
                    app_name=app["name"], app_id=app["id"], country=locale, raw_dir=query_dir
                )
                app_dirname = app["id"]
            else:
                client = GoogleClient(app_id=app["id"], language=locale, country=country, raw_dir=query_dir)
                app_dirname = app["id"].replace(".", "-")

            # Does this app exist for this country/language?
            if not reviews and not client.app_exists():
                logging.info(f"{app['name']} does not exist for {locale} - skip")
                status.update(status="app_not_found")
                continue

            # Fetch app details
            dpath = op.join(directories["details"], app_dirname, f"{locale_key}.json")
            if details and utils.file_needs_update(dpath, refresh_weeks):
                try:
                    dets = client.get_details()
                    utils.save_json(dpath, dets)
                    status['details_status'] = 'complete'
                    logging.debug("Completed details.")
                except StorageBudgetExceeded:
                    raise
                except Exception as exc:
                    status['details_error'] = str(exc)
                    logging.error(f'Details failed; still attempting reviews: {exc}')
            else:
                logging.debug("Details did not need update")

            # Fetch similar apps
            spath = op.join(directories["similar"], app_dirname, f"{locale_key}.json")
            if similar and utils.file_needs_update(spath, refresh_weeks):
                sim = client.get_similar()
                utils.save_json(spath, sim)
                logging.debug("Completed similar.")
            else:
                logging.debug("Similar did not need update")

            # Fetch app reviews
            rpath = op.join(directories["reviews"], app_dirname, f"{locale_key}.csv")
            if reviews and utils.file_needs_update(rpath, refresh_weeks):
                if store == 'app' and resume_apple_from:
                    source = Path(resume_apple_from) / app['id'] / locale
                    if resume_apple_from == 'latest':
                        # Select the furthest saved continuation across prior runs.
                        from urllib.parse import parse_qs, urlparse
                        candidates = []
                        for directory in run_dir.parent.parent.glob(f"*/apple/{app['id']}/{locale}"):
                            pages = sorted(directory.glob('page-*.json'))
                            if pages:
                                last = json.loads(pages[-1].read_text())
                                continuation = last.get('continuation')
                                if continuation:
                                    saved = int(parse_qs(urlparse(continuation).query)['offset'][0])
                                    candidates.append((saved, str(directory)))
                        source = Path(max(candidates)[1]) if candidates else run_dir / app['id'] / locale
                    offset = client.client.resume_from(source)
                    status.update(resumed_from=str(source), resumed_offset=offset,
                                  restored_rows=len(client.client.reviews))
                    logging.info(f'Resuming {locale} from offset {offset}')
                rev = client.get_reviews(review_count)
                status.update(status='complete', count=len(rev), stop_reason=client.stop_reason)
                provenance = dict(scrape_date=status['started_at'], query_country=country,
                                  query_language=locale if store=='play' else 'en-GB')
                if store == 'app':
                    provenance['country'] = country
                save_review_csv(rpath, rev, provenance)
                logging.debug(f'Saved {len(rev)} reviews, including empty-result completion files.')
            else:
                status.update(status="skipped_fresh")
                logging.debug("Reviews did not need update")

        except StorageBudgetExceeded as exc:
            status.update(status='paused_storage', error=str(exc))
            raise
        except KeyboardInterrupt:
            status.update(status="interrupted", error="Collection interrupted; archived pages retained")
            raise
        except Exception as e:
            failures += 1
            status.update(status="failed", error=str(e))
            logging.error("Uncaught exception, continue to next. " + str(e))
            continue

        # Sleep at end of (app, locale) pair to avoid hitting API request limits
        finally:
            query_dir.mkdir(parents=True, exist_ok=True)
            status['finished_at'] = datetime.now(timezone.utc).isoformat()
            (query_dir / 'status.json').write_text(json.dumps(status, indent=2))
            time.sleep(config.get("app.sleep.loop"))
            pbar.update()

    logging.info(f"Process completed with {failures} failed queries. Raw run: {run_dir}")
    return failures


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

    parser.add_argument('--locales', nargs='+', help='Country codes for Apple; language codes for Google. Default: all configured locales.')
    parser.add_argument('--countries', nargs='+', help='Google query storefronts (default us); not reviewer residence.')
    parser.add_argument('--resume-apple-from', help='Previous Apple run directory containing app-ID/storefront page archives')
    parser.add_argument('--tier', choices=['core', 'optional'], help='Only collect the selected input tier')
    parser.add_argument('--app-ids', nargs='+', help='Only collect these platform IDs from the input list')
    parser.add_argument('--locale-plan', help='JSON file mapping app IDs to explicit country/language queries')
    parser.add_argument('--country-map', help='JSON file mapping Google app IDs to their available countries')

    # cmd = "--list data/apps/example.json --store apple --details --similar --reviews".split()
    try:
        sys.exit(1 if run(**vars(parser.parse_args())) else 0)
    except StorageBudgetExceeded as exc:
        logging.error(str(exc))
        sys.exit(75)
