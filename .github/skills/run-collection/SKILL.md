---
name: run-collection
description: Run, monitor and stop review collection with the scraper controller, storing data in an external directory. Use when asked to start/dry-run/check/stop a collection, set up a config, change where data is stored, or run tests and lint.
---

# Run a collection

For the user-facing quickstart and workflow choice, read
[README.md](../../../README.md). Full controller behavior is in
[docs/collection-control.md](../../../docs/collection-control.md).

Use the shared controller for new generic runs. Do not substitute the direct
scraper CLI or research launchers: they do not provide the controller's shared
status/stop behavior. The checked-in example app ID is a placeholder, and the
controller requests all reviews for every selected query. Keep initial plans
narrow. A bounded live smoke test can use the direct CLI with `--review-count`,
but it makes a real store request and is not a controller-managed run.

## 1. Create a local config

Copy `configs/example.json` to `configs/local.json` (git-ignored via `configs/local*.json`).
Paths are resolved relative to the config file, not the shell directory.

- `data_root`: optional **where all output goes** (raw archives, CSVs, logs, status).
  The default is `<OneDrive root>/Cosmic Latte/app-reviews-scraper-data`; set
  `ONEDRIVE_ROOT` if OneDrive discovery is ambiguous, or set `DATA_ROOT` directly.
  It is the directory *containing* project folders; the app list's `project` field
  picks the subfolder. `--data-root` overrides config and environment.
- `apps`: app list JSON (read only, never modified). It can also live in the external directory.
- `steps`: one store (`apple` or `google`), explicit `app_ids`, `locales` (Google: also `countries`).
  Apple may set `resume_apple_from` to `"latest"` or an existing archive directory.
- `refresh_weeks`: default 5200 (skip fresh convenience CSVs).

Unknown top-level keys are rejected.

## 2. Always dry-run first

```sh
.venv/bin/python scraper.py collect --config configs/local.json --dry-run
```

Check the printed worker commands and that paths are under the intended `data_root`.
Dry-run validates configuration and prints commands only; it makes no store
requests and creates no collection output. It does not verify store availability.

## 3. Collect, monitor, stop

```sh
.venv/bin/python scraper.py collect --config configs/local.json [--stop-at 2026-10-20T10:30:00+01:00]
.venv/bin/python scraper.py status --config configs/local.json
.venv/bin/python scraper.py stop --config configs/local.json
```

- `collect` runs in the foreground; `--stop-at` takes ISO 8601 with timezone.
- `stop` is cooperative; `status` shows when the worker has actually exited (`paused`).
- Run state and logs: `<data_root>/diagnostics/<run>/`; pointer: `<data_root>/controller_status.json`.
- Don't run the legacy Zoe/Surge launchers at the same time; they don't share the controller locks.
- Apple only starts once the shared request lock is at least 2 hours old.

## Docker alternative

The `Dockerfile` entrypoint is `python scraper.py`, so the controller works in a container.
Mount the external data directory and use container paths in the config (for example
`"data_root": "/data"`). If omitted, set `DATA_ROOT=/data`:

```sh
docker build -t app-reviews-scraper .
docker run --rm -v /path/to/OneDrive/Cosmic-Latte-data:/data -v "$(pwd)/configs:/app/configs" \
  app-reviews-scraper collect --config configs/local.json --dry-run
```

Drop `--dry-run` to collect. `stop`/`status` need `docker exec <container> python scraper.py stop --config ...`
(use `--name`, and `-d` to run detached). The image needs `ps` (installed via `procps`); this
Docker path is untested.

## 4. Setup, tests, lint

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pytest ruff
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

Tests use temp dirs and dummy workers only; they never hit the stores or write to `data_root`.
CI installs `requirements.txt`, runs pytest, and runs Ruff. The project-specific
reproduction notes may use `requirements-lock.txt`; that lockfile is not needed for
the generic controller quickstart.

## Data migration safety

`migrate_data.py` is separate from collection. Its default preview hashes every
source file, does not copy or delete data, and may take a long time for a large or
cloud-synced source tree. Only add `--apply` after reviewing the preview. The source
tree is retained.
