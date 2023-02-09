const gplay = require("google-play-scraper");
const app = process.argv[2];
const lang = process.argv[3];

gplay
  .app({ appId: app, lang: lang })
  .then((output) => console.log(JSON.stringify(output)));
