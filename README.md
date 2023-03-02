# App scraper 

Script for scraping app details, reviews and similar apps from the Apple App Store or Google Play Store.

## Installation 

### Locally

Install the requirements via pip (preferably in a clean evironment): 
```
pip install -r requirements.txt 
```

To run the detect language job make sure to install:
```
brew install virtualenv protobuf
```

### Docker 

```
docker build -t app-reviews-scraper .
```

## Usage 

The `app.conf` file contains further configuration options, for example the sleep time between requests.

> **Warning** 
> To avoid hitting request limits for the app store APIs, the script will only update results on the local filesystem older than `REFRESH` weeks (default = 1, set in `app.conf`). 

### Locally 

Scrape app details, reviews and similars for the apps in a JSON list: 
```
python scraper.py --list path/to/list.json --store apple --details --similar --reviews
```

For full usage, run
```
python scraper.py -h 
```

### Docker 

When running on Docker, the container needs to be able to access the host filesystem for read/write access. 
Assuming the JSON input lists are in the `data/` directory, then the output will also go in this same directory (as well as the logfile). This is conveyed using the `-v` flag. 
```
docker run -t -v $(pwd)/data:/app/data app-reviews-scraper --list data/apps/example.json --store apple --details --similar --reviews
```

### Status reporting 
Status reporting is possible with an account on `www.healthchecks.io`. Set up a project on there, get a URL for pinging, and then write this into `utils.send_healthcheck()` and enable the code block at `scraper.py#L82`. 

## App lists

The input JSON app lists should be structured as follows:

```json
{
  "project": "project-name",
  "apps": [
    {
      "android": "",
      "ios": ""
    }
  ]
}
```

## Expected directory structure 

An example of the folder structure.

```
.
├── Dockerfile
├── README.md
├── app.conf
├── app_scraper
│   ├── __init__.py
│   ├── app_store.py
│   ├── constants.py
│   ├── play_store.py
│   └── utils.py
├── data
│   ├── apps
│   │   ├── covid-19.json
│   │   ├── dating.json
│   │   ├── example.json
│   │   └── fertility.json
│   ├── covid-19
│   │   ├── app-store
│   │   │   ├── details
│   │   │   │   ├── 1408008382
│   │   │   │   ├── 1501478858
│   │   │   │   │   ├── ae.json
│   │   │   │   │   ├── ag.json
│   │   │   │   │   ├── gm.json
│   │   │   │   │   └── gr.json
│   │   │   │   ├── 1502037648
│   │   │   │   ├── 1503026854
│   │   │   │   ├── 1503717224
│   │   │   │   │   ├── mr.json
│   │   │   │   │   ├── ms.json
│   │   │   │   │   ├── ro.json
│   │   │   │   │   ├── vn.json
│   │   │   │   │   ├── ye.json
│   │   │   │   │   ├── za.json
│   │   │   │   │   └── zw.json
│   │   │   │   ├── 1504655876
│   │   │   │   ├── 1509242894
│   │   │   │   │   ├── ae.json
│   │   │   │   │   ├── md.json
│   │   │   │   │   ├── ye.json
│   │   │   │   │   ├── za.json
│   │   │   │   │   └── zw.json
│   │   │   ├── reviews
│   │   │   │   ├── 1408008382
│   │   │   │   ├── 1520427663
│   │   │   │   ├── 1520443509
│   │   │   │   └── 1523594087
│   │   │   └── similar
│   │   │       ├── 1408008382
│   │   │       ├── 1520443509
│   │   │       └── 1523594087
│   │   └── play-store
│   │       ├── details
│   │       │   ├── at-roteskreuz-stopcorona
│   │       │   │   ├── af.json
│   │       │   │   ├── ar.json
│   │       │   │   ├── en.json
│   │       │   │   ├── pt-PT.json
│   │       │   │   ├── ro.json
│   │       │   │   ├── zh-CN.json
│   │       │   │   └── zh-TW.json
│   │       │   ├── au-gov-health-covidsafe
│   │       │   │   ├── af.json
│   │       │   │   ├── ar.json
│   │       │   │   ├── az.json
│   │       │   │   ├── ja.json
│   │       │   │   ├── jw.json
│   │       │   │   ├── pt-BR.json
│   │       │   │   ├── pt-PT.json
│   │       │   │   ├── xh.json
│   │       │   │   ├── zh-CN.json
│   │       │   │   ├── zh-TW.json
│   │       │   │   └── zu.json
│   │       │   ├── az-gov-etabib
│   │       │   ├── bh-bahrain-corona-tracker
│   │       │   ├── co-gov-ins-guardianes
│   │       │   ├── com-covidtracker-hse
│   │       │   ├── uk-nhs-covid19-production
│   │       │   └── uy-gub-salud-plancovid19uy
│   │       ├── review
│   │       ├── reviews
│   │       │   ├── at-roteskreuz-stopcorona
│   │       │   ├── au-gov-health-covidsafe
│   │       │   │   ├── ar.csv
│   │       │   │   ├── en.csv
│   │       │   │   ├── nl.csv
│   │       │   │   ├── sm.csv
│   │       │   │   ├── zh-CN.csv
│   │       │   │   └── zh-TW.csv
│   │       │   ├── az-gov-etabib
│   │       │   ├── bh-bahrain-corona-tracker
│   │       │   ├── uk-nhs-covid19-production
│   │       │   └── uy-gub-salud-plancovid19uy
│   │       └── similar
│   │           ├── at-roteskreuz-stopcorona
│   │           │   ├── af.json
│   │           │   ├── ar.json
│   │           │   ├── vi.json
│   │           │   ├── xh.json
│   │           │   ├── zh-CN.json
│   │           │   ├── zh-TW.json
│   │           │   └── zu.json
│   │           ├── au-gov-health-covidsafe
│   │           │   ├── af.json
│   │           │   ├── zh-TW.json
│   │           │   └── zu.json
├── package.json
├── pyproject.toml
└── yarn.lock
```


## Libraries
### Play Store (Android)

- https://github.com/JoMingyu/google-play-scraper
- https://github.com/facundoolano/google-play-scraper

### App Store (iOS)

- https://github.com/cowboy-bebug/app-store-scraper
- https://github.com/facundoolano/app-store-scraper

