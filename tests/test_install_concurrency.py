# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep competing private installs from mixing revisions or sharing unsafe locks."""
import os
from pathlib import Path
import signal
import shutil
import subprocess
import tempfile
import time
import unittest

import test_installer


class InstallConcurrencyTests(unittest.TestCase):
    def test_locked_shell_body_is_checked_as_shell_code(self):
        # install.sh feeds its body to the Python lock holder. Shell linters do
        # not inspect literal heredocs themselves, so keep that coverage here.
        source=(test_installer.ROOT/'install.sh').read_text()
        body=source.split("<<'ASTRO_INSTALL_BODY'\n",1)[1].rsplit('\nASTRO_INSTALL_BODY',1)[0]
        commands=[['/bin/sh','-n']]
        shellcheck=shutil.which('shellcheck')
        if shellcheck: commands.append([shellcheck,'--shell=sh','-'])
        for command in commands:
            with self.subTest(command=command):
                result=subprocess.run(command,input=body,text=True,capture_output=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_competing_release_is_refused_until_whole_install_finishes(self):
        fixture=test_installer.InstallerTests()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            first=folder/'a';second=folder/'b';first.mkdir();second.mkdir()
            source_a,config,bashrc,env=fixture.fixture(first)
            source_b,_,_,_=fixture.fixture(second)
            for source,revision in ((source_a,'A'),(source_b,'B')):
                for name in ('kitty.conf','window_title_bar.py'):
                    path=source/'config'/name
                    path.write_text(path.read_text()+f'\n# private revision {revision}\n')
            ready=folder/'ready';release=folder/'release'
            # Pause near the end too: the lock must cover the font/cache work,
            # not just the configuration-copy loop.
            cache=first/'commands/fc-cache'
            cache.write_text('#!/usr/bin/python3\nimport os,time\nfrom pathlib import Path\nif os.environ.get("TEST_ROLE")=="A":\n Path(os.environ["TEST_READY"]).touch()\n while not Path(os.environ["TEST_RELEASE"]).exists(): time.sleep(.01)\n')
            cache.chmod(0o755)
            env.update(TEST_ROLE='A',TEST_READY=str(ready),TEST_RELEASE=str(release))
            with (folder/'a.log').open('w') as log:
                process=subprocess.Popen(['/bin/sh',str(source_a/'install.sh')],env=env,stdout=log,stderr=log,start_new_session=True)
                try:
                    deadline=time.monotonic()+5
                    while not ready.exists():
                        self.assertIsNone(process.poll(),(folder/'a.log').read_text())
                        self.assertLess(time.monotonic(),deadline,'installer never reached the private barrier')
                        time.sleep(.01)
                    result=fixture.install(source_b,dict(env,TEST_ROLE='B'))
                    self.assertNotEqual(result.returncode,0,'competing installer must not report success')
                    self.assertIn('installation is in progress',result.stderr)
                    self.assertIn('private revision A',(config/'kitty.conf').read_text())
                    # Each shared asset root must independently conflict.
                    other=folder/'other-config'
                    for separate in ({'XDG_DATA_HOME':str(folder/'other-data')},
                                     {'ASTRO_BIN_DIRECTORY':str(folder/'other-bin')}):
                        result=fixture.install(source_b,dict(env,TEST_ROLE='B',KITTY_CONFIG_DIRECTORY=str(other),**separate))
                        self.assertNotEqual(result.returncode,0)
                        self.assertFalse((other/'kitty.conf').exists())
                finally:
                    release.touch()
                    if process.poll() is None:
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid,signal.SIGKILL);process.wait()
                self.assertEqual(process.returncode,0,(folder/'a.log').read_text())
            lock=config/'.astro-install.lock'
            self.assertEqual(lock.stat().st_mode&0o777,0o600)
            inode=lock.stat().st_ino
            result=fixture.install(source_b,dict(env,TEST_ROLE='B'))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(lock.stat().st_ino,inode,'releasing must not unlink/recreate the lock')
            self.assertIn('private revision B',(config/'kitty.conf').read_text())
            self.assertIn('private revision B',(config/'window_title_bar.py').read_text())

    def test_install_lock_symlink_is_refused_without_touching_target(self):
        fixture=test_installer.InstallerTests()
        with tempfile.TemporaryDirectory() as tmp:
            source,config,_,env=fixture.fixture(tmp)
            original=config/'kitty.conf';original.write_text('# keep\n')
            target=Path(tmp)/'not-a-lock';target.write_text('unchanged');target.chmod(0o640)
            (config/'.astro-install.lock').symlink_to(target)
            result=fixture.install(source,env)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(original.read_text(),'# keep\n')
            self.assertEqual(target.read_text(),'unchanged')
            self.assertEqual(target.stat().st_mode&0o777,0o640)
            self.assertEqual(list(config.glob('astro-backup-*')),[])
