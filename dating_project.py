"""DatingAppsNLP input validation and collection orchestration around scraper.py."""
import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
import time
import subprocess
import fcntl
from datetime import datetime, timezone
from pathlib import Path

HOME = {
    'Pairs': 'jp', 'Tapple': 'jp', 'Omiai': 'jp', 'with': 'jp', '9monsters': 'jp',
    'Dine / D3': 'jp', 'Aisle': 'in', 'TrulyMadly': 'in', 'QuackQuack': 'in',
    'Mamba': 'ru', 'Meetic': 'fr', 'Fruitz': 'fr', 'adopte': 'fr',
    'LOVOO': 'de', 'Parship': 'de', 'Meet5': 'de',
    'Tantan': 'cn', 'Soul': 'cn', 'Momo': 'cn',
    'happn': 'fr', 'Timeleft': 'fr', 'Badoo': 'gb', 'Feeld': 'gb', 'Muzz': 'gb',
    'Plenty of Fish': 'ca', 'Breeze': 'nl', 'Inner Circle': 'nl', 'Omi': 'sg',
    'Jaumo': 'de', 'Romeo': 'de',
}
MAJOR = {
    'gb': ['en'], 'ca': ['en', 'fr'], 'au': ['en'], 'de': ['en', 'de'],
    'fr': ['en', 'fr'], 'it': ['en', 'it'], 'es': ['en', 'es'],
    'br': ['en', 'pt-BR'], 'mx': ['en', 'es'], 'in': ['en', 'hi'],
    'jp': ['en', 'ja'], 'kr': ['en', 'ko'], 'nl': ['en', 'nl'],
    'se': ['en', 'sv'], 'za': ['en'],
}
HOME_LANGUAGE = {'cn': 'zh-CN', 'hk': 'zh-TW', 'ru': 'ru', 'sg': 'zh-CN',
                 'jp': 'ja', 'in': 'hi', 'fr': 'fr', 'de': 'de', 'nl': 'nl'}
FIELDS = ['app', 'store', 'id', 'exists', 'country_used', 'error',
          'store_title', 'proposed_id', 'checked_at', 'tier', 'category']


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temporary.replace(path)


def write_csv(path, records, fields=FIELDS):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    temporary.replace(path)


def setup(root):
    source = root / 'dating2026.json'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    output = root / 'data'
    copied = output / 'apps' / 'dating2026.json'
    copied.parent.mkdir(parents=True, exist_ok=True)
    if copied.exists() and copied.read_bytes() != source.read_bytes():
        raise ValueError('Existing copied input differs from source; refusing to overwrite it')
    if not copied.exists():
        shutil.copy2(source, copied)
    os.environ['DATA_LOCATION'] = str(output) + os.sep
    os.environ['APPLE_SLEEP'] = '3'
    os.environ['DATA_BUDGET_ROOT'] = str(output)
    # User authorised exceeding 10 GB; zero disables the collection-size cap.
    os.environ['DATA_BUDGET_BYTES'] = '0'
    profile = json.loads(source.read_text())
    atomic_json(output / 'input_provenance.json', {
        'original': str(source), 'copied_input': str(copied), 'sha256': digest,
        'apps': len(profile['apps']), 'created_at': now(),
        'home_country_overrides': HOME,
        'country_note': 'Specified regional countries plus named local markets; US is the default where no override is specified.',
    })
    (output / 'COLLECTION_NOTES.md').write_text('''# DatingAppsNLP collection

Reviews and app details only, using the existing app-reviews-scraper. The source
dating2026.json is unchanged; data/apps/dating2026.json is a byte-identical copy.
See input_provenance.json for its SHA-256 and coverage_plan.json for locale plans.

Order: core US/home, core major markets, optional US/home, optional major markets.
Apple and Google run in separate processes. Regional Google apps use the requested
home country. Apple starts in US when available, otherwise its validated home market.
Major coverage includes GB, CA, AU, DE, FR, IT, ES, BR, MX, IN, JP, KR, NL, SE, ZA,
plus specified home markets. Google queries use English and selected local languages.
Query country/language describes the request, not the reviewer's residence or an
automatically detected language. Apple requests use the client's en-GB language.

Output: dating2026/{app-store,play-store}/{details,reviews}; page archives and
HTTP responses are retained under dating2026/raw. Developer replies and original
fields remain in the raw pages/CSVs. CSV scrape_date is the query start time;
raw pages and HTTP sidecars also retain retrieval timestamps.

review-count=-1 follows pagination until the store stops providing results. It
does not guarantee every historical review is publicly exposed. Failed and partial
queries are reported, never labelled exhausted. Completed locale CSVs, including
empty ones, are skipped for 5200 weeks on reruns; partial archives are retained.
An interrupted unfinished locale is fetched again on rerun.

scrape_summary.csv has 122 app/store rows and refreshes during collection. Review
counts deduplicate review IDs within each app/store across raw pages, including
partial queries. raw_review_observations includes repeats. The original exports
are not deduplicated. ID failures and absent platform IDs remain in id_check.csv.

Apple uses a 3-second page sleep plus a shared 10-second request gate; Google uses
a 3-second page sleep. Requests retry transient failures with exponential backoff.
The user authorised exceeding 10 GB on 4 October 2026. The collection-size cap
is disabled (DATA_BUDGET_BYTES=0); storage usage continues to be reported.
No data is published or uploaded by the scraper; the project folder is OneDrive-synced.
''')
    return output, profile, digest


