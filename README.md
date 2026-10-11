# App review scraper

Collect app details, reviews, and similar apps from the Apple App Store and
Google Play. Reusable scraping code lives in `scraper_backend/`; research-specific
DatingAppsNLP workflows live under `research/datingapps/`.

## Choose how to run

- **Recommended for new collections:** use the shared `collect` controller. It
  validates an explicit plan, supports dry-run/status/stop, and puts run state and
  logs under the configured data root. Follow the [collection quickstart](docs/collection-control.md).
- **Direct scraper CLI:** `scraper.py --list ...` remains supported for one-shot
  runs and compatibility with existing workflows. It does not use the controller's
  run coordination or status/stop controls. Its `--review-count` option is useful
  for a small live smoke test.
- **Research workflows:** see [DatingAppsNLP research tooling](research/datingapps/README.md).
  Those scripts use project-specific plans and are not the generic collection
  quickstart.

## Install and run offline checks

Use Python 3.9 or later. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pytest ruff
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

CI installs `requirements.txt`, runs pytest, and runs Ruff. `requirements-lock.txt`
is also provided for reproducible research environments; research reproduction
instructions may use it.

## First collection: configure, dry-run, smoke-test

The checked-in `configs/example.json` and `configs/example-apps.json` use the
placeholder ID `com.example.app`; they are examples, not runnable store targets.
Create a local controller config and edit it to select a real app list:

```sh
cp configs/example.json configs/local.json
```

For example, in `configs/local.json`, use a real profile and deliberately isolated
output directory:

```json
{
  "apps": "../research/datingapps/configs/zoe.json",
  "data_root": "/tmp/app-reviews-scraper-smoke",
  "refresh_weeks": 5200,
  "steps": [
    {
      "store": "google",
      "app_ids": ["com.surgeapp.zoe"],
      "locales": ["en"],
      "countries": ["us"]
    }
  ]
}
```

Config paths are resolved relative to the config file. The Zoe profile is a
project-specific example; replace it and its app ID with the app you intend to
collect. The controller's worker requests all reviews for each selected query, so
keep the dry-run and initial controller plan narrowly scoped.

First validate only the plan. This does not contact a store or create collection
output:

```sh
.venv/bin/python scraper.py collect --config configs/local.json --dry-run
```

Check that the printed command selects the intended app, store, locale/country and
data root. To make a **small live smoke test** with a review limit, use the direct
CLI instead (this contacts Google Play and writes under the temporary data root):

```sh
.venv/bin/python scraper.py \
  --list research/datingapps/configs/zoe.json \
  --store google --reviews --review-count 5 --refresh 0 \
  --locales en --countries us \
  --data-root /tmp/app-reviews-scraper-smoke
```

This is a real store request, not an offline test. It uses one app, one query, and
a five-review limit. Inspect the generated run manifest, archived page(s), status
and CSV below `/tmp/app-reviews-scraper-smoke/zoe/` before selecting a larger
controller plan. Once satisfied, run the controller without `--dry-run`; monitor
with `status` and request a cooperative stop with `stop`. See the
[controller guide](docs/collection-control.md) for config fields, output locations,
OneDrive defaults, deadlines and Docker use.

## Where data goes and what commands change

Collection output is kept outside the repository by default at
`<OneDrive sync root>/Cosmic Latte/app-reviews-scraper-data/`. Set `DATA_ROOT` to
override it or `ONEDRIVE_ROOT` to select an unambiguous OneDrive root. The
controller's `--data-root` takes precedence over config and environment. Use a
temporary or explicitly chosen root when testing. App-list input files are read
only; collection writes outputs under the data root.

The migration utility is separate from normal collection. Its default is a
read-only preview: it hashes every source file, does not copy or delete anything,
and can take a long time on a large or cloud-synced tree. **Only `--apply` copies
files.** It preserves the source and does not overwrite conflicting destination
files:

```sh
.venv/bin/python migrate_data.py --report /tmp/app-reviews-migration-preview.json
# Review the report before explicitly choosing to copy:
.venv/bin/python migrate_data.py --apply --report /tmp/app-reviews-migration-copy.json
```

Do not use `--apply` until the preview is complete and its conflicts have been
reviewed. Migration does not remove the original repository `data/` tree.

## Direct CLI reference

```sh
.venv/bin/python scraper.py --help
.venv/bin/python scraper.py --list path/to/apps.json --store apple --reviews --details --similar
```

Input JSON has a `project` name and an `apps` list containing Apple (`ios`) and/or
Google (`android`) IDs:

```json
{
  "project": "project-name",
  "apps": [{"android": "com.vendor.app", "ios": "123456789"}]
}
```

For legacy controller operation, safe migration details and Docker examples, see
[collection control](docs/collection-control.md). For research-specific historical
collection plans and analysis, see the [research docs](research/datingapps/README.md).
