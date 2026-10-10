"""Build auditable CSVs from archived pages; never modifies raw collection files."""
import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ['platform', 'app_id', 'country', 'language', 'review_id', 'author', 'rating',
          'title', 'review', 'review_date', 'app_version', 'developer_reply',
          'developer_reply_date', 'query_country', 'query_language', 'country_basis',
          'retrieved_at', 'run_id', 'source_file', 'source_row', 'source_record_json']


def read_json(path):
    """A downloader may still be writing a newly created archive file."""
    for attempt in range(5):
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            if attempt == 4:
                raise
            time.sleep(1)


def scalar(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def normalise(record, platform, app_id, country, locale, source, index, retrieved, run_id):
    apple = platform == 'apple'
    reply = record.get('developerResponse') or {}
    row = dict(platform=platform, app_id=app_id,
               country=country if apple else record.get('country'),
               language=record.get('language'), review_id=record.get('reviewId'),
               author=record.get('userName'), rating=record.get('rating' if apple else 'score'),
               title=record.get('title'), review=record.get('review' if apple else 'content'),
               review_date=record.get('date' if apple else 'at'),
               app_version=record.get('appVersion') or record.get('reviewCreatedVersion'),
               developer_reply=reply.get('body') if apple else record.get('replyContent'),
               developer_reply_date=(reply.get('modified') or reply.get('date')) if apple else record.get('repliedAt'),
               query_country=country, query_language='en-GB' if apple else locale,
               country_basis='storefront_query' if apple else 'not_returned',
               retrieved_at=retrieved, run_id=run_id, source_file=str(source), source_row=index,
               source_record_json=json.dumps(record, ensure_ascii=False, sort_keys=True))
    row.update({platform + '_' + key: scalar(value) for key, value in record.items()})
    return row


def deduplicate(rows):
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        # Missing IDs remain separate; no potentially destructive text-only matching.
        key = (row['platform'], row['app_id'], str(row['review_id'])) if row.get('review_id') else ('missing_id', i)
        groups[key].append(row)
    result = []
    for observations in groups.values():
        def order(row):
            value = row.get('review_date') or ''
            date = datetime.fromisoformat(value.replace('Z', '+00:00')) if value else datetime.min.replace(tzinfo=timezone.utc)
            if date.tzinfo is None:
                raise ValueError(f'Naive date in full-run record: {row["source_file"]}')
            return date, row['retrieved_at'], row['source_file'], row['source_row']
        row = dict(max(observations, key=order))
        row['observation_count'] = len(observations)
        row['observed_query_countries'] = json.dumps(sorted({r['query_country'] for r in observations}))
        row['observed_query_languages'] = json.dumps(sorted({r['query_language'] for r in observations}))
        row['observed_variants'] = len({r['source_record_json'] for r in observations})
        result.append(row)
    return sorted(result, key=lambda r: (r['platform'], r.get('review_date') or '', str(r.get('review_id'))))


def write_csv(path, rows, fields=None):
    columns = fields or FIELDS + sorted(set().union(*(r.keys() for r in rows)) - set(FIELDS))
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='raise')
        writer.writeheader()
        writer.writerows(rows)


def statistics(rows):
    stats = {}
    for platform in ('apple', 'google'):
        selected = [r for r in rows if r['platform'] == platform]
        ids = [str(r['review_id']) for r in selected if r.get('review_id')]
        dates = [r['review_date'] for r in selected if r.get('review_date')]
        stats[platform] = dict(rows=len(selected), unique_review_ids=len(set(ids)),
            duplicate_id_rows=len(ids) - len(set(ids)), missing_ids=len(selected)-len(ids),
            earliest=min(dates, default=None), latest=max(dates, default=None),
            ratings=dict(sorted(Counter(str(r['rating']) for r in selected).items())),
            missing_review_text=sum(not (r.get('review') or '').strip() for r in selected),
            query_countries=sorted({r['query_country'] for r in selected}),
            query_languages=sorted({r['query_language'] for r in selected}),
            source_languages=sorted({r['language'] for r in selected if r.get('language')}),
            developer_replies=sum(bool(r.get('developer_reply')) for r in selected))
    return stats


