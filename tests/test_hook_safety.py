# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import os
import signal
import time

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
    def test_hook_lock_is_released_even_if_temporary_cleanup_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bashrc';path.write_text('# original\n')
            acquired=[]
            original=hook.private_lock
            def acquire(lock_path):
                fd=original(lock_path);acquired.append(fd);return fd
            with patch.object(hook,'private_lock',side_effect=acquire),patch.object(Path,'unlink',side_effect=OSError('cleanup failure')):
                with self.assertRaisesRegex(OSError,'cleanup failure'):
                    hook.install_hook(path,Path(folder)/'backup')
            closed=False
            try:
                try:
                    os.fstat(acquired[0])
                except OSError:
                    closed=True
                self.assertTrue(closed,'temporary cleanup failure must not leak the hook lock')
            finally:
                if not closed: os.close(acquired[0])

    def test_ambiguous_eof_escape_is_refused_without_changing_shell_semantics(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);path=folder/'bashrc';backup=folder/'backup'
            for count in (1,2,3,4):
                with self.subTest(backslashes=count):
                    original='printf "%s\\n" preserved '+'\\'*count
                    path.write_text(original)
                    args=['/bin/bash','--noprofile','--norc','-c','source "$1"','private-test',str(path)]
                    before=subprocess.run(args,capture_output=True,timeout=3)
                    self.assertEqual(before.returncode,0)
                    if count%2:
                        with self.assertRaisesRegex(ValueError,'terminal backslash'):
                            hook.install_hook(path,backup)
                        self.assertEqual(path.read_text(),original)
                    else:
                        hook.install_hook(path,backup)
                    after=subprocess.run(args,capture_output=True,timeout=3)
                    self.assertEqual((after.returncode,after.stdout),(before.returncode,before.stdout))
                    backup.unlink(missing_ok=True)

    def test_concurrent_content_identity_and_symlink_changes_are_not_overwritten(self):
        for change in ('content','identity','symlink'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as dirname:
                folder=Path(dirname)
                target=folder/'managed';target.write_text('# original\n');target.chmod(0o640)
                path=folder/'bashrc';path.symlink_to(target)
                backup=folder/'backup'
                original_copy=shutil.copy2
                def edit_after_backup(src,dst):
                    result=original_copy(src,dst)
                    if change=='content': target.write_text('# concurrent editor\n')
                    elif change=='identity':
                        replacement=folder/'replacement';replacement.write_text('# original\n')
                        replacement.chmod(0o640);replacement.replace(target)
                    else:
                        other=folder/'other';other.write_text('# other target\n')
                        path.unlink();path.symlink_to(other)
                    return result
                with patch.object(hook.shutil,'copy2',side_effect=edit_after_backup):
                    with self.assertRaisesRegex(OSError,'changed concurrently'):
                        hook.install_hook(path,backup)
                expected={'content':'# concurrent editor\n','identity':'# original\n','symlink':'# other target\n'}[change]
                self.assertEqual(path.read_text(),expected)
                self.assertTrue(path.is_symlink())
                self.assertEqual(backup.read_text(),'# original\n')
                self.assertEqual(list(folder.glob('.managed.astro-*')),[])

    def test_standalone_alias_writers_share_a_stable_private_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            path=folder/'managed';path.write_text('# original\n')
            alias=folder/'alias';alias.symlink_to(path)
            ready=folder/'ready';release=folder/'release'
            code='''import importlib.util,sys,time
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('hook',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
copy=m.shutil.copy2
def pause(src,dst):
 Path(sys.argv[4]).touch()
 while not Path(sys.argv[5]).exists(): time.sleep(.01)
 return copy(src,dst)
with patch.object(m.shutil,'copy2',side_effect=pause): m.install_hook(Path(sys.argv[2]),Path(sys.argv[3]))
'''
            python=shutil.which('python3');assert python is not None
            with (folder/'worker.log').open('w') as log:
                process=subprocess.Popen([python,'-c',code,str(PATH),str(path),str(folder/'backup'),str(ready),str(release)],stdout=log,stderr=log,start_new_session=True)
                try:
                    deadline=time.monotonic()+3
                    while not ready.exists():
                        self.assertIsNone(process.poll(),(folder/'worker.log').read_text())
                        self.assertLess(time.monotonic(),deadline)
                        time.sleep(.01)
                    result=subprocess.run([python,str(PATH),str(alias),str(folder/'backup2')],capture_output=True,text=True,timeout=3)
                    self.assertNotEqual(result.returncode,0)
                    self.assertIn('in progress',result.stderr)
                finally:
                    release.touch()
                    if process.poll() is None:
                        try: process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid,signal.SIGKILL);process.wait()
                self.assertEqual(process.returncode,0,(folder/'worker.log').read_text())
            lock=folder/'.managed.astro.lock'
            inode=lock.stat().st_ino
            self.assertEqual(lock.stat().st_mode&0o777,0o600)
            hook.install_hook(alias,folder/'unused-backup')
            self.assertEqual(lock.stat().st_ino,inode)
            self.assertFalse((folder/'backup2').exists())

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

    def test_enospc_during_hook_write_keeps_original_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            path=folder/'bashrc';path.write_text('# keep original\n');path.chmod(0o640)
            backup=folder/'backup'
            with patch('os.fsync',side_effect=OSError(28,'No space left on device')):
                with self.assertRaisesRegex(OSError,'No space left on device'):
                    hook.install_hook(path,backup)
            self.assertEqual(path.read_text(),'# keep original\n')
            self.assertFalse(backup.exists())
            self.assertEqual(list(folder.glob('.bashrc.astro-*')),[])

    def test_restore_hook_preserves_symlink_and_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            target=folder/'managed';target.write_text('# original\r\n');target.chmod(0o640)
            link=folder/'bashrc';link.symlink_to(target)
            backup=folder/'backup'
            hook.install_hook(link,backup)
            self.assertIn(hook.BEGIN,target.read_text())
            hook.restore_hook(link,backup)
            self.assertTrue(link.is_symlink())
            self.assertEqual(target.read_bytes(),b'# original\r\n')
            self.assertEqual(target.stat().st_mode&0o777,0o640)
            self.assertFalse(backup.exists())
            self.assertEqual(list(folder.glob('.managed.astro-*')),[])


if __name__=='__main__':
    unittest.main()
