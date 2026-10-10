"""Bounded retries and immutable per-request evidence for the existing clients."""
import json
import time
import fcntl
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import requests
from .storage import check_budget, write_bytes


@contextmanager
def apple_request_gate(url):
    """Serialize Apple catalog requests across processes, leaving a 10s gap."""
    if not url.startswith('https://apps.apple.com/api/apps/'):
        yield
        return
    folder = Path(__file__).resolve().parent.parent / '.runtime'
    folder.mkdir(exist_ok=True)
    with (folder / 'apple-http.lock').open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            handle.seek(0)
            previous = float(handle.read() or 0)
            time.sleep(max(0, previous + 10 - time.time()))
            yield
        finally:
            handle.seek(0)
            handle.truncate()
            handle.write(str(time.time()))
            handle.flush()
            fcntl.flock(handle, fcntl.LOCK_UN)


def json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


class Transport:
    def __init__(self, raw_dir=None):
        self.raw_dir = Path(raw_dir) if raw_dir else None
        if self.raw_dir:
            self.raw_dir.mkdir(parents=True, exist_ok=False)
        self.session = requests.Session()
        self.sequence = 0

    def request(self, method, url, **kwargs):
        for attempt in range(4):
            check_budget()
            self.sequence += 1
            meta = dict(url=url, method=method, params=kwargs.get('params'),
                        retrieved_at=datetime.now(timezone.utc).isoformat(), attempt=attempt + 1)
            stem = self.raw_dir / f'{self.sequence:06d}' if self.raw_dir else None
            try:
                with apple_request_gate(url):
                    meta['retrieved_at'] = datetime.now(timezone.utc).isoformat()
                    response = self.session.request(method, url, timeout=(15, 60), **kwargs)
                meta.update(status=response.status_code, response_url=response.url,
                            response_headers=dict(response.headers))
                if stem:
                    write_bytes(stem.with_suffix('.body'), response.content)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                meta['error'] = str(exc)
                status = getattr(getattr(exc, 'response', None), 'status_code', None)
                if attempt == 3 or (status and status not in (408, 429, 500, 502, 503, 504)):
                    raise
                delay = 10 * 2 ** attempt
                if status == 429:
                    try:
                        delay = max(delay, float(exc.response.headers.get('Retry-After', 0)))
                    except ValueError:
                        pass
                time.sleep(delay)
            finally:
                if stem:
                    stem.with_suffix('.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    def page(self, number, records, continuation):
        if self.raw_dir:
            write_bytes(self.raw_dir / f'page-{number:06d}.json', json.dumps(
                {'records': records, 'continuation': continuation, 'retrieved_at': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False,
                default=json_default).encode('utf-8'))
