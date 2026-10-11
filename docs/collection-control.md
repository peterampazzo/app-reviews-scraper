# Collection controller guide

Use this guide for new controller-managed collections. The root
[README](../README.md) is the quickstart; this page documents controller
configuration, behavior and operational details. The legacy direct scraper CLI
and project-specific research launchers remain available, but do not provide the
controller's shared status/stop behavior.

## Configuration

Copy `configs/example.json` to a local configuration and edit its paths and explicit
steps. Paths are resolved relative to the configuration file, independent of the
shell directory. `data_root` is optional; the resolution precedence is CLI
`--data-root`, config `data_root`, `DATA_ROOT`, legacy `DATA_LOCATION`, then
`<OneDrive root>/Cosmic Latte/app-reviews-scraper-data`. On macOS, a unique
`~/Library/CloudStorage/OneDrive-*` root is detected. Set `ONEDRIVE_ROOT` when
discovery is ambiguous, or `DATA_ROOT` directly. Conflicting `DATA_ROOT` and
`DATA_LOCATION` values are rejected.

The resolved root is the directory containing project folders; the app list's
`project` field determines the output subdirectory. The input file is read-only.

Each step selects one store, explicit app IDs and separate locale strings. Google
steps may specify countries. Apple steps may use `resume_apple_from: "latest"` or
an existing archive directory. Resume semantics are unchanged; this milestone does
not fix ancestry reconstruction or add Google continuation-token resume. Steps run
sequentially and a worker failure ends the controller run for inspection.

The checked-in example app ID is a placeholder and cannot be used for collection.
Choose a real app-list file and IDs. In particular, `latest` remains the existing
scraper's largest-offset selection. Review the dry-run before launching.
`refresh_weeks` defaults to 5200, preserving fresh convenience CSV skips; a skipped
CSV is not proof that a historically interrupted query is complete.

The controller always requests all reviews (`--review-count -1`) for each selected
query; it has no per-step review-count limit. Keep the number of selected apps and
queries deliberately small when starting. For a bounded live smoke test, use the
direct scraper CLI with `--review-count`; see the README. That command contacts the
store and does not create controller run state.

`--dry-run` validates the config and prints worker commands. It makes no store
requests and creates no collection output. It does not prove that the store will
return results or that a worker can complete successfully.

```sh
.venv/bin/python scraper.py collect --config configs/local.json --dry-run
.venv/bin/python scraper.py collect --config configs/local.json --data-root "$DATA_ROOT" --dry-run
.venv/bin/python scraper.py collect --config configs/local.json --stop-at 2026-10-20T10:30:00+01:00
.venv/bin/python scraper.py status --config configs/local.json
.venv/bin/python scraper.py stop --config configs/local.json
```

The collect command stays in the foreground. `stop` requests a cooperative stop;
it does not claim the worker has already exited. The controller publishes `paused`
only after its worker exits. SIGINT and SIGTERM also request shutdown. Worker shutdown
allows 30 seconds for SIGINT, then 30 for SIGTERM, then SIGKILL with a further bounded
wait. Forced shutdown is recorded. Raw data are retained, although forced termination
may leave an unfinished last write as with any interrupted process.

Apple starts only after the shared request lock's mtime is at least two hours old.
Ten-second Apple pacing and existing request serialization remain in place. Collection
has no byte cap, consistent with the user's removal of the 10 GB limit; an existing
storage-pause marker still blocks the worker. HTTP retry policy stays in the transport.

## State and compatibility

New run logs, configuration and status live under `data_root/diagnostics/<run>/`.
`data_root/controller_status.json` is a separate current-run pointer: old controller
status files, earlier diagnostics and raw archives are untouched. Worker convenience
CSVs retain their existing refresh behavior. No exports are automatically rebuilt.
Status includes a process inventory separately from the saved status label. An
unverified previous controller state blocks a restart and requires inspection.

The controller holds both existing DatingAppsNLP/Tinder locks and checks the process
list before launching. A failed process inspection blocks launch. Historical Zoe/Surge
launchers do not share these locks: do not manually launch them alongside the new
controller. Full enforcement across every legacy entry point is a later migration.
The control commands govern only runs created by this controller.

## Safe migration of existing files

`migrate_data.py` defaults to a read-only preview from repository `data/` to the
resolved data root. The preview reads and hashes every source file; a large tree,
especially one on a cloud-synced volume, can take a long time. It does not copy or
delete collection data. Use `--report` to persist the complete per-file report, and
review conflicts before copying:

```sh
python migrate_data.py
python migrate_data.py --apply --report "$ONEDRIVE_ROOT/Cosmic Latte/app-reviews-scraper-migration.json"
```

Only `--apply` copies files. The copy preserves relative paths, verifies hashes, and
never overwrites a different destination file. It leaves the source tree untouched;
cleanup is a separate manual decision after checking the report.

## Docker

Mount the OneDrive data directory at `/data`, then set `DATA_ROOT=/data` or include
`"data_root": "/data"` in the container config. Mount app-list inputs read-only at
their configured container paths. The host OneDrive path is not built into the image.
