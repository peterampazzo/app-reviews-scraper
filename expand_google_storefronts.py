"""Compatibility entry point for the DatingAppsNLP Google expansion workflow."""
import argparse

from research.datingapps.scripts.expand_google_storefronts import main


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root')
    main(parser.parse_args().data_root)
