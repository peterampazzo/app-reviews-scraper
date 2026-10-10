"""Argument parsing for the backwards-compatible scraper command."""
import argparse
import logging

from .runner import run
from .storage import StorageBudgetExceeded


def main(argv=None):
    parser = argparse.ArgumentParser(description='Query an app store.')
    parser.add_argument('--list', type=str, dest='app_list', required=True,
                        help='path to JSON file containing apps to query')
    parser.add_argument('--store', type=str, choices=['apple', 'google'],
                        required=True, dest='app_store_name',
                        help='which app store to query, Apple App Store or Google Play Store')
    parser.add_argument('--reviews', action='store_true', help='fetch app reviews')
    parser.add_argument('--details', action='store_true', help='fetch app details')
    parser.add_argument('--similar', action='store_true', help='fetch similar apps')
    parser.add_argument('--refresh', type=float, dest='refresh_weeks',
                        help='refresh past results older than N weeks (default from app.conf)')
    parser.add_argument('--review-count', type=int,
                        help='maximum reviews; set -1 to fetch all reviews')
    parser.add_argument('--locales', nargs='+',
                        help='Apple storefronts or Google Play review languages')
    parser.add_argument('--countries', nargs='+',
                        help='Google Play query storefronts (default us)')
    parser.add_argument('--resume-apple-from',
                        help='previous Apple run directory containing page archives')
    parser.add_argument('--tier', choices=['core', 'optional'],
                        help='only collect the selected input tier')
    parser.add_argument('--app-ids', nargs='+',
                        help='only collect these platform IDs from the input list')
    parser.add_argument('--locale-plan',
                        help='JSON file mapping app IDs to explicit country/language queries')
    parser.add_argument('--country-map',
                        help='JSON file mapping Google app IDs to their available countries')
    parser.add_argument('--data-root',
                        help='collection data directory (overrides DATA_ROOT)')

    try:
        return 1 if run(**vars(parser.parse_args(argv))) else 0
    except StorageBudgetExceeded as exc:
        logging.error(str(exc))
        return 75
