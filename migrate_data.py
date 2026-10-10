"""Copy repository-local data to the configured external data root safely."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from scraper_backend.paths import resolve_data_root

CHUNK_SIZE = 1024 * 1024


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_exclusive(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix='.' + destination.name + '.',
            suffix='.copying',
            dir=destination.parent,
            delete=False,
        ) as target:
            temporary = Path(target.name)
            digest = hashlib.sha256()
            with source.open('rb') as original:
                for chunk in iter(lambda: original.read(CHUNK_SIZE), b''):
                    target.write(chunk)
                    digest.update(chunk)
            target.flush()
            os.fsync(target.fileno())
        shutil.copystat(source, temporary)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            source_hash = digest.hexdigest()
            if destination.is_file() and sha256_file(destination) == source_hash:
                return 'identical', source_hash
            return 'conflict', source_hash
        source_hash = digest.hexdigest()
        if sha256_file(destination) != source_hash:
            destination.unlink()
            raise OSError(f'Copy verification failed for {source}')
        return 'copied', source_hash
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _raise_walk_error(error):
    raise error


def migrate(source, destination, apply=False):
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f'Source directory does not exist: {source}')
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Source and destination must be separate, non-nested directories')

    counts = {'would_copy': 0, 'copied': 0, 'identical': 0, 'conflict': 0}
    files = []
    for current, dirs, names in os.walk(source, followlinks=False, onerror=_raise_walk_error):
        current_path = Path(current)
        dirs[:] = sorted(dirs)
        for dirname in dirs:
            if (current_path / dirname).is_symlink():
                raise ValueError(f'Symlinked directories are not supported: {current_path / dirname}')
        for name in sorted(names):
            original = current_path / name
            if original.is_symlink():
                raise ValueError(f'Symlinked files are not supported: {original}')
            relative = original.relative_to(source)
            target = destination / relative
            source_hash = sha256_file(original)
            if target.exists():
                if target.is_file() and sha256_file(target) == source_hash:
                    status = 'identical'
                else:
                    status = 'conflict'
                digest = source_hash
            elif apply:
                status, copied_hash = _copy_exclusive(original, target)
                if copied_hash != source_hash:
                    raise OSError(f'Copy verification failed for {relative}')
                digest = source_hash
            else:
                status = 'would_copy'
                digest = source_hash
            counts[status] += 1
            files.append({'path': relative.as_posix(), 'status': status, 'sha256': digest})

    return {
        'source': str(source),
        'destination': str(destination),
        'mode': 'copy' if apply else 'dry_run',
        'counts': counts,
        'files': files,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=str(Path(__file__).resolve().parent / 'data'))
    parser.add_argument('--destination', help='defaults to the configured collection data root')
    parser.add_argument('--apply', action='store_true', help='copy files; default is a read-only dry run')
    parser.add_argument('--report', help='write the JSON report to this path (stdout otherwise)')
    args = parser.parse_args(argv)
    try:
        destination = args.destination or resolve_data_root()
        report = migrate(args.source, destination, apply=args.apply)
        text = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
        if args.report:
            report_path = Path(args.report).expanduser()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(text, encoding='utf-8')
        else:
            summary = {key: value for key, value in report.items() if key != 'files'}
            summary['conflicts'] = [item['path'] for item in report['files']
                                    if item['status'] == 'conflict'][:50]
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 1 if report['counts']['conflict'] else 0
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
