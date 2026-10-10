"""Optional shared disk budget for large research collections (logical bytes)."""
import csv
import fcntl
import io
import json
import os
from pathlib import Path
from datetime import datetime, timezone


class StorageBudgetExceeded(RuntimeError):
    pass


def budget_root():
    value = os.environ.get('DATA_BUDGET_ROOT')
    return Path(value).resolve() if value else None


def storage_bytes(root):
    total = 0
    for directory, _, filenames in os.walk(root):
        for name in filenames:
            try:
                total += (Path(directory) / name).stat().st_size
            except FileNotFoundError:
                pass
    return total


def check_budget():
    root = budget_root()
    if root and (root / 'storage_pause.json').exists():
        raise StorageBudgetExceeded(f'Collection paused near storage limit; see {root / "storage_pause.json"}')


def write_bytes(path, data, append=False):
    path = Path(path)
    root = budget_root()
    if root is None or root not in path.resolve().parents:
        with path.open('ab' if append else 'wb') as handle:
            handle.write(data)
        return
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.storage-budget.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        check_budget()
        limit = int(os.environ.get('DATA_BUDGET_BYTES', '9000000000'))
        total = storage_bytes(root)
        previous = path.stat().st_size if path.exists() and not append else 0
        projected = total - previous + len(data)
        if limit > 0 and projected > limit:
            (root / 'storage_pause.json').write_text(json.dumps({
                'status': 'paused_storage', 'limit_bytes': limit, 'current_bytes': total,
                'attempted_bytes': len(data), 'target': str(path),
                'paused_at': datetime.now(timezone.utc).isoformat(),
                'message': 'Configured storage budget reached.'
            }, indent=2))
            raise StorageBudgetExceeded(f'Write would exceed the configured {limit:,}-byte budget')
        with path.open('ab' if append else 'wb') as handle:
            handle.write(data)


def save_review_csv(path, records, provenance):
    """Write a completed locale atomically; an interrupted .part file is never skipped."""
    path = Path(path)
    temporary = path.with_suffix('.csv.part')
    fields = list(dict.fromkeys(k for record in records for k in record))
    fields.extend(k for k in provenance if k not in fields)
    if not records:
        fields = ['reviewId', 'date', 'rating', 'review', 'title'] + fields
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    write_bytes(temporary, buffer.getvalue().encode('utf-8'))
    buffer.seek(0)
    buffer.truncate(0)
    for index, record in enumerate(records, 1):
        writer.writerow(dict(record, **provenance))
        if index % 1000 == 0:
            write_bytes(temporary, buffer.getvalue().encode('utf-8'), append=True)
            buffer.seek(0)
            buffer.truncate(0)
    if buffer.tell():
        write_bytes(temporary, buffer.getvalue().encode('utf-8'), append=True)
    temporary.replace(path)
