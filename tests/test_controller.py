import json
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scraper_backend.collection import load_config, command, supervise, active_collectors


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'apps.json').write_text(json.dumps({'project': 'test', 'apps': [
            {'ios': {'id': '1'}, 'android': {'id': 'test.app'}}]}))
        self.config_path = self.root / 'config.json'
        self.source = {'data_root': 'output', 'apps': 'apps.json', 'steps': [
            {'store': 'google', 'app_ids': ['test.app'], 'locales': ['en', 'fr'], 'countries': ['us']}]}

    def config(self):
        self.config_path.write_text(json.dumps(self.source))
        return load_config(self.config_path)

    def test_config_resolves_paths_and_keeps_arguments_separate(self):
        config = self.config()
        self.assertEqual(config['apps'], str((self.root / 'apps.json').resolve()))
        args = command(config, config['steps'][0])
        self.assertEqual(args[args.index('--locales') + 1:args.index('--countries')], ['en', 'fr'])
        self.assertNotIn('--similar', args)
        self.source['steps'][0]['locales'] = ['us ae ao']
        with self.assertRaises(ValueError):
            self.config()

    def test_cli_data_root_overrides_config_root(self):
        self.config()
        override = self.root / 'override'
        result = subprocess.run(
            [sys.executable, 'scraper.py', 'collect', '--config', str(self.config_path),
             '--data-root', str(override), '--dry-run'],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(override), result.stdout)
        self.assertFalse(override.exists())

    def test_unknown_ids_and_google_apple_resume_are_rejected(self):
        self.source['steps'][0]['app_ids'] = ['wrong']
        with self.assertRaises(ValueError):
            self.config()
        self.source['steps'][0]['app_ids'] = ['test.app']
        self.source['steps'][0]['resume_apple_from'] = 'latest'
        with self.assertRaises(ValueError):
            self.config()

    def test_dry_run_creates_no_output(self):
        self.config()
        result = subprocess.run([sys.executable, 'scraper.py', 'collect', '--config',
                                 str(self.config_path), '--dry-run'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'output').exists())

    def test_existing_collector_blocks_launch(self):
        with patch('scraper_backend.collection.active_collectors', return_value=['123 scraper.py']):
            with self.assertRaisesRegex(RuntimeError, 'already running'):
                supervise(self.config())

    def test_sequential_workers_and_failure_stop(self):
        config = self.config()
        config['steps'] *= 2
        with patch('scraper_backend.collection.active_collectors', return_value=[]), patch(
                'scraper_backend.collection.command', return_value=[sys.executable, '-c', 'raise SystemExit(3)']):
            state = supervise(config)
        self.assertEqual(state['status'], 'failed')
        self.assertEqual(len(state['steps']), 1)
        self.assertEqual(state['steps'][0]['exit_code'], 3)

    def test_stop_request_waits_for_worker_exit(self):
        config = self.config()
        def stop():
            pointer = self.root / 'output/controller_status.json'
            for _ in range(100):
                if pointer.exists():
                    state = json.loads(pointer.read_text())
                    if state['steps']:
                        (Path(state['job']) / 'stop.request').touch()
                        return
                time.sleep(.02)
        thread = threading.Thread(target=stop)
        thread.start()
        with patch('scraper_backend.collection.active_collectors', return_value=[]), patch(
                'scraper_backend.collection.command', return_value=[sys.executable, '-c', 'import time; time.sleep(60)']):
            state = supervise(config)
        thread.join()
        self.assertEqual(state['status'], 'paused')
        with self.assertRaises(ProcessLookupError):
            os.kill(state['steps'][0]['pid'], 0)

    def test_expired_deadline_starts_no_worker(self):
        with patch('scraper_backend.collection.active_collectors', return_value=[]):
            state = supervise(self.config(), time.time() - 1)
        self.assertEqual(state['status'], 'paused')
        self.assertEqual(state['steps'], [])

    def test_legacy_lock_prevents_launch(self):
        config = self.config()
        root = Path(config['data_root'])
        root.mkdir()
        with (root / '.collection.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                supervise(config)

    def test_deadline_interrupts_apple_cooldown_without_launch(self):
        self.source['steps'] = [{'store': 'apple', 'app_ids': ['1'], 'locales': ['us']}]
        config = self.config()
        (self.root / '.runtime').mkdir()
        (self.root / '.runtime/apple-http.lock').touch()
        with patch('scraper_backend.collection.BASE', self.root), patch(
                'scraper_backend.collection.active_collectors', return_value=[]), patch(
                'scraper_backend.collection.subprocess.Popen') as launch:
            state = supervise(config, time.time() + .1)
        launch.assert_not_called()
        self.assertEqual(state['status'], 'paused')

    def test_sigterm_is_graceful_and_handler_restored(self):
        config = self.config()
        original = signal.getsignal(signal.SIGTERM)
        timer = threading.Timer(.2, lambda: os.kill(os.getpid(), signal.SIGTERM))
        with patch('scraper_backend.collection.active_collectors', return_value=[]), patch(
                'scraper_backend.collection.command', return_value=[sys.executable, '-c', 'import time; time.sleep(60)']):
            timer.start()
            try:
                state = supervise(config)
            finally:
                timer.cancel()
                timer.join()
        self.assertEqual(state['status'], 'paused')
        self.assertEqual(signal.getsignal(signal.SIGTERM), original)
        with self.assertRaises(ProcessLookupError):
            os.kill(state['steps'][0]['pid'], 0)

    def test_stale_running_state_is_not_silently_replaced(self):
        config = self.config()
        root = Path(config['data_root'])
        root.mkdir()
        pointer = root / 'controller_status.json'
        pointer.write_text('{"status": "running", "pid": 99999999}')
        before = pointer.read_bytes()
        with patch('scraper_backend.collection.active_collectors', return_value=[]):
            with self.assertRaisesRegex(RuntimeError, 'no verified terminal state'):
                supervise(config)
        self.assertEqual(pointer.read_bytes(), before)

    def test_process_inventory_detects_legacy_launchers(self):
        result = subprocess.CompletedProcess([], 0, '123 /python /repo/tinder_collection.py\n124 ps -axo pid=,command=\n')
        with patch('scraper_backend.collection.subprocess.run', return_value=result):
            self.assertEqual(active_collectors(), ['123 /python /repo/tinder_collection.py'])
