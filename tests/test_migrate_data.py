import tempfile
import unittest
from pathlib import Path

from migrate_data import migrate


class DataMigrationTests(unittest.TestCase):
    def test_dry_run_does_not_create_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (source / 'partial.body').write_bytes(b'incomplete response')
            destination = root / 'external'

            report = migrate(source, destination)

            self.assertEqual(report['counts']['would_copy'], 1)
            self.assertFalse(destination.exists())
            self.assertEqual((source / 'partial.body').read_bytes(), b'incomplete response')

    def test_copy_is_idempotent_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            (source / 'nested').mkdir(parents=True)
            original = source / 'nested' / 'reviews.csv'
            original.write_bytes(b'a,b\n1,2\n')
            destination = root / 'external'

            first = migrate(source, destination, apply=True)
            second = migrate(source, destination, apply=True)

            self.assertEqual(first['counts']['copied'], 1)
            self.assertEqual(second['counts']['identical'], 1)
            self.assertEqual((destination / 'nested' / 'reviews.csv').read_bytes(), original.read_bytes())
            self.assertEqual(original.read_bytes(), b'a,b\n1,2\n')

    def test_conflicting_destination_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (source / 'file').write_bytes(b'source')
            destination = root / 'external'
            destination.mkdir()
            (destination / 'file').write_bytes(b'destination')

            report = migrate(source, destination, apply=True)

            self.assertEqual(report['counts']['conflict'], 1)
            self.assertEqual((destination / 'file').read_bytes(), b'destination')

    def test_nested_roots_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            with self.assertRaisesRegex(ValueError, 'separate, non-nested'):
                migrate(source, source / 'destination')


if __name__ == '__main__':
    unittest.main()
