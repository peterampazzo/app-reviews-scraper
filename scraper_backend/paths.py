"""Shared resolution for collection data paths."""
import os
import warnings
from pathlib import Path


def _resolved(value, base_dir=None):
    path = Path(value).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = Path(base_dir) / path
    return path.resolve()


def _onedrive_root(environ):
    explicit = environ.get('ONEDRIVE_ROOT')
    if explicit:
        return _resolved(explicit)

    for name in ('OneDriveCommercial', 'OneDriveConsumer', 'OneDrive'):
        value = environ.get(name)
        if value:
            return _resolved(value)

    cloud_storage = Path.home() / 'Library' / 'CloudStorage'
    candidates = sorted(cloud_storage.glob('OneDrive-*')) if cloud_storage.is_dir() else []
    if len(candidates) == 1:
        return candidates[0].resolve()
    if len(candidates) > 1:
        raise RuntimeError(
            'Multiple OneDrive sync roots were found; set ONEDRIVE_ROOT or DATA_ROOT explicitly'
        )
    raise RuntimeError(
        'No OneDrive sync root was found; set ONEDRIVE_ROOT or DATA_ROOT explicitly'
    )


def resolve_data_root(explicit=None, configured=None, base_dir=None, environ=None):
    """Return the canonical data root without creating it.

    Precedence is explicit argument, config value, DATA_ROOT, legacy DATA_LOCATION,
    then the dedicated app folder under the resolved OneDrive root.
    """
    environ = os.environ if environ is None else environ
    if explicit:
        return _resolved(explicit, base_dir)
    if configured:
        return _resolved(configured, base_dir)

    data_root = environ.get('DATA_ROOT')
    legacy_location = environ.get('DATA_LOCATION')
    if data_root and legacy_location:
        if _resolved(data_root) != _resolved(legacy_location):
            raise ValueError('DATA_ROOT and legacy DATA_LOCATION point to different directories')
    if data_root:
        return _resolved(data_root)
    if legacy_location:
        warnings.warn(
            'DATA_LOCATION is deprecated; use DATA_ROOT instead',
            DeprecationWarning,
            stacklevel=2,
        )
        return _resolved(legacy_location)
    return _onedrive_root(environ) / 'Cosmic Latte' / 'app-reviews-scraper-data'
