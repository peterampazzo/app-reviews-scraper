const store = require("app-store-scraper");
const app = process.argv[2];
const country = process.argv[3];

store
  .app({ id: app, country: country, ratings: true })
  .then((output) => console.log(JSON.stringify(output)))
  .catch(console.log);