def write_report(output, summary, unique, coverage, project='zoe'):
    lines = [f'# {project.title()} collection results', '', 'Generated: ' + summary['generated_at'], '',
             'These counts describe the archived observations available at generation time. '
             'See `query_coverage_final.csv` for completed, failed and unattempted queries.', '',
             '| Platform | Raw observations | Deduplicated reviews | Earliest UTC | Latest UTC |',
             '|---|---:|---:|---|---|']
    for platform in ('apple', 'google'):
        raw, clean = summary['raw'][platform], summary['deduplicated'][platform]
        lines.append(f"| {platform} | {raw['rows']:,} | {clean['rows']:,} | {clean['earliest']} | {clean['latest']} |")
    lines += ['', '## Validation', '', '| Check (deduplicated) | Apple | Google |', '|---|---:|---:|']
    for key, label in [('missing_review_text','Missing review text'),('missing_ids','Missing IDs'),
                       ('duplicate_id_rows','Duplicate ID rows'),('developer_replies','Developer replies')]:
        lines.append(f"| {label} | {summary['deduplicated']['apple'][key]:,} | {summary['deduplicated']['google'][key]:,} |")
    for key, label in [('query_countries','Query storefronts represented by observations'),
                       ('query_languages','Query languages represented by observations'),
                       ('source_languages','Source-reported review languages')]:
        # Deduplication can select only one observation; count all observed query provenance.
        lines.append(f"| {label} | {len(summary['raw']['apple'][key])} | {len(summary['raw']['google'][key])} |")
    lines += ['', '## Rating distribution (deduplicated)', '', '| Stars | Apple | Google |', '|---|---:|---:|']
    for rating in range(1,6):
        lines.append(f"| {rating} | {summary['deduplicated']['apple']['ratings'].get(str(rating), 0):,} | {summary['deduplicated']['google']['ratings'].get(str(rating), 0):,} |")
    lines += ['', '## Query coverage', '', '| Platform | Complete | Failed | Active / interrupted | Not attempted |', '|---|---:|---:|---:|---:|']
    for platform in ('apple','google'):
        states = Counter(r['status'] for r in coverage if r['platform']==platform)
        active = states['interrupted'] + states['in_progress_or_interrupted']
        lines.append(f"| {platform} | {states['complete']} | {states['failed']} | {active} | {states['not_attempted']} |")
    errors = Counter('HTTP 404' if '404' in r['error'] else 'HTTP 429 / capacity' if '429' in r['error'] else r['error'] for r in coverage if r['status']=='failed')
    lines += ['', 'Unresolved failures: ' + json.dumps(dict(errors), ensure_ascii=False), '',
              'HTTP 404 means unavailable at that endpoint; HTTP 429 means retrieval remained blocked '
              'after backoff. Failed queries can still contribute successfully archived earlier pages. '
              'The coverage CSV lists their error URLs/offsets and raw source directories.', '',
              'Google country and source language are not fabricated. Apple country is a storefront, '
              'not reviewer residence. Query languages may fall back or overlap.', '', '## Sample rows', '',
              'Text excerpts below are shortened for display only; CSV review text is unchanged.', '',
              '| Platform | Review ID | Date | Rating | Query country / language | Review excerpt |',
              '|---|---|---|---:|---|---|']
    for platform in ('apple','google'):
        selected = [r for r in unique if r['platform']==platform]
        # Display historical and recent observations rather than only one end of the range.
        samples = ([selected[0], selected[len(selected)//2], selected[-1]] if selected else [])
        for r in samples:
            excerpt = ' '.join((r.get('review') or '').split())[:160].replace('|','\\|')
            lines.append(f"| {platform} | {r['review_id']} | {r['review_date']} | {r['rating']} | {r['query_country']} / {r['query_language']} | {excerpt} |")
    lines += ['', 'Full methods, dependency changes, reproduction commands and deduplication rules: '
              '`../../../ZOE_RESEARCH_NOTES.md`. Raw observations and source paths allow every selected '
              'row and every deduplication decision to be audited.', '']
    (output/'RESULTS.md').write_text('\n'.join(lines), encoding='utf-8')


def build(root, output):
    output.mkdir(parents=True, exist_ok=True)
    rows, coverage, runs = [], [], []
    for manifest in sorted((root / 'raw').glob('*/*/run.json')):
        run = read_json(manifest)
        # Pilots are retained untouched, but do not contaminate the full-run dataset.
        if run['review_count'] != sys.maxsize or not run.get('reviews', True):
            continue
        run_dir = manifest.parent
        runs.append(run)
        for query in run['queries']:
            app_id, locale, country = query['app_id'], query['locale'], query['country']
            key = locale if run['platform'] == 'apple' else f'{country}-{locale}'
            # A failed shell launch once passed an entire storefront list as
            # one Apple locale. Keep that immutable run auditable, but do not
            # construct an invalid overlong filesystem path while rebuilding.
            if any(ch.isspace() for ch in str(key)) or len(str(key)) > 32:
                # This is a malformed launch record, not a real storefront.
                # Leave it in the immutable run manifest but omit it from the
                # user-facing coverage table.
                continue
            folder = run_dir / app_id / key
            status_path = folder / 'status.json'
            status = read_json(status_path) if status_path.exists() else dict(status='in_progress_or_interrupted' if folder.exists() else 'not_attempted')
            status.setdefault('status', 'interrupted')
            pages = sorted(folder.glob('page-*.json'))
            count = 0
            metadata = [read_json(p) for p in sorted(folder.glob('[0-9]*.json'))]
            successful = [m for m in metadata if m.get('status') == 200]
            retrieved = metadata[-1]['retrieved_at'] if metadata else run['started_at']
            for page_index, page in enumerate(pages):
                data = read_json(page)
                retrieved = data.get('retrieved_at') or (successful[page_index]['retrieved_at'] if page_index < len(successful) else run['started_at'])
                # Early full Apple records use ISO Z; Google full run v2 uses UTC offsets.
                for index, record in enumerate(data['records']):
                    rows.append(normalise(record, run['platform'], app_id, country, locale,
                                          page.relative_to(root), index, retrieved, run['run_id']))
                    count += 1
            coverage.append(dict(run_id=run['run_id'], platform=run['platform'], app_id=app_id,
                query_country=country, query_language='en-GB' if run['platform']=='apple' else locale,
                status=status['status'], stop_reason=status.get('stop_reason', ''),
                pages=len(pages), rows=count, requests=len(metadata),
                error=status.get('error', ''), source_directory=str(folder.relative_to(root))))
    unique = deduplicate(rows)
    write_csv(output / f'{root.name}_reviews_combined_raw.csv', rows)
    write_csv(output / f'{root.name}_reviews_deduplicated.csv', unique)
    write_csv(output / 'query_coverage.csv', coverage, list(coverage[0]) if coverage else ['status'])
    # Collapse repeated attempts without losing pages collected by an earlier
    # attempt. A later retry can be marked not_attempted when it was interrupted
    # before reaching a storefront that already has archived pages. Prefer a
    # complete attempt; otherwise prefer the attempt with the most pages/rows,
    # then the latest run as the tie-breaker. This makes the final table describe
    # the best observed state across all runs rather than only the retry run.
    effective = {}
    status_rank = {'complete': 3, 'failed': 2, 'in_progress_or_interrupted': 1, 'not_attempted': 0}
    for observation in coverage:
        key = tuple(observation[k] for k in ('platform', 'app_id', 'query_country', 'query_language'))
        previous = effective.get(key)
        if previous is None:
            effective[key] = observation
            continue
        candidate_score = (status_rank.get(observation['status'], 0), observation['pages'],
                           observation['rows'], observation['run_id'])
        previous_score = (status_rank.get(previous['status'], 0), previous['pages'],
                          previous['rows'], previous['run_id'])
        if candidate_score > previous_score:
            effective[key] = observation
    final_coverage = list(effective.values())
    write_csv(output / 'query_coverage_final.csv', final_coverage, list(coverage[0]) if coverage else ['status'])
    summary = dict(generated_at=datetime.now(timezone.utc).isoformat(), raw=statistics(rows),
                   deduplicated=statistics(unique), query_statuses=dict(Counter(r['status'] for r in coverage)),
                   final_query_statuses=dict(Counter(r['status'] for r in final_coverage)),
                   run_ids=[r['run_id'] for r in runs])
    write_report(output, summary, unique, final_coverage, root.name)
    (output / 'validation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    (output / 'collection_manifests.json').write_text(json.dumps(runs, ensure_ascii=False, indent=2))
    with (output / 'SHA256SUMS').open('w') as f:
        for p in sorted(output.glob('*.csv')):
            f.write(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n')
    print(json.dumps(summary, indent=2))
    return rows, unique, coverage


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/zoe'))
    parser.add_argument('--output', type=Path, default=Path('data/zoe/research'))
    args = parser.parse_args()
    build(args.root, args.output)
