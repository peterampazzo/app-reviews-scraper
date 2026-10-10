# App scraper 

Script for scraping app details, reviews and similar apps from the Apple App Store or Google Play Store.

For the opt-in shared collection controller, configuration examples, and graceful
stop/status commands, see [collection control](docs/collection-control.md).
The original command-line interface below remains supported.

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

### Docker image

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

### Data location

Collection output defaults to a dedicated folder under the detected OneDrive sync
root (`Cosmic Latte/app-reviews-scraper-data`). Set `DATA_ROOT` to override it;
`ONEDRIVE_ROOT` can select the sync root explicitly. The legacy `DATA_LOCATION`
variable is supported temporarily when `DATA_ROOT` is unset.

For a regular local run, point the input file at its actual location and optionally
override the output root:

```sh
export ONEDRIVE_ROOT="/path/to/OneDrive sync root"
export DATA_ROOT="$ONEDRIVE_ROOT/Cosmic Latte/app-reviews-scraper-data"
python scraper.py --list path/to/list.json --store apple --details --similar --reviews
```

### Docker run

When running on Docker, mount both the external output folder and the input file.
The container writes to `/data`; the host OneDrive path is never built into the image.

```
docker run --rm \
  -v "$DATA_ROOT:/data" \
  -v "$(pwd)/path/to/list.json:/inputs/apps.json:ro" \
  app-reviews-scraper \
  --list /inputs/apps.json --store apple --details --similar --reviews
```

Optional:
```
docker run --rm \
  -v "$DATA_ROOT:/data" \
  -v "$(pwd)/path/to/list.json:/inputs/apps.json:ro" \
  -e HEALTH_CHECK=something -e LOGS_FILE=example \
  app-reviews-scraper --list /inputs/apps.json --store apple --details --similar --reviews
```

Migrate an existing repository-local `data/` tree with a read-only preview first:

```sh
python migrate_data.py
python migrate_data.py --apply --report "$DATA_ROOT/../app-reviews-scraper-migration.json"
```

The migration command never deletes or overwrites source files. Existing destination
files are hash-compared; conflicts are reported and left untouched.

### Status reporting 
Status reporting is possible with an account on `www.healthchecks.io`. Set up a project on there, get a URL for pinging, and then assign to the `HEALTH_CHECK` env variable the profile id. 

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

## Current project layout

```text
.
├── scraper.py                 # backwards-compatible CLI
├── scraper_backend/           # runner, controller, stores, transport and storage
├── configs/                   # generic examples
├── research/datingapps/       # project-specific workflows, inputs and analysis
└── tests/

# Collection outputs are outside the repository by default:
<OneDrive root>/Cosmic Latte/app-reviews-scraper-data/
```

The following directory tree is a historical example from an earlier version,
not the current source layout.

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


## Zoe research collection (2026 compatibility update)

Project-specific collection notes and analysis live under
[research/datingapps/](research/datingapps/), separate from the reusable scraper.
