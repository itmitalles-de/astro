# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BashHookTests(unittest.TestCase):
    def test_install_preserves_user_content_and_is_idempotent(self):
        path = ROOT / 'tools/install_bash_hook.py'
        self.assertTrue(path.exists(), 'bash hook installer is missing')
        spec = importlib.util.spec_from_file_location('astro_bash_hook', path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            bashrc = Path(folder)/'bashrc'
            backup = Path(folder)/'backup/bashrc'
            original = '# Existing user config\nalias safe="printf hello"\n'
            bashrc.write_text(original)
            module.install_hook(bashrc, backup)
            first = bashrc.read_text()
            self.assertTrue(first.startswith(original))
            self.assertEqual(backup.read_text(), original)
            self.assertEqual(first.count('# >>> Astro greeting >>>'), 1)
            module.install_hook(bashrc, Path(folder)/'unused')
            self.assertEqual(bashrc.read_text(), first)
            self.assertFalse((Path(folder)/'unused').exists())


if __name__ == '__main__':
    unittest.main()
