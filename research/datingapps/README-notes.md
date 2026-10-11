# Zoe review collection: project reproduction notes

These notes preserve the project-specific collection plan, run history and
reproduction commands. They are not the generic scraper setup guide. For current
generic installation and controller instructions, see the repository
[README](../../README.md) and [controller guide](../../docs/collection-control.md).
Commands below can contact app stores and write research data; review their scope
and `DATA_ROOT` before running.

This reuses https://github.com/peterampazzo/app-reviews-scraper at commit
`fce1a897c52426a5615802e5a654fb0c9b9b8930`. Collection began 2 October 2026.
The original `scraper.py` entry point, configuration, client classes, output directories,
Apple dependency and Google dependency are retained. Similar-app collection was not requested or run.

## Reproduce

### Retry and Surge extension (2 October, afternoon)

The completed initial Apple sweep had 104 completed queries, 37 HTTP 429 failures,
and 34 HTTP 404 failures. The later retry job resumes the 429 queries at their archived
next offsets and rechecks the 404 storefronts once. A 404 is an observed endpoint failure,
not proof that an app will remain permanently unavailable. Existing raw archives are retained.
Offset-based pagination can shift as reviews are posted/edited; a resumed run is not a
transactional snapshot. All earlier observations remain part of the combined raw dataset.

Surge is a separate project under `$DATA_ROOT/surge/`, with Google ID `com.lavendrapp.lavendr`
and Apple ID `709551897`. Both were checked against the stores and identified as Surge;
Apple returned the same bundle ID. It uses the same 175 Apple storefronts and 84 Google
language queries, plus GB English queries. Google completed successfully for Zoe and is
not rerun as part of the Apple retry.

Launch the three independently logged jobs with:

```sh
.venv/bin/python -u continue_collection.py zoe-retry --data-root "$DATA_ROOT"
.venv/bin/python -u continue_collection.py surge-apple --data-root "$DATA_ROOT"
.venv/bin/python -u continue_collection.py surge-google --data-root "$DATA_ROOT"
```

Each job creates `$DATA_ROOT/diagnostics/<timestamp>-<job>/status.json` and `scraper-1.log` (plus a
second Google log for the GB queries). The retry plan is saved in the Zoe job directory.
These commands perform one collection pass; they are not recurring schedules. Each job
automatically rebuilds its project's research CSVs after finishing. Avoid launching a
duplicate of an already-running job. The scripts use POSIX file locks (tested on macOS).

Starting with these jobs, Apple requests across all processes are serialized and separated
by at least ten seconds; the configured Apple page pause is also ten seconds. HTTP retry
backoff remains in place. Earlier runs used the original three-second page pause.
Google retains its three-second pacing. No stored review observations are deleted by resuming.

### Additional Google storefront collection

Following the request to check other Google storefronts, `expand_google_storefronts.py`
adds 29 country settings for both Zoe and Surge: ca, au, nz, ie, it, de, fr, es, pt, br,
mx, ar, nl, be, ch, se, pl, tr, za, in, jp, kr, tw, id, ph, th, vn, my, sg. Each uses
English plus the local-language choices explicitly recorded in the script and job's
`plan.json` (62 country/language queries per app). This is a broader sample of Google
storefronts, not a claim to cover every country or every language in those countries.

```sh
.venv/bin/python -u expand_google_storefronts.py --data-root "$DATA_ROOT"
```

The job runs one Google query sequence at a time with three-second pacing and full
pagination; it must not be duplicated while running. It saves new raw observations in
each app's existing raw directory, then rebuilds both research datasets on completion.
Its `diagnostics/<timestamp>-google-storefronts/` directory contains per-country logs,
progress status, frozen baseline ID sets and `storefront_comparison.csv`. The comparison
counts distinct IDs absent from the full US/GB archive for each query, and separately
counts IDs first encountered during this expansion. Identical ID sets do not establish
that all countries globally are equivalent; repeated countries/languages can overlap.
Additional IDs are relative to an earlier snapshot: newly posted reviews or changing
API results can also explain differences, so these counts do not isolate a country effect.
Query country remains a requested Google filter, never an inferred reviewer location.

