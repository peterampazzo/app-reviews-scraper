"""Backwards-compatible command entry point for app-store collection."""
import sys


def run(*args, **kwargs):
    from scraper_backend.runner import run as run_collection

    return run_collection(*args, **kwargs)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] in ('collect', 'status', 'stop'):
        from scraper_backend.collection import main as collection_main

        return collection_main(argv)

    from scraper_backend.cli import main as scraper_main

    return scraper_main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
