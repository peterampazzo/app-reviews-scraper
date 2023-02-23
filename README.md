# App scraper 

Script for scraping app details, reviews and similar apps from the Apple App Store or Google Play Store.

## Instructions from Francesco

-    Given a list of apps ID download the similar apps, reviews and ratings.
-    Improve the handling of exceptions (ie, time out, too many requests, validating countries without data, validating language -number reviews download vs printed on the page)
-    Number of rating and similar apps are fetched from the two stores using libraries written in NodeJS - consider a way to make it more consistent with the rest of the Python codebase
-    Trigger automatic downloading (ie, Airflow trigger of docker image which dumps the data in S3 - needs to be discussed with Doug)

## Installation 

Install the requirements via pip (preferably in a clean evironment): 
```
pip install -r requirements.txt 
```

To run the detect language job make sure to install:
```
brew install virtualenv protobuf
```

## Usage 

Scrape app details, reviews and similars for the apps in a JSON list: 
```
python scraper.py --list path/to/list.json --store app --details --similar --reviews
```

For full usage, run `python scraper.py -h`

> **Warning** 
> To avoid hitting request limits for the app store APIs, the script will only update results on the local filesystem older than `REFRESH` weeks (default = 1). 

The `app.conf` file contains further configuration options, for example the sleep time between requests.


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

