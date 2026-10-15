# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_start_copies_exact_resume_before_launch_and_preserves_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            timeout=shutil.which('timeout')
            assert timeout is not None
            (folder/'timeout').symlink_to(timeout)
            copy = folder/'clipboard-copy'
            copy.write_text('#!/usr/bin/python3\nimport os,sys\nfrom pathlib import Path\np=Path(os.environ["TEST_DIR"]); (p/"clipboard").write_bytes(sys.stdin.buffer.read()); (p/"order").write_text("copy\\n")\n')
            copy.chmod(0o755)
            kitty = folder/'kitty'
            kitty.write_text('#!/usr/bin/python3\nimport json,os,sys\nfrom pathlib import Path\np=Path(os.environ["TEST_DIR"]); (p/"args").write_text(json.dumps(sys.argv[1:])); f=(p/"order").open("a"); f.write("kitty\\n"); f.close()\n')
            kitty.chmod(0o755)
            result = subprocess.run(['/bin/sh', str(ROOT/'bin/astro'), '--working-directory', '/a path'], env=dict(os.environ, PATH=str(folder), WAYLAND_DISPLAY='wayland-test', TEST_DIR=tmp), capture_output=True, timeout=3)
            self.assertEqual(result.returncode, 0)
            self.assertTrue((folder/'clipboard').exists(), 'startup did not copy /resume')
            self.assertEqual((folder/'clipboard').read_bytes(), b'/resume')
            self.assertEqual((folder/'order').read_text(), 'copy\nkitty\n')
            self.assertEqual(json.loads((folder/'args').read_text()), ['--class=astro', '--name=astro', '--title=Astro', '--working-directory', '/a path'])
            # A clipboard failure must never stop the terminal from opening.
            copy.write_text('#!/bin/sh\nexit 1\n')
            (folder/'args').unlink()
            result = subprocess.run(['/bin/sh', str(ROOT/'bin/astro')], env=dict(os.environ, PATH=str(folder), WAYLAND_DISPLAY='wayland-test', TEST_DIR=tmp), capture_output=True, timeout=3)
            self.assertEqual(result.returncode, 0)
            self.assertTrue((folder/'args').exists())

    def test_wayland_fallback_passes_the_complete_mime_type_to_both_selections(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            timeout=shutil.which('timeout');assert timeout is not None
            (folder/'timeout').symlink_to(timeout)
            copy=folder/'wl-copy'
            copy.write_text('#!/usr/bin/python3\nimport json,os,sys\nfrom pathlib import Path\np=Path(os.environ["TEST_DIR"])/"copies.json"; a=json.loads(p.read_text()) if p.exists() else []; a.append({"args":sys.argv[1:],"text":sys.stdin.buffer.read().decode()}); p.write_text(json.dumps(a))\n')
            copy.chmod(0o755)
            kitty=folder/'kitty';kitty.write_text('#!/bin/sh\nexit 0\n');kitty.chmod(0o755)
            result=subprocess.run(['/bin/sh',str(ROOT/'bin/astro')],env=dict(os.environ,PATH=str(folder),WAYLAND_DISPLAY='private-test',TEST_DIR=tmp),capture_output=True,timeout=3)
            self.assertEqual(result.returncode,0,result.stderr)
            calls=json.loads((folder/'copies.json').read_text())
            self.assertEqual([c['text'] for c in calls],['/resume','/resume'])
            self.assertEqual(calls[0]['args'],['--type','text/plain;charset=utf-8'])
            self.assertEqual(calls[1]['args'],['--primary','--type','text/plain;charset=utf-8'])

    def test_stuck_clipboard_helper_does_not_block_opening_the_terminal(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            timeout=shutil.which('timeout');assert timeout is not None
            (folder/'timeout').symlink_to(timeout)
            copy=folder/'clipboard-copy';copy.write_text('#!/usr/bin/python3\nimport time\ntime.sleep(10)\n');copy.chmod(0o755)
            kitty=folder/'kitty';kitty.write_text('#!/bin/sh\nexit 0\n');kitty.chmod(0o755)
            start=time.monotonic()
            result=subprocess.run(['/bin/sh',str(ROOT/'bin/astro')],env=dict(os.environ,PATH=str(folder),WAYLAND_DISPLAY='private-test',ASTRO_CLIPBOARD_TIMEOUT='0.1'),capture_output=True,timeout=1.5)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertLess(time.monotonic()-start,1.0)

    def test_information_commands_do_not_overwrite_clipboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            timeout=shutil.which('timeout');assert timeout is not None
            (folder/'timeout').symlink_to(timeout)
            copy=folder/'clipboard-copy'
            copy.write_text('#!/usr/bin/python3\nimport os,sys\nfrom pathlib import Path\nPath(os.environ["TEST_DIR"]).joinpath("copied").write_bytes(sys.stdin.buffer.read())\n')
            copy.chmod(0o755)
            kitty=folder/'kitty';kitty.write_text('#!/bin/sh\nexit 0\n');kitty.chmod(0o755)
            for flag in ('--version','--help','-h'):
                result=subprocess.run(['/bin/sh',str(ROOT/'bin/astro'),flag],env=dict(os.environ,PATH=str(folder),WAYLAND_DISPLAY='private-test',TEST_DIR=tmp),capture_output=True,timeout=3)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertFalse((folder/'copied').exists(),'help/version must not replace clipboard contents')

    def test_desktop_entry_uses_the_startup_launcher(self):
        desktop = (ROOT/'assets/astro.desktop').read_text()
        self.assertIn('\nExec=astro\n', desktop)


if __name__ == '__main__':
    unittest.main()
