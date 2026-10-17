# SPDX-License-Identifier: GPL-3.0-or-later
"""A startup animation must not let its cache block the interactive shell."""
import fcntl
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'config/astro_intro.py'
SPEC = importlib.util.spec_from_file_location('astro_intro_cache', PATH)
assert SPEC is not None and SPEC.loader is not None
intro = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(intro)


class IntroCacheSafetyTests(unittest.TestCase):
    def test_a_stuck_cache_lock_does_not_block_starting_a_shell(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / 'astro'
            cache.mkdir()
            with (cache / 'intro-cycle.json').open('a+') as locked:
                fcntl.flock(locked, fcntl.LOCK_EX)
                executable = shutil.which('python3')
                assert executable is not None
                script = f"import runpy; print(runpy.run_path({str(PATH)!r})['choose_effect']())"
                process = subprocess.Popen([executable, '-c', script], stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, env=dict(os.environ, XDG_CACHE_HOME=folder))
                try:
                    try:
                        output, errors = process.communicate(timeout=1)
                    except subprocess.TimeoutExpired:
                        self.fail('an unrelated cache lock blocked the prompt for a full second')
                    self.assertEqual(process.returncode, 0, errors)
                    self.assertIn(int(output), range(10))
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()

    def test_a_cache_symlink_never_overwrites_an_unrelated_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, XDG_CACHE_HOME=folder):
            cache = Path(folder) / 'astro'
            cache.mkdir()
            unrelated = Path(folder) / 'user-notes.txt'
            unrelated.write_text('these are not animation settings\n')
            (cache / 'intro-cycle.json').symlink_to(unrelated)
            self.assertIn(intro.choose_effect(), range(10))
            self.assertEqual(unrelated.read_text(), 'these are not animation settings\n')


if __name__ == '__main__':
    unittest.main()
