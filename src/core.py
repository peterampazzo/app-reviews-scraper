import argparse
import os
import json
import pandas as pd
from utils import *
from play_store import play_store_app, play_store_reviews
from app_store import app_store_reviews

FOLDERS = ["reviews", "similar", "details"]

def android(appslist):
    apps = [x["android"] for x in appslist["apps"] if x["android"] != None]
    csv = pd.DataFrame()

    for app in apps:
        df = play_store_app(appslist["project"], app["id"])
        csv = csv.append(df)
        play_store_reviews(appslist["project"], appapp["id"])

    csv.to_csv("../data/" + appslist["project"] + "/play-store/apps.csv")

def ios(appslist):
    apps = [x["ios"] for x in appslist["apps"] if x["ios"] != None]
    for app in apps:
        app_store_reviews(appslist["project"], app)

def main(args):
    print(args.list)
    apps = load_apps(args.list) # load app list
    create_folder("../data/" + apps["project"]) # create main project folder

    if args.android:
        android(apps)

    if args.ios:
        ios(apps)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', dest='list')
    parser.add_argument('--android', dest='android', action='store_true')
    parser.add_argument('--ios', dest='ios', action='store_true')
    args = parser.parse_args()

    main(args)
