"""Regression coverage for import-time migration and delayed episode writes."""
import jinx_test_support
import ast
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import jinx
import long_memory


class MemoryIsolation(unittest.TestCase):
    def test_import_and_default_constructor_use_temporary_state(self):
        self.assertEqual(jinx.memory.path.parent, jinx_test_support.STATE)
        self.assertEqual(long_memory.LongMemory().path, jinx.memory.path)
        self.assertEqual(jinx.memory.embed(['test']), [[1.0, 0.0]])

    def test_delayed_episode_keeps_temporary_target_after_patch_ends(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = long_memory.LongMemory(Path(folder) / 'memory.sqlite3', embed=lambda _: None)
            with patch.object(jinx, 'memory', memory):
                worker = threading.Thread(target=jinx.memory.record_episode,
                                          args=('isolated question', 'isolated answer'), daemon=True)
            worker.start()
            worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(memory.count(), 1)
            self.assertEqual(jinx.memory.path.parent, jinx_test_support.STATE)

    def test_all_jinx_importing_modules_load_fixture_first(self):
        for path in Path(__file__).parent.glob('test*.py'):
            tree = ast.parse(path.read_text())
            imports = sorted((node.lineno, alias.name)
                             for node in ast.walk(tree) if isinstance(node, ast.Import)
                             for alias in node.names)
            targets = [line for line, name in imports if name == 'jinx']
            if targets:
                fixtures = [line for line, name in imports if name == 'jinx_test_support']
                self.assertTrue(fixtures and min(fixtures) < min(targets), path.name)
