import argparse
import os
import json
import pandas as pd
from utils import *
from play_store import play_store_app, play_store_reviews
from app_store import app_store_reviews

def play_store(apps_list: dict, details: bool, reviews: bool) -> None:
    apps = [x["android"] for x in apps_list["apps"] if x["android"] != None]
    df = pd.DataFrame()

    for app in apps:
        if details:
            detail = play_store_app(apps_list["project"], app["id"])
            df = df.append(detail)
        if reviews:
            play_store_reviews(apps_list["project"], app["id"])

    if details:
        df.to_csv(f"data/{apps_list.project}/play-store/apps.csv")


def app_store(apps_list: dict) -> None:
    apps = [x["ios"] for x in apps_list["apps"] if x["ios"] != None]
    for app in apps:
        app_store_reviews(apps_list["project"], app)


def main(args):
    print(args.list)
    apps = load_apps(args.list)
    init_project(apps.project)

    if args.play_store:
        play_store(apps, args.details, args.reviews)

    if args.ios:
        app_store(apps)

    if args.merge:
        app_store_details_merge(apps)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', dest='list')
    parser.add_argument('--play-store', dest='play_store', action='store_true')
    parser.add_argument('--ios', dest='ios', action='store_true')

    parser.add_argument('--reviews', dest='reviews', action='store_true')
    parser.add_argument('--details', dest='details', action='store_true')
    parser.add_argument('--similar', dest='similar', action='store_true')

    parser.add_argument('--merge', dest='merge', action='store_true')
    args = parser.parse_args()

    main(args)
