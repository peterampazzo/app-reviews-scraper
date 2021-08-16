"use strict";

const fs = require("fs");
const store = require("app-store-scraper");
const { count } = require("console");

const filename = process.argv[2];
const app = process.argv[3];
const appId = process.argv[4];
const country = process.argv[5].toLowerCase();

const Path = "../../data/" + filename + "/app-store/details/";

store
  .app({
    id: app,
    appId: appId,
    country: country,
    ratings: true,
  })
  .then((result) => {
    fs.writeFileSync(
      Path + app + "-" + country + ".json",
      JSON.stringify(result)
    );
  })
  .catch((error) => {
    console.log(app, country, error.statusCode, error.statusMessage);
    // console.log(error);
  });