Run from this repository directory, using Python 3.9 or later (tested: Python 3.9.6):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python scraper.py --list research/datingapps/configs/zoe.json --store apple --reviews --review-count -1 --refresh 0 --data-root "$DATA_ROOT"
.venv/bin/python scraper.py --list research/datingapps/configs/zoe.json --store google --reviews --review-count -1 --refresh 0 --data-root "$DATA_ROOT"
.venv/bin/python scraper.py --list research/datingapps/configs/zoe.json --store google --reviews --review-count -1 --refresh 0 --countries gb --locales en en_GB --data-root "$DATA_ROOT"
.venv/bin/python prepare_dataset.py --root "$DATA_ROOT/zoe" --output "$DATA_ROOT/zoe/research"
.venv/bin/python -m unittest discover -s tests -v
```

The supplied research app list uses exactly the documented string-ID input schema.
`--review-count -1` means no user-imposed total limit. `--refresh 0` deliberately
requeries existing locale CSVs. Each invocation makes a new immutable raw run folder;
previous raw files are never overwritten. Locale CSVs are convenience exports and may
be overwritten on refresh; the research exports are rebuilt from raw page archives.
To query particular storefronts/languages, use `--locales us gb` for Apple or
`--locales en fr` for Google. `--countries` applies to Google query storefronts.
A nonzero scraper exit status indicates failed queries; successful prior pages remain saved.

## Original workflow tests and changes

The original requirements installed successfully. The misleading `python_version >= "3.9"`
line installed the unrelated `python-version` package; it did not enforce an interpreter
version. This line was removed and dependencies were pinned to the versions actually tested.
The Apple fork is pinned to `7d2fa3dc544404c8182ba6aad5e403a1f1476b01` rather than mutable
`master`. `requirements-lock.txt` also pins transitive dependencies. The fork still requires
requests 2.23.0; no dependency was silently replaced. Google resolved to 1.2.7. `pip check` passed.

Both original commands failed with `TypeError: string indices must be integers` because
the code expected `{id, name}` objects while the README documented string IDs. Input
normalisation now accepts both forms. Original tracebacks are in `diagnostics/`.

A direct original-client test returned 20 Google reviews. Apple's original client returned
zero reviews after HTTP 401: its old HTML meta-tag token extraction returned no token,
and its exception handler concealed the failure as an empty result. Inspection of Apple's
current public website JavaScript identified its `/api/apps/` proxy for the same catalog API.
`CompatibleAppStore` subclasses the existing fork, retaining its identity, parameters and
offset parser. It uses that public proxy, preserves resource IDs and all attributes,
archives pages, and raises retrieval failures instead of silently declaring success.
No private account, authenticated API or App Store Connect access is involved.

The Google public `reviews()` helper also suppresses exceptions. `GoogleClient` therefore
uses the **same installed library's** page fetcher, request format and field specifications,
with an explicit continuation loop and a scoped transport override. Its `len(None)` failure
for a verified null empty-review payload was fixed. Full-run Google dates are converted
from source Unix timestamps to explicit UTC instead of the library's naive local datetimes.
Google page size is the library's supported maximum of 4,500; this reduces request count,
and is not a total-review cap. Apple explicitly rejects page sizes above 20 (HTTP 400);
its original 20-review page size is retained.

Each request has connection/read timeouts, bounded exponential retry delays, and honours
numeric `Retry-After` values. HTTP 429/408/5xx failures retry after at least 10, 20 and 40 seconds.
Normal page and locale pauses are three seconds. Google parse/gateway failures also retry
with backoff. Repeated continuation tokens/offsets and empty pages with continuation are
reported as incomplete rather than silently accepted. There is no parallel traffic within
a platform. Apple and Google were collected in separate processes.

## Scope and meaning of fields

Apple: the original list contained 155 storefronts. The 20 storefronts in
[Apple's documented expansion](https://www.apple.com/newsroom/2020/04/apple-services-now-available-in-more-countries-around-the-world/)
were added, giving 175. Apple's [availability documentation](https://developer.apple.com/help/app-store-connect/manage-your-apps-availability/manage-availability-for-your-app-on-the-app-store)
still describes 175 countries/regions. A storefront existing does not establish that Zoe
or its review API is available there. The full explicit query list is saved in each
`run.json` and `research/collection_manifests.json`.

Google: all 83 original language codes were retained, plus `am` for Amharic. The old `sm`
label incorrectly said Amharic; it is Samoan. The original US query storefront is retained
for the 84-language sweep. A supplementary GB run queries `en` and the user's `en_GB`.
Unsupported or sparsely populated language codes can return empty results or fall back to
another language. Overlapping result sets are retained in raw data and deduplicated by ID.
**A query language is not evidence of the language in which a review was written.**

- `country`: Apple storefront query code, with `country_basis=storefront_query`. It is not
  inferred residence or nationality. Google leaves this empty because its review objects
  do not identify reviewer country. `query_country` preserves the requested `gl` value.
- `language`: source-reported review language only; empty when absent. No language detection,
  translation or country-based language inference is performed. `query_language` preserves
  the requested Google language or Apple's original `en-GB` request parameter. Apple may
  choose its own storefront language in its response; raw response links retain that detail.
- IDs are strings; ratings are 1–5; timestamps are ISO 8601 UTC. Missing values are empty,
  not invented. Apple does not necessarily return an app version; Google does not return titles.
- Developer response body/date and all original library fields are retained. Extra columns
  have `apple_`/`google_` prefixes; nested data uses JSON strings. `source_record_json`
  retains the complete pre-harmonisation parsed record. Raw HTTP bodies retain even fields
  that the original library does not extract.
- `retrieved_at` is request/archive time. For initial runs it is reconstructed from the
  ordered successful HTTP-response metadata, not review date or the local file modification time.

## Files and deduplication

- `data/zoe/raw/<run>/<platform>/<app>/<query>/`: original HTTP response bodies (`*.body`),
  status/URL/header/request-time sidecars (`000001.json`, etc.), parsed page snapshots
  (`page-*.json`) and query completion/error records (`status.json`). HTTP decompression by
  the requests library precedes saving; body contents are otherwise uncleaned.
- `research/zoe_reviews_combined_raw.csv`: one row per collected review observation, including
  overlap across queries, pages and restarted full runs. Failed queries' successful earlier
  pages are included. Finite-count pilot runs are retained in raw storage but excluded here.
- `research/zoe_reviews_deduplicated.csv`: one row per `(platform, app_id, review_id)`.
  Missing IDs are never merged by text. Within an ID group, select greatest review date,
  then latest retrieval time, then source path and row for deterministic ties. This retains
  the most recent observed edit while all versions remain in combined raw. No cross-platform
  or fuzzy matching, text cleaning, rating filtering or date truncation is performed.
- Deduplicated rows also retain `observation_count`, JSON lists of all observed query
  countries/languages and `observed_variants` (distinct full parsed record values).
- `research/query_coverage.csv` lists every planned query in every full-run attempt,
  including interrupted/unattempted parts of superseded runs. `query_coverage_final.csv`
  selects successful attempts where available, otherwise the latest attempt. A query with
  no continuation is complete only with respect to that endpoint, not all reviews ever posted.
- `research/validation.json` contains platform counts, date ranges, rating distributions,
  missing text/IDs, duplicate IDs, developer replies, and represented query locales.
  `SHA256SUMS` identifies the delivered CSVs. Rebuilding from unchanged archives is deterministic
  for the CSVs; the validation generation timestamp naturally changes.

## Limitations and collection outcomes

See the generated `data/zoe/research/RESULTS.md` for final counts, dates, samples, rating
checks and failure summaries, and the coverage CSV for every unretrieved query/page.
During collection, these files are provisional until all planned queries have returned.

Apple's catalog endpoint intermittently returned HTTP 429 `API capacity exceeded`, sometimes
mid-pagination, despite backoff. HTTP 404 is recorded as unavailable, not a zero-review success.
The failed request URL/offset is preserved in error metadata. A tested RSS fallback returned
empty feeds for US/AE/AU even though the catalog had reviews; it was therefore not used as
an authoritative substitute. Larger Apple pages are explicitly forbidden by its API.

Neither public endpoint promises a complete historical archive. Deleted, moderated,
private/unpublished, unavailable-storefront, inaccessible or no-longer-returned reviews
cannot be recovered. Google language/storefront filters can overlap or fall back, and returned
review counts need not match headline rating counts (which include ratings without text).
There is no claim that reviews represent all users, national populations, or all historical reviews.
