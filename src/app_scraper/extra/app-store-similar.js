"use strict";

const fs = require("fs");
const store = require("app-store-scraper");
const { count } = require("console");

const filename = process.argv[2];
// const app = process.argv[3];
const appId = process.argv[3];
// const country = process.argv[5].toLowerCase();

const Path = "../../data/" + filename + "/app-store/similar/";

store
  .similar({
    id: appId,
  })
  .then((result) => {
    fs.writeFileSync(
      Path + appId + ".json",
      JSON.stringify(result)
    );
  })
  .catch((error) => {
    console.log(appId, error.statusCode, error.statusMessage);
    // console.log(error);
  });
