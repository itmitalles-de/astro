# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def load_clipboard():
    spec=importlib.util.spec_from_file_location('astro_clipboard_limits',ROOT/'config/astro_clipboard.py')
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class ClipboardLimitTests(unittest.TestCase):
    def test_close_failure_removes_the_incomplete_saved_file(self):
        from contextlib import contextmanager
        module=load_clipboard()
        original=module.tempfile.NamedTemporaryFile
        @contextmanager
        def fail_after_close(**kwargs):
            with original(**kwargs) as image:
                yield image
            raise OSError('simulated close failure')
        with tempfile.TemporaryDirectory() as cache,patch.dict(os.environ,WAYLAND_DISPLAY='private-test',XDG_CACHE_HOME=cache),patch.object(module,'read_bounded',side_effect=[b'image/png\n',b'\x89PNG\r\n\x1a\nfixture']),patch.object(module.tempfile,'NamedTemporaryFile',side_effect=fail_after_close):
            self.assertEqual(module.clipboard_image(),'')
            self.assertEqual(list((Path(cache)/'astro/clipboard').iterdir()),[])

    def test_oversize_png_falls_back_without_creating_a_file(self):
        module=load_clipboard()
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            executable=shutil.which('python3');assert executable is not None
            tool=folder/'wl-paste'
            tool.write_text(f'#!{executable}\nimport sys\nsys.stdout.buffer.write(b"image/png\\n" if "--list-types" in sys.argv else b"\\x89PNG\\r\\n\\x1a\\n"+b"x"*128)\n')
            tool.chmod(0o755)
            cache=folder/'cache'
            with patch.dict(os.environ,PATH=str(folder),WAYLAND_DISPLAY='private-test',XDG_CACHE_HOME=str(cache)),patch.object(module,'MAX_IMAGE_BYTES',32,create=True):
                self.assertEqual(module.clipboard_image(),'')
            self.assertFalse(cache.exists())

    def test_stream_accepts_limit_and_rejects_one_extra_byte(self):
        module=load_clipboard()
        self.assertTrue(hasattr(module,'read_bounded'),'clipboard subprocess output must be bounded while reading')
        executable=shutil.which('python3');assert executable is not None
        self.assertEqual(module.read_bounded([executable,'-c','print("x"*31,end="")'],32,1),b'x'*31)
        self.assertEqual(module.read_bounded([executable,'-c','print("x"*32,end="")'],32,1),b'x'*32)
        with self.assertRaises(ValueError):
            module.read_bounded([executable,'-c','print("x"*33,end="")'],32,1)

    def test_stalled_producer_is_killed_within_the_deadline(self):
        module=load_clipboard()
        self.assertTrue(hasattr(module,'read_bounded'),'clipboard subprocess output must have a streaming deadline')
        executable=shutil.which('python3');assert executable is not None
        start=time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            module.read_bounded([executable,'-c','import time;time.sleep(10)'],1024,.08)
        self.assertLess(time.monotonic()-start,1)


if __name__=='__main__':
    unittest.main()