def check(root):
    output, profile, digest = setup(root)
    from scraper_backend.clients import AppleClient, GoogleClient
    rows = []
    # Successful checks can be reused within this validation attempt after an interruption.
    previous = output / 'id_check.csv'
    cached = {}
    if previous.exists():
        with previous.open(newline='') as handle:
            cached = {(r['app'], r['store'], r['id'], r['country_used']): r for r in csv.DictReader(handle)
                if r['exists'] in ('True', 'False')}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    ordered = sorted(profile['apps'], key=lambda a: a['tier'] != 'core')
    for index, app in enumerate(ordered):
        home = HOME.get(app['app'], 'us')
        for store, key in [('google', 'android'), ('apple', 'ios')]:
            spec = app.get(key)
            identifier = str(spec['id']) if spec else ''
            if store == 'google':
                # Google Play has no mainland-China storefront; probe US then HK for these IDs.
                countries = [home] if home != 'cn' else ['us', 'hk']
            else:
                countries = list(dict.fromkeys(['us', home]))
            if not spec:
                countries = [countries[0]]
            for country in countries:
                cache_key = (app['app'], store, identifier, country)
                if cache_key in cached:
                    rows.append(cached[cache_key])
                    continue
                row = dict(app=app['app'], store=store, id=identifier, exists='', country_used=country,
                           error='', store_title='', proposed_id='', checked_at=now(),
                           tier=app['tier'], category=app['category'])
                if not spec:
                    row.update(exists=False, error='No ID supplied for this platform')
                else:
                    raw = output / 'id_checks' / stamp / store / f'{identifier}-{country}'
                    try:
                        client = (GoogleClient(identifier, 'en', raw_dir=raw, country=country) if store == 'google'
                                  else AppleClient(spec.get('name', identifier), identifier, country, raw_dir=raw))
                        row['exists'] = client.app_exists()
                        if row['exists']:
                            if store == 'google':
                                details = client.details
                                row['store_title'] = details.get('title', '')
                                path = output / 'dating2026/play-store/details' / identifier.replace('.', '-') / f'{country}-en.json'
                            else:
                                time.sleep(3)
                                details = client.get_details()
                                row['store_title'] = ' | '.join(r.get('trackName', '') for r in details)
                                if not details:
                                    row['error'] = 'App page exists, but lookup returned no metadata; review availability unconfirmed'
                                path = output / 'dating2026/app-store/details' / identifier / f'{country}.json'
                            atomic_json(path, details)
                        else:
                            row['error'] = 'Store returned not found for this ID/country'
                    except Exception as exc:
                        row['error'] = f'{type(exc).__name__}: {exc}'
                    finally:
                        time.sleep(3)
                rows.append(row)
                write_csv(output / 'id_check.csv', rows)
                atomic_json(output / 'id_check_progress.json', dict(status='running', current_app=app['app'],
                            completed_apps=index, total_apps=len(ordered), rows=len(rows), updated_at=now()))
        print(f'ID checks {index+1}/{len(ordered)}: {app["app"]}', flush=True)
    write_csv(output / 'id_check.csv', rows)
    choices = {}
    for row in rows:
        if row['store']=='google' and str(row['exists'])=='True':
            choices.setdefault(row['id'], row['country_used'])
    atomic_json(output / 'play_countries.json', choices)
    atomic_json(output / 'id_check_complete.json', dict(status='complete', input_sha256=digest,
                rows=len(rows), completed_at=now(), valid_google_ids=len(choices)))
    atomic_json(output / 'id_check_progress.json', dict(status='complete', completed_apps=len(ordered),
                total_apps=len(ordered), rows=len(rows), updated_at=now()))
    print(f'Finished ID validation: {len(rows)} country-specific checks; {len(choices)} usable Google IDs.', flush=True)


