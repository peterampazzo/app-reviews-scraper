"""Tinder Google worldwide candidates, with per-country availability checks."""
import os, sys, json, time, signal, subprocess, fcntl
from pathlib import Path
from datetime import datetime, timezone
from scraper_backend.constants import PLAY_STORE_LANGUAGES
from dating_project import atomic_json

repo = Path(__file__).resolve().parent
output = Path('/Users/user/Library/CloudStorage/OneDrive-TheUniversityofManchester/DatingAppsNLP/data')
os.environ.update(DATA_LOCATION=str(output)+'/', DATA_BUDGET_ROOT=str(output), DATA_BUDGET_BYTES='0')
from scraper_backend.clients import GoogleClient
lock = (output/'.tinder-google-worldwide.lock').open('a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
job = output/'diagnostics'/(stamp+'-tinder-google-worldwide')
job.mkdir(parents=True)
source = repo/'tinder-territoryInfo.json'
(job/source.name).write_bytes(source.read_bytes())
territories = json.loads(source.read_text())['supplemental']['territoryInfo']
plan = {}
for country, info in territories.items():
    if len(country)!=2 or not country.isalpha() or country in ('ZZ','EU','UN'): continue
    languages = ['en']
    for language, values in info.get('languagePopulation',{}).items():
        if not (values.get('_officialStatus') or float(values.get('_populationPercent',0))>=10): continue
        base = language.split('_')[0]
        mapped = {'he':'iw','fil':'tl','jv':'jw'}.get(base,base)
        if base=='zh': mapped = 'zh-TW' if country in ('TW','HK','MO') or 'Hant' in language else 'zh-CN'
        if base=='pt': mapped = 'pt-BR' if country=='BR' else 'pt-PT'
        if mapped in PLAY_STORE_LANGUAGES and mapped not in languages: languages.append(mapped)
    plan[country.lower()] = languages
atomic_json(job/'candidate_plan.json',dict(source='Unicode CLDR territoryInfo',rule='English plus scraper-supported official or >=10% population languages; country availability checked before collection',countries=plan))
priority = 'id ph th vn tr pl ar co cl pe tw hk my sg nz ie be ch at pt dk no fi ua ro cz gr sa ae'.split()
order = [c for c in priority if c in plan] + [c for c in sorted(plan) if c not in priority]
state = dict(status='running',pid=os.getpid(),started_at=stamp,candidate_countries=len(plan),candidate_queries=sum(map(len,plan.values())),countries={})
atomic_json(job/'status.json',state)
atomic_json(output/'tinder_google_worldwide_status.json',dict(job=str(job),pid=os.getpid(),status='running'))
print(f'Worldwide Google expansion: {len(plan)} candidate countries, {state["candidate_queries"]} queries. Job: {job}',flush=True)
child = None
try:
    for country in order:
        row = dict(status='checking',languages=plan[country])
        state['countries'][country]=row
        atomic_json(job/'status.json',state)
        try:
            exists = GoogleClient('com.tinder','en',country=country,raw_dir=job/'availability'/country).app_exists()
            row['exists']=exists
            if not exists:
                row['status']='unavailable'
                continue
            qfile=job/f'{country}-plan.json'
            atomic_json(qfile,{'com.tinder':[dict(country=country,language=l) for l in plan[country]]})
            cmd=[sys.executable,'-u','scraper.py','--list',str(output/'apps/dating2026.json'),'--store','google','--app-ids','com.tinder','--reviews','--details','--review-count','-1','--refresh','5200','--locale-plan',str(qfile)]
            with (job/f'{country}.log').open('a') as log:
                child=subprocess.Popen(cmd,cwd=repo,env=dict(os.environ,LOGS_FILE=f'tinder-worldwide-{stamp}'),stdout=log,stderr=subprocess.STDOUT)
                row.update(status='collecting',pid=child.pid)
                atomic_json(job/'status.json',state)
                code=child.wait()
                row.update(status='complete' if code==0 else 'finished_with_errors',exit_code=code)
                child=None
        except Exception as exc:
            row.update(status='error',error=str(exc))
        finally:
            atomic_json(job/'status.json',state)
        time.sleep(3)
    state['status']='finished'
except KeyboardInterrupt:
    state['status']='interrupted'
finally:
    if child is not None and child.poll() is None:
        child.send_signal(signal.SIGINT)
        child.wait()
    atomic_json(job/'status.json',state)
    atomic_json(output/'tinder_google_worldwide_status.json',dict(job=str(job),pid=os.getpid(),status=state['status']))
