import os
import json

def create_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

def load_apps(filename):
    with open('data/apps/' + filename + '.json') as f:
        appsList = json.load(f)

    return appsList