def make_plans(output, profile):
    with (output / 'id_check.csv').open(newline='') as handle:
        checks = list(csv.DictReader(handle))
    valid = {(r['store'], r['id'], r['country_used']) for r in checks if r['exists']=='True'}
    invalid = {(r['store'], r['id'], r['country_used']) for r in checks if r['exists']=='False'}
    play = json.loads((output / 'play_countries.json').read_text())
    plans = {(tier, phase, store): {} for tier in ('core', 'optional')
             for phase in ('primary', 'major') for store in ('apple', 'google')}
    for app in profile['apps']:
        home = HOME.get(app['app'], 'us')
        for store, key in [('google', 'android'), ('apple', 'ios')]:
            spec = app.get(key)
            if not spec:
                continue
            identifier = str(spec['id'])
            if store=='google':
                primary = play.get(identifier)
            else:
                primary = next((c for c in dict.fromkeys(['us', home]) if (store,identifier,c) in valid), None)
            if not primary:
                continue
            plans[(app['tier'], 'primary', store)][identifier] = [dict(country=primary, language='en')]
            markets = dict(MAJOR)
            if home != 'us':
                markets.setdefault('hk' if store=='google' and home=='cn' else home,
                                   ['en', HOME_LANGUAGE.get(home, 'en')])
            queries = []
            for country, languages in markets.items():
                if (store, identifier, country) in invalid:
                    continue
                for language in dict.fromkeys(languages if store=='google' else ['en-GB']):
                    if country==primary and (store=='apple' or language=='en'):
                        continue
                    queries.append(dict(country=country, language=language))
            plans[(app['tier'], 'major', store)][identifier] = queries
    for (tier, phase, store), plan in plans.items():
        atomic_json(output / 'plans' / f'{tier}-{phase}-{store}.json', plan)
    atomic_json(output / 'coverage_plan.json', {
        'primary': 'US first; validated regional/home storefront where specified or US unavailable',
        'major_markets': MAJOR, 'home_country_overrides': HOME,
        'stage_order': ['core-primary', 'core-major', 'optional-primary', 'optional-major'],
        'queries': {'-'.join(key): sum(map(len, value.values())) for key,value in plans.items()},
        'refresh_weeks': 5200, 'review_count': -1, 'storage_pause_bytes': 0,
    })
    return plans


def summary(output, profile):
    """Count distinct review IDs across raw pages, including saved partial queries."""
    from collections import defaultdict
    from scraper_backend.storage import storage_bytes
    with (output / 'id_check.csv').open(newline='') as handle:
        checks = list(csv.DictReader(handle))
    errors = defaultdict(set)
    validated = set()
    for row in checks:
        if row['exists']=='True':
            validated.add((row['store'], row['id']))
        if row['error']:
            errors[(row['store'], row['id'])].add(f"ID check {row['country_used']}: {row['error']}")
    folders = defaultdict(list)
    for manifest in (output / 'dating2026/raw').glob('*/*/run.json'):
        try:
            run = json.loads(manifest.read_text())
        except json.JSONDecodeError:
            continue
        for query in run['queries']:
            locale = query['locale'] if run['platform']=='apple' else f"{query['country']}-{query['locale']}"
            folders[(run['platform'],query['app_id'])].append((manifest.parent/query['app_id']/locale, query))
    result = []
    for app in profile['apps']:
        for store, key in [('apple','ios'),('google','android')]:
            identifier = str(app[key]['id']) if app.get(key) else ''
            ids, countries, languages, raw_count, earliest, latest = set(), set(), set(), 0, None, None
            complete, failed = set(), set()
            for folder, query in folders[(store,identifier)]:
                query_key = (query['country'], query['locale'])
                status_path = folder/'status.json'
                if status_path.exists():
                    try:
                        status = json.loads(status_path.read_text())
                    except json.JSONDecodeError:
                        status = {}
                    if status.get('status') in ('complete','skipped_fresh'):
                        complete.add(query_key)
                    elif status.get('status') in ('failed','paused_storage'):
                        failed.add(query_key)
                    for error in ('error','details_error'):
                        if status.get(error):
                            errors[(store,identifier)].add(f"{query_key}: {status[error]}")
                for page in sorted(folder.glob('page-*.json')):
                    try:
                        records = json.loads(page.read_text())['records']
                    except json.JSONDecodeError:
                        continue  # Current page may still be written; next summary catches it.
                    for index, review in enumerate(records):
                        raw_count += 1
                        ids.add(review.get('reviewId') or f'{page}:{index}')
                        countries.add(query['country'])
                        if store=='google':
                            languages.add(query['locale'])
                        value = review.get('date' if store=='apple' else 'at')
                        if value:
                            try:
                                date = datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
                                earliest = date if earliest is None else min(earliest,date)
                                latest = date if latest is None else max(latest,date)
                            except (ValueError,TypeError):
                                errors[(store,identifier)].add(f'Unparseable review date in {page.name}')
            result.append(dict(app=app['app'], store=store, id=identifier, tier=app['tier'], category=app['category'],
                number_of_reviews=len(ids), raw_review_observations=raw_count,
                earliest_review_date=earliest.isoformat() if earliest else '',
                latest_review_date=latest.isoformat() if latest else '',
                locales_with_reviews=len(countries if store=='apple' else languages),
                locale_type='query_country' if store=='apple' else 'query_language',
                countries_with_reviews=len(countries), languages_with_reviews=len(languages),
                completed_queries=len(complete), failed_queries=len(failed-complete),
                id_check_status='not_supplied' if not identifier else 'available' if (store,identifier) in validated else 'failed_or_unknown',
                errors=' | '.join(sorted(errors[(store,identifier)])), summary_date=now()))
    write_csv(output/'scrape_summary.csv', result, list(result[0]))
    atomic_json(output/'storage_usage.json', dict(bytes=storage_bytes(output), pause_threshold_bytes=0, checked_at=now()))


