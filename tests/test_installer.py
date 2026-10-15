# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the real installer in private source/config/data directories."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    @unittest.skipIf(os.geteuid()==0,'write-permission refusal needs an unprivileged user')
    def test_unwritable_hook_target_fails_before_replacing_config(self):
        with tempfile.TemporaryDirectory() as folder:
            source,config,bashrc,env=self.fixture(folder)
            (config/'kitty.conf').write_text('# keep me\n')
            locked=Path(folder)/'managed-readonly';locked.mkdir()
            target=locked/'bashrc';bashrc.rename(target);bashrc.symlink_to(target)
            target.chmod(0o400);locked.chmod(0o500)
            try:
                result=self.install(source,env)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual((config/'kitty.conf').read_text(),'# keep me\n')
                self.assertEqual(list(config.glob('astro-backup-*')),[])
                self.assertEqual(target.read_text(),'# personal shell settings\n')
            finally:
                locked.chmod(0o700);target.chmod(0o600)

    def fixture(self, folder):
        folder=Path(folder)
        source=folder/'source';source.mkdir()
        for directory in ('assets','bin','config','fonts','tools'):
            shutil.copytree(ROOT/directory,source/directory)
        shutil.copy2(ROOT/'install.sh',source/'install.sh')
        commands=folder/'commands';commands.mkdir()
        for name in ('fc-cache','gtk-update-icon-cache','update-desktop-database'):
            path=commands/name;path.write_text('#!/bin/sh\nexit 0\n');path.chmod(0o755)
        config=folder/'installed/config';config.mkdir(parents=True)
        bashrc=folder/'bashrc';bashrc.write_text('# personal shell settings\n')
        env=dict(os.environ,PATH=str(commands)+os.pathsep+os.environ['PATH'],
                 KITTY_CONFIG_DIRECTORY=str(config),XDG_DATA_HOME=str(folder/'installed/data'),
                 XDG_CACHE_HOME=str(folder/'cache'),ASTRO_BIN_DIRECTORY=str(folder/'installed/bin'),
                 ASTRO_BASHRC=str(bashrc))
        return source,config,bashrc,env

    def install(self,source,env):
        return subprocess.run(['/bin/sh',str(source/'install.sh')],env=env,text=True,capture_output=True,timeout=12)

    def test_upgrade_preserves_personal_workspace_and_backs_up_replaced_config(self):
        with tempfile.TemporaryDirectory() as folder:
            source,config,bashrc,env=self.fixture(folder)
            session=config/'sessions/default.conf';session.parent.mkdir();session.write_text('layout splits\n# personal panes\n')
            original=session.read_bytes()
            (config/'kitty.conf').write_text('# old personal configuration\n')
            result=self.install(source,env)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(session.read_bytes(),original,'upgrades must not replace the personal pane layout')
            self.assertIn('Ctrl+Shift+F5',result.stdout)
            self.assertNotIn('Restart kitty',result.stdout)
            self.assertEqual((config/'kitty.conf').read_bytes(),(source/'config/kitty.conf').read_bytes())
            backups=list(config.glob('astro-backup-*'))
            self.assertEqual(len(backups),1)
            self.assertEqual(backups[0].stat().st_mode&0o777,0o700)
            self.assertEqual((backups[0]/'kitty.conf').read_text(),'# old personal configuration\n')
            self.assertEqual((config/'reload_pane_controls.py').read_bytes(),(source/'config/reload_pane_controls.py').read_bytes())

    def test_explicit_session_replacement_keeps_a_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            source,config,bashrc,env=self.fixture(folder)
            session=config/'sessions/default.conf';session.parent.mkdir();session.write_text('# custom session\n')
            result=self.install(source,dict(env,ASTRO_REPLACE_SESSION='1'))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(session.read_bytes(),(source/'config/sessions/default.conf').read_bytes())
            backups=list(config.glob('astro-backup-*'))
            self.assertEqual((backups[0]/'sessions/default.conf').read_text(),'# custom session\n')

    def test_missing_source_asset_fails_before_replacing_any_user_file(self):
        with tempfile.TemporaryDirectory() as folder:
            source,config,bashrc,env=self.fixture(folder)
            (source/'assets/astro-128.png').unlink()
            (config/'kitty.conf').write_text('# keep me\n')
            result=self.install(source,env)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((config/'kitty.conf').read_text(),'# keep me\n')
            self.assertEqual(list(config.glob('astro-backup-*')),[])
            self.assertEqual(bashrc.read_text(),'# personal shell settings\n')

    def test_invalid_bash_hook_fails_before_replacing_any_user_file(self):
        with tempfile.TemporaryDirectory() as folder:
            source,config,bashrc,env=self.fixture(folder)
            (config/'kitty.conf').write_text('# keep me\n')
            bashrc.write_text('# >>> Astro greeting >>>\n# missing end marker\n')
            before=bashrc.read_bytes()
            result=self.install(source,env)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((config/'kitty.conf').read_text(),'# keep me\n')
            self.assertEqual(bashrc.read_bytes(),before)
            self.assertEqual(list(config.glob('astro-backup-*')),[])

    def test_first_install_adds_default_session_and_preserves_bashrc_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            source,config,bashrc,env=self.fixture(folder)
            actual=Path(folder)/'managed-bashrc';bashrc.rename(actual);bashrc.symlink_to(actual)
            result=self.install(source,env)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(bashrc.is_symlink())
            self.assertTrue(actual.read_text().startswith('# personal shell settings\n'))
            self.assertEqual((config/'sessions/default.conf').read_bytes(),(source/'config/sessions/default.conf').read_bytes())
            self.assertEqual(actual.read_text().count('# >>> Astro greeting >>>'),1)


if __name__=='__main__':
    unittest.main()
