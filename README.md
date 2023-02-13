# app-reviews-scraper

Supported dataset: 
1. App details
1. App reviews
1. Similar apps

Given one app id:

|               | Apple Store | Play Store |
| ------------- | ----------- | ---------- |
| (All) Reviews | Yes         | Yes        |
| App details   | Yes         | Yes        |
| Similar apps  | Yes         | Yes        |

App list:

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

## Usage

An example of the folder structure.

```
.
├── Dockerfile
├── README.md
├── app.conf
├── app_scraper
│   ├── __init__.py
│   ├── app_store.py
│   ├── apple.js
│   ├── constants.py
│   ├── google.js
│   ├── play_store.py
│   └── utils.py
├── data
│   ├── apps
│   │   ├── covid-19.json
│   │   ├── dating-apps.json
│   │   ├── dating-similar.json
│   │   ├── dating_apps.csv
│   │   ├── dating_apps_old.csv
│   │   ├── example.json
│   │   ├── fertility-extra.json
│   │   ├── fertility-init-similar.json
│   │   ├── fertility-init.json
│   │   ├── fertility-retry.json
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
├── poetry.lock
├── pyproject.toml
└── yarn.lock
```

Make sure to have Poetry and Yarn installed on your machine.

```
> poetry install
> yarn install
```

How to run:

```bash
poetry run app-store|play-store <app-list-filename> --reviews --details --similar
# <app-list-filename> is the filename of the JSON file (ext excluded) which must be located in data/apps/
# the value assigned to 'project' is the directory where the data will be dumped in data/

# To download the reviews
# --reviews
# To download the app details
# --details
# To download the similar apps
# --similar
```

## Libraries
### Play Store (Android)

- https://github.com/JoMingyu/google-play-scraper
- https://github.com/facundoolano/google-play-scraper

### App Store (iOS)

- https://github.com/cowboy-bebug/app-store-scraper
- https://github.com/facundoolano/app-store-scraper

### Extra

To run the detect language job make sure to install:

```
brew install virtualenv protobuf
```
