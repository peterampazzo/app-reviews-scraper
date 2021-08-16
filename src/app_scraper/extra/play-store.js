"use strict";

const fs = require("fs");
const gplay = require("google-play-scraper");

const filename = process.argv[2];
const details = process.argv.find((a) => a === "--details") ? true : false;
const similar = process.argv.find((a) => a === "--similar") ? true : false;

if (!filename) {
  console.error("Missing filename");
  return;
}

if (!details && !similar) {
  console.error("You need to specify at least one option");
  return;
}

const AppsList = require("../../data/apps/" + filename + ".json");
const Path = "data/" + AppsList.project + "/play-store/";

AppsList.apps.map((app) => {
  if (app.android) {
    if (details) {
      gplay
        .app({ appId: app.android.id })
        .then((result) => {
          let data = JSON.stringify(result);
          fs.writeFileSync(Path + "details/" + app.android.id + ".json", data);
        })
        .catch((e) => {
          console.log("Non found: " + app.android.id);
        });
    }
    if (similar) {
      gplay
        .similar({ appId: app.android.id })
        .then((result) => {
          let data = JSON.stringify(result);
          fs.writeFileSync(Path + "similar/" + app.android.id + ".json", data);
        })
        .catch(() => {
          console.log("Non found: " + app.android.id);
        });
    }
  }
});
