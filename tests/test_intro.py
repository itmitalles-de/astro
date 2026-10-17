# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'config/astro_intro.py'


class IntroTests(unittest.TestCase):
    def test_ten_effects_are_distinct_animated_ascii_and_fit_small_panes(self):
        self.assertTrue(PATH.exists(), 'terminal intro module is missing')
        spec = importlib.util.spec_from_file_location('astro_intro', PATH)
        assert spec is not None and spec.loader is not None
        intro = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(intro)
        self.assertEqual(len(intro.EFFECTS), 10)
        self.assertEqual(len(set(intro.EFFECTS)), 10)
        signatures = set()
        for effect in range(10):
            for width, height in [(34, 14), (64, 24), (90, 30)]:
                frames = [intro.frame(effect, time, width, height) for time in [0.0, 0.35, 0.8, 1.2]]
                for picture in frames:
                    self.assertEqual(len(picture), height)
                    self.assertTrue(all(len(row) == width and row.isascii() for row in picture))
                self.assertGreater(len({tuple(p) for p in frames}), 1, intro.EFFECTS[effect])
            signatures.add(tuple(intro.frame(effect, 0.8, 64, 24)[2:-2]))
        self.assertEqual(len(signatures), 10)

    def test_redirected_output_has_no_animation(self):
        import os
        import subprocess
        import sys
        import shutil
        executable = shutil.which('python3')
        assert executable is not None
        result = subprocess.run([executable, str(PATH), '--effect', '1'], capture_output=True, env=dict(os.environ, TERM='xterm-kitty'), timeout=2)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr, b'')

    def test_early_typing_is_preserved_and_terminal_restored(self):
        import fcntl
        import os
        import pty
        import select
        import struct
        import subprocess
        import sys
        import termios
        import time
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 28, 80, 0, 0))
        original = termios.tcgetattr(slave)
        script = f"import runpy,os; m=runpy.run_path({str(PATH)!r}); m['play'](0,3.0); os.write(1,b'INPUT:'+os.read(0,100))"
        import shutil
        executable = shutil.which('python3')
        assert executable is not None
        process = subprocess.Popen([executable, '-c', script], stdin=slave, stdout=slave, stderr=slave, env=dict(os.environ, TERM='xterm-kitty'))
        output = b''
        sent = False
        start = time.monotonic()
        try:
            while time.monotonic()-start < 3:
                if select.select([master], [], [], .1)[0]:
                    output += os.read(master, 65536)
                if b'\x1b[?1049h' in output and not sent:
                    os.write(master, b'astro-keeps-my-typing\n')
                    sent = True
                if b'INPUT:astro-keeps-my-typing' in output:
                    break
            process.wait(timeout=1)
            self.assertTrue(sent, 'intro never entered its alternate screen')
            self.assertIn(b'INPUT:astro-keeps-my-typing', output)
            self.assertIn(b'\x1b[?1049l', output)
            self.assertIn(b'\x1b[?25h', output)
            self.assertEqual(termios.tcgetattr(slave), original)
            self.assertLess(time.monotonic()-start, 1.5, 'input should interrupt the 3-second intro')
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
            os.close(slave)

    def test_default_greeting_waits_for_typing_and_preserves_the_first_command(self):
        import fcntl
        import os
        import pty
        import select
        import shutil
        import struct
        import subprocess
        import termios
        import time
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 28, 80, 0, 0))
        original = termios.tcgetattr(slave)
        executable = shutil.which('python3')
        script = f"import runpy,os; m=runpy.run_path({str(PATH)!r}); m['play'](0); os.write(1,b'FIRST-COMMAND:'+os.read(0,100))"
        assert executable is not None
        process = subprocess.Popen([executable, '-c', script], stdin=slave, stdout=slave, stderr=slave, env=dict(os.environ, TERM='xterm-kitty'))
        output = b''
        try:
            deadline = time.monotonic()+2
            while b'\x1b[?1049h' not in output and time.monotonic()<deadline:
                if select.select([master], [], [], .05)[0]:
                    output += os.read(master,65536)
            self.assertIn(b'\x1b[?1049h',output)
            deadline = time.monotonic()+1.7
            while time.monotonic()<deadline:
                if select.select([master], [], [], .05)[0]:
                    output += os.read(master,65536)
            self.assertIsNone(process.poll(), 'greeting must not time out while idle')
            self.assertFalse(b'\x1b[?1049l' in output, 'must stay visible until typing')
            os.write(master,b'echo astro-first-command\n')
            deadline=time.monotonic()+2
            while b'FIRST-COMMAND:echo astro-first-command' not in output and time.monotonic()<deadline:
                if select.select([master], [], [], .05)[0]:
                    output += os.read(master,65536)
            process.wait(timeout=1)
            self.assertIn(b'FIRST-COMMAND:echo astro-first-command',output)
            self.assertEqual(termios.tcgetattr(slave),original)
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            os.close(master); os.close(slave)

    def test_effects_have_distinct_cat_actions_not_the_same_portrait(self):
        spec = importlib.util.spec_from_file_location('astro_intro_actions', PATH)
        assert spec is not None and spec.loader is not None
        intro = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(intro)
        self.assertTrue(hasattr(intro, 'SCENES'), 'each effect needs its own animated cat poses')
        self.assertEqual(len(intro.SCENES),10)
        self.assertEqual(len(set(intro.SCENES)),10)
        for poses in intro.SCENES:
            self.assertGreaterEqual(len(poses),2)
            self.assertGreater(len(set(poses)),1)
            for pose in poses:
                self.assertTrue(all(row.isascii() for row in pose))
                self.assertLessEqual(''.join(pose).count('@'),1)
        for effect in range(10):
            self.assertNotEqual(intro.frame(effect,5.0,64,24),intro.frame(effect,5.4,64,24),intro.EFFECTS[effect])

    def test_shuffle_bags_cover_ten_without_adjacent_repeats_or_mutation(self):
        import copy
        import random
        spec = importlib.util.spec_from_file_location('astro_intro', PATH)
        assert spec is not None and spec.loader is not None
        intro = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(intro)
        self.assertTrue(hasattr(intro, 'next_effect'), 'shuffle-bag selector is missing')
        for seed in range(20):
            rng = random.Random(seed)
            state = {}
            values = []
            for _ in range(100):
                before = copy.deepcopy(state)
                value, updated = intro.next_effect(state, rng)
                self.assertEqual(state, before)
                state = updated
                values.append(value)
            for offset in range(0, 100, 10):
                self.assertEqual(set(values[offset:offset+10]), set(range(10)))
            self.assertTrue(all(a != b for a, b in zip(values, values[1:])))
        for invalid in [None, [], {'order': [True]+list(range(1, 10)), 'cursor': 0}, {'order': list(range(10)), 'cursor': True}, {'order': [0]*10, 'cursor': 10}, {'order': list(range(10)), 'cursor': -1}]:
            value, state = intro.next_effect(invalid, random.Random(3))
            self.assertIn(value, range(10))
            self.assertEqual(state['cursor'], 1)
            self.assertEqual(set(state['order']), set(range(10)))

    def test_simultaneous_panes_share_one_persistent_bag_and_recover_bad_cache(self):
        import concurrent.futures
        import os
        import tempfile
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('astro_intro', PATH)
        assert spec is not None and spec.loader is not None
        intro = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(intro)
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, XDG_CACHE_HOME=folder):
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                values = list(pool.map(lambda _: intro.choose_effect(), range(10)))
            self.assertEqual(sorted(values), list(range(10)))
            cache = Path(folder)/'astro/intro-cycle.json'
            self.assertTrue(cache.exists())
            cache.write_text('corrupt state')
            self.assertIn(intro.choose_effect(), range(10))


if __name__ == '__main__':
    unittest.main()
