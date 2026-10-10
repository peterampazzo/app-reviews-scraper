"""Compatibility entry point for project-specific collection lanes."""
import argparse

from research.datingapps.scripts.continue_collection import BASE, export, main, retry_plan

__all__ = ['BASE', 'export', 'main', 'retry_plan']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lane', choices=['zoe-retry', 'surge-apple', 'surge-google'])
    parser.add_argument('--data-root')
    arguments = parser.parse_args()
    main(arguments.lane, arguments.data_root)
