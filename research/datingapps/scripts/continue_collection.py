"""Run a named collection lane and refresh its research exports when done.

Each invocation saves an independent job log/status; it does not start a scheduler.
"""
import argparse
import fcntl
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from scraper_backend.constants import APP_STORE_COUNTRIES, PLAY_STORE_LANGUAGES
from scraper_backend.paths import resolve_data_root

BASE = Path(__file__).resolve().parents[3]
APPS = BASE / 'research' / 'datingapps' / 'configs'


def retry_plan(data_root):
    old_apple = Path(data_root) / 'zoe/raw/20261002T075047Z-db68d2f8/apple'
    items = []
    for file in sorted((old_apple / '1269081011').glob('*/status.json')):
        status = json.loads(file.read_text())
        if status.get('status') != 'failed':
            continue
        country = file.parent.name
        kind = '429' if '429' in status.get('error', '') else '404' if '404' in status.get('error', '') else 'other'
        items.append(dict(country=country, error_type=kind, error=status.get('error'),
                          saved_pages=len(list(file.parent.glob('page-*.json')))))
    return sorted(items, key=lambda x: (x['error_type'] != '429', x['country'] not in ('us', 'gb'), x['country']))


def export(project, data_root):
    # Apple and Google may finish separately; serialize writers for each project.
    runtime = BASE / '.runtime'
    runtime.mkdir(exist_ok=True)
    with (runtime / f'{project}-export.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = subprocess.run([sys.executable, str(BASE / 'prepare_dataset.py'),
                         '--root', str(Path(data_root) / project),
                         '--output', str(Path(data_root) / project / 'research')], cwd=BASE,
                                stdout=subprocess.DEVNULL)
        return result.returncode


def main(lane, data_root=None):
    data_root = resolve_data_root(explicit=data_root)
    old_apple = data_root / 'zoe/raw/20261002T075047Z-db68d2f8/apple'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    job = data_root / 'diagnostics' / f'{stamp}-{lane}'
    job.mkdir(parents=True, exist_ok=False)
    status = dict(lane=lane, pid=os.getpid(), started_at=stamp, status='running', steps=[])
    def save():
        temporary = job / 'status.tmp'
        temporary.write_text(json.dumps(status, indent=2))
        temporary.replace(job / 'status.json')
    save()
    common = [sys.executable, '-u', str(BASE / 'scraper.py'), '--reviews', '--review-count', '-1',
              '--refresh', '0', '--data-root', str(data_root)]
    if lane == 'zoe-retry':
        plan = retry_plan(data_root)
        (job / 'retry-plan.json').write_text(json.dumps(plan, indent=2))
        print('Retry types:', dict(Counter(x['error_type'] for x in plan)), flush=True)
        project = 'zoe'
        commands = [common + ['--list', str(APPS / 'zoe.json'), '--store', 'apple',
                    '--resume-apple-from', str(old_apple), '--locales'] + [x['country'] for x in plan]]
    elif lane == 'surge-apple':
        project = 'surge'
        locales = ['gb', 'us'] + [c for c in APP_STORE_COUNTRIES if c not in ('gb', 'us')]
        commands = [common + ['--list', str(APPS / 'surge.json'), '--store', 'apple', '--locales'] + locales]
    else:
        project = 'surge'
        locales = ['en'] + [l for l in PLAY_STORE_LANGUAGES if l != 'en']
        commands = [common + ['--list', str(APPS / 'surge.json'), '--store', 'google', '--locales'] + locales,
                    common + ['--list', str(APPS / 'surge.json'), '--store', 'google',
                              '--countries', 'gb', '--locales', 'en', 'en_GB']]
    try:
        for i, command in enumerate(commands):
            step = dict(command=command, status='running')
            status['steps'].append(step)
            save()
            with (job / f'scraper-{i+1}.log').open('w') as logfile:
                process = subprocess.Popen(command, cwd=BASE, stdout=logfile, stderr=subprocess.STDOUT)
                step['pid'] = process.pid
                save()
                step['exit_code'] = process.wait()
            step['status'] = 'finished'
            save()
        status['export_exit_code'] = export(project, data_root)
        status['status'] = 'finished_with_errors' if status['export_exit_code'] or any(s['exit_code'] for s in status['steps']) else 'complete'
    except BaseException as exc:
        status.update(status='interrupted', error=str(exc))
        raise
    finally:
        status['finished_at'] = datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps(status, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lane', choices=['zoe-retry', 'surge-apple', 'surge-google'])
    main(parser.parse_args().lane)
