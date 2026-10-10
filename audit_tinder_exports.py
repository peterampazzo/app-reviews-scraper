"""Compatibility entry point for the Tinder export audit."""
import runpy


if __name__ == '__main__':
    runpy.run_module('research.datingapps.analysis.audit_tinder_exports', run_name='__main__')
