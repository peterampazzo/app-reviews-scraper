"""Compatibility entry point for DatingAppsNLP research workflows."""
from research.datingapps.scripts.dating_project import (
    atomic_json,
    check,
    collect,
    main,
    make_plans,
    setup,
    summary,
    write_csv,
)

__all__ = [
    'atomic_json',
    'check',
    'collect',
    'main',
    'make_plans',
    'setup',
    'summary',
    'write_csv',
]


if __name__ == '__main__':
    main()
