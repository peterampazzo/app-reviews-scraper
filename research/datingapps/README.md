# DatingAppsNLP research tooling

This tree contains project-specific collection policies, app profiles and
analysis. Reusable App Store/Play Store clients, archive formats, and generic
collection control remain in `scraper_backend/`.

For generic installation and the recommended controller quickstart, start at the
repository [README](../../README.md) and
[collection controller guide](../../docs/collection-control.md). This directory is
for reproducing DatingAppsNLP-specific workflows, not the generic first-run path.
The detailed [collection notes](README-notes.md) describe project-specific plans,
data interpretation and historical runs; check each command's paths and scope
before re-running it.

Research scripts resolve collection data through `DATA_ROOT` (or the generic
OneDrive-backed default). Set `DATA_ROOT` explicitly before running a workflow
that uses external app lists or existing raw archives. Scripts are kept at their
old repository paths as compatibility entry points while this layout is adopted.
