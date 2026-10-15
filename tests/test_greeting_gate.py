# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the startup gate in real interactive Bash shells on private PTYs."""
import os
from pathlib import Path
import pty
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class GreetingGateTests(unittest.TestCase):
    def greeted(self, command_shell=False, descendant=False):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            marker=folder/'intro-called'
            python=folder/'python3'
            python.write_text('#!/bin/sh\nprintf called > "$TEST_CALLED"\n');python.chmod(0o755)
            rc=folder/'bashrc';rc.write_text('source "$ASTRO_TEST_SOURCE"\n')
            env=dict(os.environ,PATH=str(folder)+os.pathsep+os.environ['PATH'],
                     KITTY_CONFIG_DIRECTORY=str(ROOT/'config'),KITTY_WINDOW_ID='9876',
                     ASTRO_TEST_SOURCE=str(ROOT/'config/astro.bash'),TEST_CALLED=str(marker))
            env.pop('ASTRO_GREETED_WINDOW',None)
            if descendant: env['ASTRO_GREETED_WINDOW']='9876'
            args=['/bin/bash','--noprofile','--rcfile',str(rc),'-i']
            if command_shell: args.extend(['-c','printf AGENT_READY'])
            master,slave=pty.openpty()
            process=subprocess.Popen(args,stdin=slave,stdout=slave,stderr=slave,env=env)
            try:
                if not command_shell: os.write(master,b'exit\n')
                self.assertEqual(process.wait(timeout=3),0)
                return marker.exists()
            finally:
                if process.poll() is None: process.kill();process.wait()
                os.close(master);os.close(slave)

    def test_agent_command_shell_does_not_invoke_waiting_greeting(self):
        self.assertFalse(self.greeted(command_shell=True))

    def test_new_interactive_prompt_still_greets(self):
        self.assertTrue(self.greeted())

    def test_descendant_shell_skips_already_seen_greeting(self):
        self.assertFalse(self.greeted(descendant=True))


if __name__=='__main__':
    unittest.main()