def collect(root):
    output, profile, digest = setup(root)
    with (output/'.collection.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = dict(status='waiting_for_id_checks', pid=os.getpid(), started_at=now(), stages=[])
        atomic_json(output/'collection_status.json', state)
        while not (output/'id_check_complete.json').exists():
            time.sleep(5)
        completed = json.loads((output/'id_check_complete.json').read_text())
        if completed['input_sha256'] != digest:
            raise ValueError('Completed ID checks do not match the copied input')
        plans = make_plans(output, profile)
        summary(output, profile)
        print('ID validation finished. Starting core apps, US/home first.', flush=True)
        for tier in ('core','optional'):
            for phase in ('primary','major'):
                if (output/'storage_pause.json').exists():
                    break
                stage = dict(tier=tier, phase=phase, status='running', started_at=now(), stores={})
                state.update(status='running')
                state['stages'].append(stage)
                workers = []
                for store in ('apple','google'):
                    plan = plans[(tier,phase,store)]
                    if not any(plan.values()):
                        continue
                    logfile = output/f'{tier}-{phase}-{store}.log'
                    command = [sys.executable, '-u', 'scraper.py', '--list', str(output/'apps/dating2026.json'),
                        '--store', store, '--tier', tier, '--reviews', '--details', '--review-count', '-1',
                        '--refresh', '5200', '--locale-plan', str(output/'plans'/f'{tier}-{phase}-{store}.json'),
                        '--country-map', str(output/'play_countries.json')]
                    if store == 'apple':
                        command += ['--resume-apple-from', 'latest']
                    environment = dict(os.environ, LOGS_FILE=f'dating2026-{store}', APPLE_SLEEP='3')
                    handle = logfile.open('a')
                    process = subprocess.Popen(command, cwd=Path(__file__).resolve().parent,
                                               env=environment, stdout=handle, stderr=subprocess.STDOUT)
                    workers.append((store,process,handle))
                    stage['stores'][store] = dict(pid=process.pid, command=command, log=str(logfile))
                atomic_json(output/'collection_status.json', state)
                next_summary = time.monotonic()+120
                while any(process.poll() is None for _,process,_ in workers):
                    time.sleep(5)
                    if time.monotonic() >= next_summary:
                        summary(output, profile)
                        next_summary = time.monotonic()+120
                for store,process,handle in workers:
                    handle.close()
                    stage['stores'][store]['exit_code'] = process.returncode
                stage.update(status='finished', finished_at=now())
                atomic_json(output/'collection_status.json', state)
                summary(output, profile)
            if (output/'storage_pause.json').exists():
                break
        state.update(status='paused_storage' if (output/'storage_pause.json').exists() else
                     'finished_with_errors' if any(s.get('exit_code',0) for stage in state['stages'] for s in stage['stores'].values()) else 'complete',
                     finished_at=now())
        atomic_json(output/'collection_status.json', state)
        summary(output, profile)
        print(f'Collection {state["status"]}. See {output / "scrape_summary.csv"}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['check', 'collect', 'summary'])
    parser.add_argument('--project-root', type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.phase=='check':
        check(arguments.project_root)
    elif arguments.phase=='collect':
        collect(arguments.project_root)
    else:
        output, profile, _ = setup(arguments.project_root)
        summary(output, profile)
