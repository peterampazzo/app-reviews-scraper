"""Run only Tinder with the existing primary and major-market plans."""
import os, sys, json, time, subprocess, fcntl, threading, signal
from pathlib import Path
from datetime import datetime, timezone
from dating_project import atomic_json, summary

root = Path('/Users/user/Library/CloudStorage/OneDrive-TheUniversityofManchester/DatingAppsNLP')
output = root / 'data'
repo = Path(__file__).resolve().parent
lock = (output / '.collection.lock').open('a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
diag = output / 'diagnostics' / (stamp + '-tinder-only')
diag.mkdir(parents=True)
status_path = output / 'collection_status.json'
if status_path.exists():
    (diag / 'previous_collection_status.json').write_bytes(status_path.read_bytes())
profile = json.loads((output / 'apps/dating2026.json').read_text())
env = dict(os.environ, DATA_LOCATION=str(output)+'/', DATA_BUDGET_ROOT=str(output), DATA_BUDGET_BYTES='0', APPLE_SLEEP='10')
state = dict(status='running', pid=os.getpid(), scope='Tinder only', started_at=stamp, stores={})
workers = []
stop_at = os.environ.get('COLLECTION_STOP_AT')
deadline = datetime.fromisoformat(stop_at).timestamp() if stop_at else None
if deadline is not None and deadline <= time.time():
    raise SystemExit('Stop deadline has already passed; no collection started.')
stopping = threading.Event()
def timed_stop():
    stopping.set()
    for _, process, _ in workers:
        if process.poll() is None:
            try:
                process.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass
    print('Scheduled stop requested; waiting for workers to exit.', flush=True)
timer = None
try:
    if os.environ.get('APPLE_WORLDWIDE') == '1':
        gate = repo / '.runtime/apple-http.lock'
        ready = gate.stat().st_mtime + 7200 if gate.exists() else time.time()
        state.update(status='waiting_for_cooldown', apple_resume_after=datetime.fromtimestamp(ready, timezone.utc).isoformat())
        atomic_json(status_path, state)
        print('Apple resumes after '+state['apple_resume_after'], flush=True)
        while time.time() < ready:
            time.sleep(min(30, ready-time.time()))
        state['status'] = 'running'
    for store, appid in [('apple','547702041'), ('google','com.tinder')]:
        if store not in os.environ.get('TINDER_STORES', 'apple,google').split(','):
            continue
        queries = []
        for phase in ('primary','major'):
            for query in json.loads((output / f'plans/core-{phase}-{store}.json').read_text())[appid]:
                if query not in queries: queries.append(query)
        if store == 'apple' and os.environ.get('APPLE_WORLDWIDE') == '1':
            from scraper_backend.constants import APP_STORE_COUNTRIES
            existing = {q['country'] for q in queries}
            queries += [dict(country=cc, language='en-GB') for cc in sorted(APP_STORE_COUNTRIES) if cc not in existing]
            unavailable = set()
            for status_file in (output/'dating2026/raw').glob('*/apple/547702041/*/status.json'):
                previous = json.loads(status_file.read_text())
                if '404' in str(previous.get('error', '')):
                    unavailable.add(status_file.parent.name)
            queries = [q for q in queries if q['country'] not in unavailable]
            state['apple_country_count'] = len(queries)
            state['apple_unavailable_404_skipped'] = sorted(unavailable)
        plan = diag / f'{store}-plan.json'
        atomic_json(plan, {appid: queries})
        logfile = diag / f'{store}.log'
        handle = logfile.open('a')
        command = [sys.executable,'-u','scraper.py','--list',str(output/'apps/dating2026.json'),'--store',store,'--app-ids',appid,'--reviews','--details','--review-count','-1','--refresh','5200','--locale-plan',str(plan)]
        if store == 'apple': command += ['--resume-apple-from','latest']
        process = subprocess.Popen(command,cwd=repo,env=dict(env,LOGS_FILE=f'tinder-{stamp}-{store}'),stdout=handle,stderr=subprocess.STDOUT)
        workers.append((store,process,handle))
        state['stores'][store] = dict(pid=process.pid,log=str(logfile),command=command)
    if deadline is not None:
        state['scheduled_stop_at'] = stop_at
        timer = threading.Timer(max(0, deadline-time.time()), timed_stop)
        timer.daemon = True
        timer.start()
    atomic_json(status_path,state)
    print('Tinder-only collection started: '+str(diag),flush=True)
    while any(process.poll() is None for _,process,_ in workers):
        if stopping.wait(120):
            for _, process, _ in workers:
                process.wait()
            break
        summary(output,profile)
    for store,process,handle in workers:
        handle.close()
        state['stores'][store]['exit_code'] = process.returncode
    state['status'] = 'paused_by_user' if stopping.is_set() else ('finished_with_errors' if any(p.returncode for _,p,_ in workers) else 'complete')
    state['finished_at'] = datetime.now(timezone.utc).isoformat()
    atomic_json(status_path,state)
    summary(output,profile)
finally:
    if timer is not None:
        timer.cancel()
    for _,process,_ in workers:
        if process.poll() is None:
            process.send_signal(__import__('signal').SIGINT)
