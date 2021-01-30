"use strict";

const fs = require("fs");
const store = require("app-store-scraper");

const filename = process.argv[2];

if (!filename) {
  console.error("Missing filename");
  return;
}

const AppsList = require("../../data/apps/" + filename + ".json");
const Path = "../../data/" + AppsList.project + "/app-store/";

AppsList.apps.map((app) => {
  if (app.ios) {
    store
      .similar({ id: app.ios.id })
      .then((result) => {
        let data = JSON.stringify(result);
        fs.writeFileSync(Path + "similar/" + app.ios.id + ".json", data);
      })
      .catch(() => {
        console.log("Non found: " + app.ios.id);
      });
  }
});
