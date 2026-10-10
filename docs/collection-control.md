# Collection control: first refactoring milestone

The source checkpoint is `b6d7a52`. The new controller is opt-in; no collection is
started by installing or testing it. Existing scraper arguments and archives remain
compatible. No historical launchers have been removed or silently redirected.

## Configuration

Copy `configs/example.json` to a local configuration and edit its paths and explicit
steps. Paths are resolved relative to the configuration file, independent of the
shell directory. `data_root` is the directory containing project folders (for example
DatingAppsNLP/data), not the project folder inside it. The app list's `project` field
continues to determine the raw output subdirectory. The input file is never edited.

Each step selects one store, explicit app IDs and separate locale strings. Google
steps may specify countries. Apple steps may use `resume_apple_from: "latest"` or
an existing archive directory. Resume semantics are unchanged; this milestone does
not fix ancestry reconstruction or add Google continuation-token resume. Steps run
sequentially and a worker failure ends the controller run for inspection.

The example is illustrative, not the agreed next collection plan. In particular,
`latest` remains the existing scraper's largest-offset selection. Review the dry-run
before launching. `refresh_weeks` defaults to 5200, preserving fresh convenience CSV
skips; a skipped CSV is not proof that a historically interrupted query is complete.

```sh
.venv/bin/python scraper.py collect --config configs/local.json --dry-run
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

## Remaining refactoring work

1. Move existing locale-plan generation into configuration and migrate the legacy
   launchers one at a time, including common locks at every entry point.
2. Unify Apple resume history and implement verified Google token checkpoints.
3. Consolidate exports and preserve all observations while deduplicating by ID.
4. Add incremental summaries after snapshot/export equivalence checks.
5. Retire duplicated launchers only after matching their selected plans and behavior.

This milestone deliberately avoids archive scans, data migrations, client rewrites,
and dependency upgrades. Tests use temporary files and local dummy workers only.
