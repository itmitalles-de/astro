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

    def test_nvtop_fallback_uses_xterm_256color_without_mutating_shell_term(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            nvtop=folder/'nvtop'
            nvtop.write_text('#!/bin/sh\nprintf "%s:%s" "$TERM" "$*" > "$TEST_NVTOP_OUT"\n')
            nvtop.chmod(0o755)
            out=folder/'nvtop-out'
            rc=folder/'bashrc';rc.write_text('source "$ASTRO_TEST_SOURCE"\n')
            env=dict(os.environ,PATH=str(folder)+os.pathsep+os.environ['PATH'],
                     TERM='xterm-kitty',KITTY_CONFIG_DIRECTORY=str(ROOT/'config'),
                     KITTY_WINDOW_ID='9876',ASTRO_GREETED_WINDOW='9876',
                     ASTRO_TEST_SOURCE=str(ROOT/'config/astro.bash'),TEST_NVTOP_OUT=str(out))
            result=subprocess.run(
                ['/bin/bash','--noprofile','--rcfile',str(rc),'-i','-c','nvtop --delay 5 && printf ":%s" "$TERM" >> "$TEST_NVTOP_OUT"'],
                env=env,capture_output=True,text=True,timeout=3,check=True)
            self.assertEqual(result.returncode,0)
            self.assertEqual(out.read_text(),'xterm-256color:--delay 5:xterm-kitty')

    def test_nvtop_fallback_preserves_existing_user_definition(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            out=folder/'nvtop-custom'
            rc=folder/'bashrc'
            rc.write_text('nvtop() { printf "custom:%s" "$*" > "$TEST_NVTOP_OUT"; }\nsource "$ASTRO_TEST_SOURCE"\n')
            env=dict(os.environ,TERM='xterm-kitty',KITTY_CONFIG_DIRECTORY=str(ROOT/'config'),
                     KITTY_WINDOW_ID='9876',ASTRO_GREETED_WINDOW='9876',
                     ASTRO_TEST_SOURCE=str(ROOT/'config/astro.bash'),TEST_NVTOP_OUT=str(out))
            subprocess.run(['/bin/bash','--noprofile','--rcfile',str(rc),'-i','-c','nvtop -d'],
                           env=env,capture_output=True,text=True,timeout=3,check=True)
            self.assertEqual(out.read_text(),'custom:-d')


if __name__=='__main__':
    unittest.main()
