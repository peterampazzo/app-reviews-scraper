"""Collect additional Google storefronts using the existing scraper and archive format."""
import csv
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from research.datingapps.scripts.continue_collection import BASE, export
from scraper_backend.paths import resolve_data_root

# Explicit research coverage plan, not a claim to cover every Google storefront.
# Include English and selected local query languages; no reviewer language is inferred.
STOREFRONTS = {
    'ca': ['en', 'fr'], 'au': ['en'], 'nz': ['en'], 'ie': ['en'],
    'it': ['en', 'it'], 'de': ['en', 'de'], 'fr': ['en', 'fr'],
    'es': ['en', 'es'], 'pt': ['en', 'pt-PT'], 'br': ['en', 'pt-BR'],
    'mx': ['en', 'es'], 'ar': ['en', 'es'], 'nl': ['en', 'nl'],
    'be': ['en', 'fr', 'nl', 'de'], 'ch': ['en', 'de', 'fr', 'it'],
    'se': ['en', 'sv'], 'pl': ['en', 'pl'], 'tr': ['en', 'tr'],
    'za': ['en', 'af'], 'in': ['en', 'hi', 'bn', 'ta', 'te'],
    'jp': ['en', 'ja'], 'kr': ['en', 'ko'], 'tw': ['en', 'zh-TW'],
    'id': ['en', 'id'], 'ph': ['en', 'tl'], 'th': ['en', 'th'],
    'vn': ['en', 'vi'], 'my': ['en', 'ms'], 'sg': ['en', 'zh-CN'],
}
PROJECTS = {'zoe': 'com.surgeapp.zoe', 'surge': 'com.lavendrapp.lavendr'}


def read_json(path):
    return json.loads(path.read_text())


def baseline_ids(project, data_root):
    """Freeze original US/GB IDs from full-run raw pages, excluding finite pilots."""
    identifiers = set()
    for manifest in sorted((data_root / project / 'raw').glob('*/google/run.json')):
        if read_json(manifest)['review_count'] != sys.maxsize:
            continue
        for folder in (manifest.parent / PROJECTS[project]).glob('*'):
            if folder.name.split('-', 1)[0] not in ('us', 'gb'):
                continue
            for page in folder.glob('page-*.json'):
                identifiers.update(r['reviewId'] for r in read_json(page)['records'] if r.get('reviewId'))
    return identifiers


def save_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


def main(data_root=None):
    data_root = resolve_data_root(explicit=data_root)
    runtime = BASE / '.runtime'
    runtime.mkdir(exist_ok=True)
    with (runtime / 'google-expansion.lock').open('a') as lock:
        # Avoid duplicate expansion jobs; only one Google expansion requests at a time.
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        collect(data_root)


def collect(data_root):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    job = data_root / 'diagnostics' / f'{stamp}-google-storefronts'
    job.mkdir(parents=True)
    state = dict(status='running', pid=os.getpid(), started_at=stamp, steps=[])
    save_json(job / 'plan.json', dict(storefronts=STOREFRONTS, projects=PROJECTS,
                                    review_count=-1, page_sleep_seconds=3))
    save_json(job / 'status.json', state)
    baseline = {project: baseline_ids(project, data_root) for project in PROJECTS}
    seen = {project: set(ids) for project, ids in baseline.items()}
    for project, ids in baseline.items():
        save_json(job / f'{project}-us-gb-baseline-ids.json', sorted(ids))
    report = []
    print(f'Checking {len(STOREFRONTS)} additional storefronts for both apps.', flush=True)
    print('US/GB baseline unique IDs:', {p: len(ids) for p, ids in baseline.items()}, flush=True)
    try:
        for country, languages in STOREFRONTS.items():
            for project, app_id in PROJECTS.items():
                raw_root = data_root / project / 'raw'
                previous = set(raw_root.glob('*/google/run.json'))
                command = [sys.executable, '-u', str(BASE / 'scraper.py'),
                           '--list', str(BASE / 'research' / 'datingapps' / 'configs' / f'{project}.json'),
                           '--store', 'google', '--reviews', '--review-count', '-1', '--refresh', '0',
                           '--data-root', str(data_root), '--countries', country, '--locales'] + languages
                step = dict(project=project, country=country, languages=languages,
                            status='running', command=command)
                state['steps'].append(step)
                save_json(job / 'status.json', state)
                with (job / f'{project}-{country}.log').open('w') as logfile:
                    process = subprocess.Popen(command, cwd=BASE, stdout=logfile, stderr=subprocess.STDOUT)
                    step['pid'] = process.pid
                    save_json(job / 'status.json', state)
                    step['exit_code'] = process.wait()
                step['status'] = 'finished'
                manifests = sorted(set(raw_root.glob('*/google/run.json')) - previous)
                if len(manifests) != 1:
                    raise RuntimeError(f'Expected one new run for {project}/{country}, found {len(manifests)}')
                manifest = manifests[0]
                for language in languages:
                    folder = manifest.parent / app_id / f'{country}-{language}'
                    ids, rows = set(), 0
                    for page in folder.glob('page-*.json'):
                        records = read_json(page)['records']
                        rows += len(records)
                        ids.update(r['reviewId'] for r in records if r.get('reviewId'))
                    status_file = folder / 'status.json'
                    query = read_json(status_file) if status_file.exists() else {'status': 'not_finished'}
                    report.append(dict(project=project, query_country=country, query_language=language,
                        status=query.get('status', 'interrupted'), error=query.get('error', ''),
                        raw_rows=rows, unique_ids=len(ids), new_ids_vs_us_gb=len(ids-baseline[project]),
                        first_seen_in_expansion=len(ids-seen[project]),
                        source_directory=str(folder.relative_to(data_root))))
                    seen[project].update(ids)
                with (job / 'storefront_comparison.csv').open('w', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=list(report[0]))
                    writer.writeheader()
                    writer.writerows(report)
                save_json(job / 'summary.json', {
                    'status': 'running', 'completed_steps': len(state['steps']),
                    'us_gb_baseline_ids': {p: len(ids) for p, ids in baseline.items()},
                    'additional_unique_ids': {p: len(seen[p]-baseline[p]) for p in PROJECTS},
                })
                save_json(job / 'status.json', state)
                print(f'{project} {country}: finished (exit {step["exit_code"]}); new IDs so far = {len(seen[project]-baseline[project])}', flush=True)
        state['export_exit_codes'] = {project: export(project, data_root) for project in PROJECTS}
        state['status'] = 'finished_with_errors' if any(s['exit_code'] for s in state['steps']) or any(state['export_exit_codes'].values()) else 'complete'
    except BaseException as exc:
        state.update(status='interrupted', error=str(exc))
        raise
    finally:
        state['finished_at'] = datetime.now(timezone.utc).isoformat()
        save_json(job / 'status.json', state)
        save_json(job / 'summary.json', {
            'status': state['status'], 'completed_steps': sum(s['status']=='finished' for s in state['steps']),
            'us_gb_baseline_ids': {p: len(ids) for p, ids in baseline.items()},
            'additional_unique_ids': {p: len(seen[p]-baseline[p]) for p in PROJECTS},
        })


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root')
    main(parser.parse_args().data_root)
