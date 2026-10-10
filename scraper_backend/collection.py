"""Small, cooperative supervisor for the existing scraper worker.

No archive parsing or store-specific fetching belongs here.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from uuid import uuid4

from .paths import resolve_data_root

BASE = Path(__file__).resolve().parent.parent
TERMINAL = {'complete', 'failed', 'paused'}


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def load_config(path, data_root_override=None):
    path = Path(path).resolve()
    config = json.loads(path.read_text())
    allowed = {'data_root', 'apps', 'steps', 'refresh_weeks'}
    if set(config) - allowed:
        raise ValueError('Unknown configuration fields: ' + ', '.join(set(config) - allowed))
    config['data_root'] = str(resolve_data_root(
        explicit=data_root_override,
        configured=config.get('data_root'),
        base_dir=path.parent,
    ))
    config['apps'] = str((path.parent / config['apps']).resolve())
    profile = json.loads(Path(config['apps']).read_text())
    if not profile.get('project') or not profile.get('apps'):
        raise ValueError('App list must contain project and apps')
    if not config.get('steps'):
        raise ValueError('At least one explicit collection step is required')
    config['refresh_weeks'] = float(config.get('refresh_weeks', 5200))
    if config['refresh_weeks'] < 0:
        raise ValueError('refresh_weeks must be nonnegative')
    for step in config['steps']:
        if set(step) - {'store', 'app_ids', 'locales', 'countries', 'resume_apple_from'}:
            raise ValueError('Unknown collection step field')
        if step.get('store') not in ('apple', 'google'):
            raise ValueError('Each step requires store apple or google')
        for key in ('app_ids', 'locales'):
            if not isinstance(step.get(key), list) or not step[key]:
                raise ValueError(key + ' must be a nonempty list')
        for key in ('app_ids', 'locales', 'countries'):
            if key in step and (not isinstance(step[key], list) or not step[key] or
                               any(not isinstance(x, str) or not x or any(c.isspace() for c in x)
                                   for x in step[key])):
                raise ValueError(key + ' must contain separate nonempty strings')
        platform = 'ios' if step['store'] == 'apple' else 'android'
        known = {str(x[platform]['id'] if isinstance(x[platform], dict) else x[platform])
                 for x in profile['apps'] if x.get(platform)}
        if set(step['app_ids']) - known:
            raise ValueError('Selected app ID is absent from the input list')
        if step['store'] == 'google' and 'resume_apple_from' in step:
            raise ValueError('Apple resume cannot be used with Google')
        resume = step.get('resume_apple_from')
        if resume and resume != 'latest':
            step['resume_apple_from'] = str((path.parent / resume).resolve())
            if not Path(step['resume_apple_from']).is_dir():
                raise ValueError('Apple resume directory does not exist')
    return config


def command(config, step):
    args = [sys.executable, '-u', str(BASE / 'scraper.py'), '--list', config['apps'],
            '--store', step['store'], '--reviews', '--details', '--review-count', '-1',
            '--refresh', str(config['refresh_weeks']), '--data-root', config['data_root']]
    for key in ('app_ids', 'locales', 'countries'):
        if key in step:
            args += ['--' + key.replace('_', '-')] + step[key]
    if step.get('resume_apple_from'):
        args += ['--resume-apple-from', step['resume_apple_from']]
    return args


def active_collectors():
    # Fail closed if ps is unavailable. A stale JSON status alone is not liveness.
    result = subprocess.run(['ps', '-axo', 'pid=,command='], check=True,
                            capture_output=True, text=True)
    names = ('scraper.py', 'continue_collection.py', 'expand_google_storefronts.py',
             'dating_project.py', 'tinder_collection.py', 'tinder_google_worldwide.py')
    return [line.strip() for line in result.stdout.splitlines()
            if line.strip() and int(line.split(None, 1)[0]) != os.getpid()
            and any(name in line.split(None, 1)[1].split() or
                    any(word.endswith('/' + name) for word in line.split(None, 1)[1].split())
                    for name in names)]


def supervise(config, stop_at=None):
    root = Path(config['data_root'])
    root.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        # Share the existing project/Tinder locks. Older Zoe/Surge launchers do
        # not use these locks; preflight detects them, but must not be launched
        # concurrently by hand.
        for name in ('.collection.lock', '.tinder-google-worldwide.lock'):
            lock = stack.enter_context((root / name).open('a'))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        running = active_collectors()
        if running:
            raise RuntimeError('Collection already running: ' + '; '.join(running))
        pointer = root / 'controller_status.json'
        if pointer.exists() and json.loads(pointer.read_text()).get('status') not in TERMINAL:
            raise RuntimeError('Previous controller has no verified terminal state; inspect before restarting')
        job = root / 'diagnostics' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-controller-' + uuid4().hex[:8])
        job.mkdir(parents=True)
        save(job / 'config.json', config)
        state = dict(status='running', run_id=job.name, pid=os.getpid(), job=str(job), steps=[])
        stopping = []
        handlers = {}
        child = None
        def publish():
            state['updated_at'] = datetime.now(timezone.utc).isoformat()
            save(job / 'status.json', state)
            save(pointer, state)
        def requested():
            return stopping or (job / 'stop.request').exists() or (stop_at is not None and time.time() >= stop_at)
        def halt():
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
                if child.poll() is not None:
                    return
                child.send_signal(sig)
                try:
                    child.wait(timeout=30)
                    return
                except subprocess.TimeoutExpired:
                    state['forced_shutdown'] = True
            raise RuntimeError('Worker did not exit after bounded shutdown')
        try:
            for sig in (signal.SIGINT, signal.SIGTERM):
                handlers[sig] = signal.signal(sig, lambda signum, frame: stopping.append(signum))
            publish()
            for index, step in enumerate(config['steps']):
                if requested():
                    break
                if step['store'] == 'apple':
                    gate = BASE / '.runtime/apple-http.lock'
                    ready = gate.stat().st_mtime + 7200 if gate.exists() else 0
                    while time.time() < ready and not requested():
                        state.update(status='waiting_cooldown', ready_at=ready)
                        publish()
                        time.sleep(1)
                    if requested():
                        break
                env = dict(os.environ, DATA_ROOT=str(root), DATA_LOCATION=str(root) + '/',
                           DATA_BUDGET_ROOT=str(root),
                           DATA_BUDGET_BYTES='0', APPLE_SLEEP='10',
                           LOGS_FILE=str(job / ('worker-%d-internal' % index)))
                args = command(config, step)
                with (job / ('worker-%d.log' % index)).open('x') as log:
                    child = subprocess.Popen(args, cwd=BASE, env=env, stdout=log, stderr=subprocess.STDOUT)
                    record = dict(command=args, pid=child.pid, status='running')
                    state['steps'].append(record)
                    state['status'] = 'running'
                    publish()
                    while child.poll() is None:
                        if requested():
                            state['status'] = 'stopping'
                            publish()
                            halt()
                            break
                        time.sleep(1)
                        publish()
                    record.update(exit_code=child.returncode,
                                  status='paused' if requested() else 'complete' if child.returncode == 0 else 'failed')
                    publish()
                    if child.returncode or requested():
                        break
            state['status'] = 'paused' if requested() else 'failed' if any(s['status'] == 'failed' for s in state['steps']) else 'complete'
        except BaseException as exc:
            state.update(status='failed', error=str(exc))
            raise
        finally:
            try:
                if child is not None and child.poll() is None:
                    halt()
                publish()
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
        return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['collect', 'status', 'stop'])
    parser.add_argument('--config', required=True)
    parser.add_argument('--data-root', help='collection data directory (overrides config and environment)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--stop-at', help='ISO 8601 timestamp with explicit timezone')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config, data_root_override=args.data_root)
        deadline = None
        if args.stop_at:
            date = datetime.fromisoformat(args.stop_at)
            if date.tzinfo is None or date.timestamp() <= time.time():
                raise ValueError('stop-at must be a future timezone-aware timestamp')
            deadline = date.timestamp()
        if args.action == 'collect':
            result = {'commands': [command(config, s) for s in config['steps']]} if args.dry_run else supervise(config, deadline)
        else:
            pointer = Path(config['data_root']) / 'controller_status.json'
            result = json.loads(pointer.read_text()) if pointer.exists() else {'status': 'not_started'}
            if args.action == 'stop' and result['status'] not in TERMINAL | {'not_started'}:
                (Path(result['job']) / 'stop.request').touch(exist_ok=True)
                result = dict(result, stop_requested=True)
            # Report evidence separately; never interpret an old running label as proof.
            result['active_collectors'] = active_collectors()
        print(json.dumps(result, indent=2))
        return 1 if result.get('status') == 'failed' else 0
    except (ValueError, KeyError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(2, str(exc) + '\n')
