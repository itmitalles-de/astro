# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/'tools/install_bash_hook.py'
spec=importlib.util.spec_from_file_location('astro_hook_safety',PATH)
assert spec is not None and spec.loader is not None
hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)


class HookSafetyTests(unittest.TestCase):
    def test_already_current_readonly_hook_needs_no_write_permission(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bashrc';path.write_text(hook.BLOCK);path.chmod(0o400)
            parent=Path(folder);parent.chmod(0o500)
            try:
                hook.install_hook(path,parent/'unused-backup')
                self.assertEqual(path.read_text(),hook.BLOCK)
                self.assertFalse((parent/'unused-backup').exists())
            finally:
                parent.chmod(0o700);path.chmod(0o600)

    def test_inline_marker_text_is_not_a_managed_block(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bashrc';original=f"note='{hook.BEGIN}'\nexport USER_SETTING=kept\n"
            path.write_text(original)
            hook.install_hook(path,Path(folder)/'backup')
            self.assertTrue(path.read_text().startswith(original))
            once=path.read_bytes();hook.install_hook(path,Path(folder)/'backup2')
            self.assertEqual(path.read_bytes(),once)
            self.assertFalse((Path(folder)/'backup2').exists())

    def test_missing_reversed_and_duplicate_markers_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bashrc';backup=Path(folder)/'backup'
            for content in (hook.BEGIN+'\n',hook.END+'\n'+hook.BEGIN+'\n',hook.BEGIN+'\n'+hook.BEGIN+'\n'+hook.END+'\n'):
                path.write_text(content)
                with self.assertRaisesRegex(ValueError,'Ambiguous'):
                    hook.install_hook(path,backup)
                self.assertEqual(path.read_text(),content)
                self.assertFalse(backup.exists())

    def test_atomic_replace_failure_keeps_original_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bashrc';path.write_text('# do not truncate me\n');path.chmod(0o640)
            with patch('os.replace',side_effect=OSError('simulated rename failure')):
                with self.assertRaises(OSError):
                    hook.install_hook(path,Path(folder)/'backup')
            self.assertEqual(path.read_text(),'# do not truncate me\n')
            self.assertEqual(list(Path(folder).glob('.bashrc.astro-*')),[])

    def test_symlink_and_file_mode_survive_atomic_update(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'managed';target.write_text('# personal\r\n');target.chmod(0o640)
            link=Path(folder)/'bashrc';link.symlink_to(target)
            hook.install_hook(link,Path(folder)/'backup')
            self.assertTrue(link.is_symlink())
            self.assertTrue(target.read_bytes().startswith(b'# personal\r\n'))
            self.assertEqual(target.stat().st_mode&0o777,0o640)
            self.assertEqual((Path(folder)/'backup').read_bytes(),b'# personal\r\n')

    def test_cli_check_refuses_bad_markers_without_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bashrc';path.write_text(hook.END+'\n')
            python=shutil.which('python3');assert python is not None
            result=subprocess.run([python,str(PATH),'--check',str(path)],cwd=folder,capture_output=True,timeout=3)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(path.read_text(),hook.END+'\n')
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()),['bashrc'])


if __name__=='__main__':
    unittest.main()
