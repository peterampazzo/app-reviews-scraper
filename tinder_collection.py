"""Compatibility entry point for the Tinder-only collection workflow."""
import runpy


if __name__ == '__main__':
    runpy.run_module('research.datingapps.scripts.tinder_collection', run_name='__main__')
