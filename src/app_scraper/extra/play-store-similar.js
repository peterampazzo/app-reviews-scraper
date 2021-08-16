"use strict";

const fs = require("fs");
const gplay = require("google-play-scraper");
const { count } = require("console");

const filename = process.argv[2];
const appId = process.argv[3];

const Path = "../../data/" + filename + "/play-store/similar/";

gplay
.similar({ appId: appId })
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
    