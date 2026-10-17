# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the real installer in private source/config/data directories."""
import os
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_installation_cannot_overwrite_its_own_source_checkout(self):
        for overlap in ('config','launcher','font-parent-symlink','bashrc'):
            with self.subTest(overlap=overlap),tempfile.TemporaryDirectory() as folder:
                source,config,bashrc,env=self.fixture(folder)
                (config/'kitty.conf').write_text('# keep config\n')
                if overlap=='config':env['KITTY_CONFIG_DIRECTORY']=str(source/'config')
                elif overlap=='launcher':env['ASTRO_BIN_DIRECTORY']=str(source/'bin')
                elif overlap=='bashrc':env['ASTRO_BASHRC']=str(source/'config/astro.bash')
                else:
                    font_parent=Path(env['XDG_DATA_HOME'])/'fonts/astro-pane-controls'
                    font_parent.parent.mkdir(parents=True)
                    font_parent.symlink_to(source/'fonts',target_is_directory=True)
                before={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
                result=self.install(source,env)
                self.assertNotEqual(result.returncode,0)
                after={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
                self.assertEqual(after,before)
                self.assertEqual((config/'kitty.conf').read_text(),'# keep config\n')
                self.assertEqual(bashrc.read_text(),'# personal shell settings\n')
                self.assertEqual(list(config.glob('astro-backup-*')),[])

    def test_help_and_unknown_arguments_never_start_an_installation(self):
        for argument in ('--help','-h','--unknown-option'):
            with self.subTest(argument=argument),tempfile.TemporaryDirectory() as folder:
                source,config,bashrc,env=self.fixture(folder)
                (config/'kitty.conf').write_text('# keep config\n')
                result=subprocess.run(['/bin/sh',str(source/'install.sh'),argument],env=env,
                                      text=True,capture_output=True,timeout=12)
                self.assertEqual((config/'kitty.conf').read_text(),'# keep config\n')
                self.assertEqual(bashrc.read_text(),'# personal shell settings\n')
                self.assertEqual(list(config.glob('astro-backup-*')),[])
                self.assertFalse((config/'.astro-install.lock').exists())
                if argument in ('--help','-h'):
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertIn('Usage:',result.stdout)
                else:
                    self.assertNotEqual(result.returncode,0)

    def test_ambiguous_bashrc_eof_is_refused_before_any_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            source,config,bashrc,env=self.fixture(folder)
            original='export PERSONAL=literal'+'\\'
            bashrc.write_text(original)
            (config/'kitty.conf').write_text('# keep config\n')
            result=self.install(source,env)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('terminal backslash',result.stderr)
            self.assertEqual(bashrc.read_text(),original)
            self.assertEqual((config/'kitty.conf').read_text(),'# keep config\n')
            self.assertEqual(list(config.glob('astro-backup-*')),[])

    def test_unsafe_hook_lock_fails_before_configuration_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            source,config,bashrc,env=self.fixture(folder)
            (config/'kitty.conf').write_text('# keep config\n')
            target=Path(folder)/'not-a-lock';target.write_text('unchanged')
            bashrc.with_name('.bashrc.astro.lock').symlink_to(target)
            result=self.install(source,env)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((config/'kitty.conf').read_text(),'# keep config\n')
            self.assertEqual(target.read_text(),'unchanged')
            self.assertEqual(list(config.glob('astro-backup-*')),[])

    def test_bad_output_types_fail_before_any_replacement(self):
        cases=('config/kitty.app.png','config/astro.bash','data/applications/astro.desktop',
               'bin/astro','data/icons/hicolor/scalable/apps/astro.svg',
               'data/icons/hicolor/32x32/apps/astro.png',
               'data/fonts/astro-pane-controls/AstroPaneControls.ttf')
        for name in cases:
            for kind in ('directory','fifo'):
                with self.subTest(output=name,kind=kind),tempfile.TemporaryDirectory() as folder:
                    source,config,bashrc,env=self.fixture(folder)
                    (config/'kitty.conf').write_text('# keep config\n')
                    path=Path(folder)/'installed'/name
                    path.parent.mkdir(parents=True,exist_ok=True)
                    if kind=='directory': path.mkdir()
                    else: os.mkfifo(path)
                    result=self.install(source,env)
                    self.assertNotEqual(result.returncode,0)
                    self.assertEqual((config/'kitty.conf').read_text(),'# keep config\n')
                    self.assertEqual(bashrc.read_text(),'# personal shell settings\n')
                    self.assertEqual(list(config.glob('astro-backup-*')),[])

    @unittest.skipIf(os.geteuid()==0,'permission checks require an unprivileged user')
    def test_output_parent_permissions_and_types_are_preflighted(self):
        for name,mode in (('data/applications',0o500),('data/icons',0o600),
                          ('data/fonts/astro-pane-controls',0o500),('config/sessions',0o500)):
            with self.subTest(parent=name),tempfile.TemporaryDirectory() as folder:
                source,config,_,env=self.fixture(folder)
                (config/'kitty.conf').write_text('# keep config\n')
                parent=Path(folder)/'installed'/name;parent.mkdir(parents=True,exist_ok=True)
                parent.chmod(mode)
                try:
                    result=self.install(source,env)
                    self.assertNotEqual(result.returncode,0)
                    self.assertEqual((config/'kitty.conf').read_text(),'# keep config\n')
                    self.assertEqual(list(config.glob('astro-backup-*')),[])
                finally: parent.chmod(0o700)
        with tempfile.TemporaryDirectory() as folder:
            source,config,_,env=self.fixture(folder)
            (config/'kitty.conf').write_text('# keep config\n')
            data=Path(env['XDG_DATA_HOME']);data.mkdir(parents=True)
            (data/'icons').write_text('not a directory')
            result=self.install(source,env)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((config/'kitty.conf').read_text(),'# keep config\n')
            self.assertEqual(list(config.glob('astro-backup-*')),[])

    def test_all_asset_backups_preserve_live_and_dangling_symlinks(self):
        for dangling in (False,True):
            with tempfile.TemporaryDirectory() as folder:
                source,config,_,env=self.fixture(folder)
                data=Path(env['XDG_DATA_HOME'])
                destinations={
                    'kitty.app.png':config/'kitty.app.png',
                    'desktop/astro.desktop':data/'applications/astro.desktop',
                    'bin/astro':Path(env['ASTRO_BIN_DIRECTORY'])/'astro',
                    'icons/astro.svg':data/'icons/hicolor/scalable/apps/astro.svg',
                    'fonts/AstroPaneControls.ttf':data/'fonts/astro-pane-controls/AstroPaneControls.ttf',
                }
                for size in (32,64,128,256,512):
                    destinations[f'icons/astro-{size}.png']=data/f'icons/hicolor/{size}x{size}/apps/astro.png'
                targets={}
                for index,(name,path) in enumerate(destinations.items()):
                    path.parent.mkdir(parents=True,exist_ok=True)
                    target=Path(folder)/f'personal-{index}'
                    if not dangling: target.write_text('personal target\n')
                    path.symlink_to(target)
                    targets[name]=target
                result=self.install(source,env)
                self.assertEqual(result.returncode,0,result.stderr)
                backup=next(config.glob('astro-backup-*'))
                for name,path in destinations.items():
                    with self.subTest(dangling=dangling,asset=name):
                        self.assertFalse(path.is_symlink())
                        self.assertTrue((backup/name).is_symlink(),'backup must retain link identity')
                        self.assertEqual(os.readlink(backup/name),str(targets[name]))
                        if dangling: self.assertFalse(targets[name].exists())
                        else: self.assertEqual(targets[name].read_text(),'personal target\n')

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

    def test_mid_install_write_failure_cleans_partial_output_and_restores_from_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            source,config,bashrc,env=self.fixture(folder)
            actual_rc=Path(folder)/'managed-bashrc';bashrc.rename(actual_rc);actual_rc.chmod(0o640);bashrc.symlink_to(actual_rc)
            (config/'kitty.conf').write_text('# original kitty.conf\n')
            session=config/'sessions/default.conf';session.parent.mkdir();session.write_text('# personal session\n')
            dangling_target=Path(folder)/'missing-target'
            launcher=Path(env['ASTRO_BIN_DIRECTORY'])/'astro';launcher.parent.mkdir(parents=True)
            launcher.symlink_to(dangling_target)
            font_out=Path(env['XDG_DATA_HOME'])/'fonts/astro-pane-controls/AstroPaneControls.ttf'
            font_out.parent.mkdir(parents=True);font_out.write_text('old-font')
            # Inject an ENOSPC-like partial write failure on the late font install step,
            # after config files, assets, and the bashrc hook have already been updated.
            real_install=shutil.which('install');assert real_install is not None
            wrapper=Path(folder)/'commands/install'
            wrapper.write_text(
                f'#!/bin/sh\n'
                f'case "$*" in *AstroPaneControls.ttf*) printf partial > "$4"; echo "install: No space left on device" >&2; exit 1 ;; esac\n'
                f'exec "{real_install}" "$@"\n'
            )
            wrapper.chmod(0o755)
            failed=self.install(source,env)
            self.assertNotEqual(failed.returncode,0)
            self.assertIn('Installation stopped; backup directory:',failed.stderr)
            self.assertIn('--restore',failed.stderr)
            self.assertFalse(font_out.exists(),'partial destination file must be removed on write failure')
            backups=list(config.glob('astro-backup-*'))
            self.assertEqual(len(backups),1)
            wrapper.unlink()
            restored=subprocess.run(['/bin/sh',str(source/'install.sh'),'--restore',str(backups[0])],
                                    env=env,text=True,capture_output=True,timeout=12)
            self.assertEqual(restored.returncode,0,restored.stderr)
            self.assertIn('Restored backed-up files from:',restored.stdout)
            self.assertEqual((config/'kitty.conf').read_text(),'# original kitty.conf\n')
            self.assertEqual(session.read_text(),'# personal session\n')
            self.assertTrue(launcher.is_symlink())
            self.assertEqual(os.readlink(launcher),str(dangling_target))
            self.assertEqual(font_out.read_text(),'old-font')
            self.assertTrue(bashrc.is_symlink())
            self.assertEqual(actual_rc.read_text(),'# personal shell settings\n')
            self.assertEqual(actual_rc.stat().st_mode&0o777,0o640)

    def test_invalid_restore_target_is_rejected_without_touching_files(self):
        with tempfile.TemporaryDirectory() as folder:
            source,config,bashrc,env=self.fixture(folder)
            (config/'kitty.conf').write_text('# keep config\n')
            real_dir=Path(folder)/'real-dir';real_dir.mkdir()
            symlink_dir=Path(folder)/'symlink-dir';symlink_dir.symlink_to(real_dir,target_is_directory=True)
            for candidate in (Path(folder)/'missing',bashrc,symlink_dir):
                result=subprocess.run(['/bin/sh',str(source/'install.sh'),'--restore',str(candidate)],
                                      env=env,text=True,capture_output=True,timeout=12)
                self.assertEqual(result.returncode,2)
                self.assertEqual((config/'kitty.conf').read_text(),'# keep config\n')
                self.assertFalse((config/'.astro-install.lock').exists())


if __name__=='__main__':
    unittest.main()
