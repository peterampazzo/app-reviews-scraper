"""Read-only raw audit and timestamped, unique-ID Tinder CSV snapshots."""
import csv, hashlib, json, time
from datetime import datetime, timezone
from collections import Counter, defaultdict
from prepare_dataset import normalise, FIELDS
from scraper_backend.paths import resolve_data_root

root = resolve_data_root()
cutoff = time.time() - 5
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
out = root / 'dating2026/research' / ('tinder-' + stamp)
out.mkdir(parents=True, exist_ok=False)
report = dict(snapshot_cutoff_epoch=cutoff, scope='Tinder only, both platforms',
              rule='One row per platform/app/review ID; latest retrieved observation, then source path and row. Missing IDs retained individually.',
              raw_files_modified_by_exporter=False, platforms={})
with (out/'source_manifest.csv').open('w', newline='') as manifest:
    mw=csv.writer(manifest);mw.writerow(['path','bytes','mtime_ns','sha256'])
    for platform, appid in [('apple','547702041'),('google','com.tinder')]:
        paths=sorted(p for p in (root/'dating2026/raw').glob(f'*/{platform}/{appid}/*/page-*.json')
                     if p.stat().st_mtime < cutoff and ' ' not in p.parent.name)
        chosen={}; observations=0; missing_ids=0; bad=[]; attrs=set(); stats=[]
        locales=Counter(); pages_meta=[]
        for fi,p in enumerate(paths):
            st=p.stat(); blob=p.read_bytes()
            try:
                page=json.loads(blob); records=page['records']
            except Exception as exc:
                bad.append(dict(path=str(p),error=str(exc)));continue
            mw.writerow([str(p),st.st_size,st.st_mtime_ns,hashlib.sha256(blob).hexdigest()])
            stats.append((p,st.st_size,st.st_mtime_ns))
            retrieved=page.get('retrieved_at','')
            pages_meta.append((fi,retrieved))
            for ri,r in enumerate(records):
                observations+=1;locales[p.parent.name]+=1;attrs.update(r)
                rid=r.get('reviewId')
                if not rid: missing_ids+=1
                key=str(rid) if rid else f'__missing__:{fi}:{ri}'
                old=chosen.get(key)
                # Keep source pointers instead of retaining millions of full records.
                if old is None: chosen[key]=(retrieved,fi,ri,1)
                elif (retrieved,fi,ri) >= old[:3]: chosen[key]=(retrieved,fi,ri,old[3]+1)
                else: chosen[key]=(old[0],old[1],old[2],old[3]+1)
            if fi%500==0: print(platform,'scanned',fi,'/',len(paths),'unique',len(chosen),flush=True)
        byfile=defaultdict(dict)
        for rid,(_,fi,ri,count) in chosen.items():byfile[fi][ri]=(rid,count)
        fields=FIELDS+['observation_count']+[platform+'_'+k for k in sorted(attrs)]
        dest=out/f'tinder_{platform}_reviews_deduplicated.csv'
        missing=Counter(); n=0; dates=[]; exported=set()
        with dest.open('w',newline='') as h:
            writer=csv.DictWriter(h,fieldnames=fields,extrasaction='ignore');writer.writeheader()
            for fi,selection in sorted(byfile.items()):
                p=paths[fi];page=json.loads(p.read_text());locale=p.parent.name
                country=locale if platform=='apple' else locale.split('-',1)[0]
                language='en-GB' if platform=='apple' else locale.split('-',1)[1]
                for ri,(key,count) in sorted(selection.items()):
                    record=page['records'][ri]
                    row=normalise(record,platform,appid,country,language,p,ri,page.get('retrieved_at',''),p.parents[3].name)
                    row['observation_count']=count;writer.writerow(row);exported.add(key);n+=1
                    if not row.get('review'):missing['text']+=1
                    if row.get('rating') is None:missing['rating']+=1
                    if row.get('review_date'):dates.append(row['review_date'])
        changed=[str(p) for p,size,mtime in stats if not p.exists() or p.stat().st_size!=size or p.stat().st_mtime_ns!=mtime]
        # Independently re-read the actual written CSV, validating its IDs.
        csv_keys=set();duplicates=0;csv_rows=0
        with dest.open(newline='') as h:
            for r in csv.DictReader(h):
                csv_rows+=1
                key=r['review_id'] or (r['source_file']+':'+r['source_row'])
                if key in csv_keys:duplicates+=1
                csv_keys.add(key)
        expected={key for key in chosen if not key.startswith('__missing__:')}
        csv_ids={key for key in csv_keys if key in expected}
        valid=(not bad and not changed and duplicates==0 and csv_rows==len(chosen) and csv_ids==expected and exported==set(chosen))
        report['platforms'][platform]=dict(validated=valid,raw_pages=len(stats),observations=observations,
            unique_exported_rows=n,repeated_id_observations=observations-n,missing_ids=missing_ids,
            missing_text=missing['text'],missing_ratings=missing['rating'],earliest_date=min(dates) if dates else None,
            latest_date=max(dates) if dates else None,duplicate_csv_keys=duplicates,raw_export_id_sets_equal=csv_ids==expected,
            unreadable_pages=bad,changed_source_files=changed,query_observations=dict(locales))
        print('VALIDATION',platform,json.dumps({k:v for k,v in report['platforms'][platform].items() if k!='query_observations'}),flush=True)
        del chosen,byfile,exported,csv_keys,expected,csv_ids
(out/'validation.json').write_text(json.dumps(report,indent=2))
(out/'README.md').write_text('Tinder review snapshot\n\nRaw archives and previous exports are untouched. Each CSV contains one row per review ID within its platform. The latest retrieved observation is retained, including original fields, developer replies, and source_record_json. Other versions remain in raw archives. observation_count records repeated sightings. Query country/language is not reviewer residence or detected text language.\n\nSources are frozen by the timestamp cutoff in validation.json; collection can continue afterward. source_manifest.csv records SHA-256 hashes of every source page read. Missing IDs, if any, are kept as separate rows. Validation independently rereads the CSV and compares its ID set with the source pages.\n')
with (out/'SHA256SUMS').open('w') as h:
    for p in sorted(out.iterdir()):
        if p.name=='SHA256SUMS':continue
        digest=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
        h.write(digest.hexdigest()+'  '+p.name+'\n')
print('OUTPUT',out,flush=True)
if not all(x['validated'] for x in report['platforms'].values()):raise SystemExit('Validation failed; inspect validation.json')
