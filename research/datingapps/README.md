# DatingAppsNLP research tooling

This tree contains project-specific collection policies, app profiles and
analysis. Reusable App Store/Play Store clients, archive formats, and generic
collection control remain in `scraper_backend/`.

Research scripts resolve collection data through `DATA_ROOT` (or the generic
OneDrive-backed default). Set `DATA_ROOT` explicitly before running a workflow
that uses external app lists or existing raw archives. Scripts are kept at their
old repository paths as compatibility entry points while this layout is adopted.
