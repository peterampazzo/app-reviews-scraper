import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_help_does_not_need_store_configuration_or_network(self):
        result = subprocess.run(
            [sys.executable, str(BASE / 'scraper.py'), '--help'],
            capture_output=True, text=True, cwd=tempfile.gettempdir(),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--data-root', result.stdout)

    def test_runner_uses_explicit_root_from_outside_repository_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_list = root / 'apps.json'
            data_root = root / 'output'
            app_list.write_text(json.dumps({'project': 'test', 'apps': []}))
            result = subprocess.run(
                [sys.executable, str(BASE / 'scraper.py'), '--list', str(app_list),
                 '--store', 'apple', '--reviews', '--data-root', str(data_root)],
                capture_output=True, text=True, cwd=root,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifests = list((data_root / 'test' / 'raw').glob('*/apple/run.json'))
            self.assertEqual(len(manifests), 1)
            self.assertEqual(json.loads(manifests[0].read_text())['queries'], [])


if __name__ == '__main__':
    unittest.main()
