import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scraper_backend.paths import resolve_data_root


class DataRootTests(unittest.TestCase):
    def test_explicit_and_configured_paths_take_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                resolve_data_root(explicit='cli', configured='config',
                                  base_dir=root, environ={'DATA_ROOT': 'env'}),
                (root / 'cli').resolve(),
            )
            self.assertEqual(
                resolve_data_root(configured='config', base_dir=root,
                                  environ={'DATA_ROOT': 'env'}),
                (root / 'config').resolve(),
            )

    def test_conflicting_environment_roots_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'point to different'):
            resolve_data_root(environ={'DATA_ROOT': '/external/current',
                                       'DATA_LOCATION': '/external/legacy'})

    def test_data_root_environment_is_used(self):
        self.assertEqual(
            resolve_data_root(environ={'DATA_ROOT': '/external/current'}),
            Path('/external/current'),
        )

    def test_configured_root_precedes_environment_aliases(self):
        self.assertEqual(
            resolve_data_root(configured='/config',
                              environ={'DATA_ROOT': '/one', 'DATA_LOCATION': '/two'}),
            Path('/config'),
        )

    def test_legacy_location_warns(self):
        with self.assertWarnsRegex(DeprecationWarning, 'DATA_LOCATION'):
            root = resolve_data_root(environ={'DATA_LOCATION': '/external/legacy'})
        self.assertEqual(root, Path('/external/legacy'))

    def test_default_uses_dedicated_folder_under_configured_onedrive_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = resolve_data_root(environ={'ONEDRIVE_ROOT': str(root)})
        self.assertEqual(resolved, (root / 'Cosmic Latte' / 'app-reviews-scraper-data').resolve())

    def test_missing_onedrive_root_fails_with_override_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('scraper_backend.paths.Path.home', return_value=Path(tmp)):
                with self.assertRaisesRegex(RuntimeError, 'set ONEDRIVE_ROOT or DATA_ROOT'):
                    resolve_data_root(environ={})

    def test_multiple_discovered_roots_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            cloud = Path(tmp) / 'Library' / 'CloudStorage'
            cloud.mkdir(parents=True)
            (cloud / 'OneDrive-work').mkdir()
            (cloud / 'OneDrive-personal').mkdir()
            with patch('scraper_backend.paths.Path.home', return_value=Path(tmp)):
                with self.assertRaisesRegex(RuntimeError, 'Multiple OneDrive'):
                    resolve_data_root(environ={})


if __name__ == '__main__':
    unittest.main()
