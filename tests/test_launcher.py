# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_start_copies_exact_resume_before_launch_and_preserves_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
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

    def test_desktop_entry_uses_the_startup_launcher(self):
        desktop = (ROOT/'assets/astro.desktop').read_text()
        self.assertIn('\nExec=astro\n', desktop)


if __name__ == '__main__':
    unittest.main()
