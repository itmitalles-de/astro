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
    def test_boolean_information_options_match_native_values_and_overrides(self):
        import contextlib
        from importlib import import_module
        parse_args=import_module('kitty.cli').parse_args
        aliases=('--help','--version','-h','-v','-hh','-vv','-1h','-1v','-eh','-ev','-hv','-vh')
        cases=[[alias+'='+value] for alias in aliases for value in ('n','no','false','y','yes','true','NO','0')]
        cases.extend((['-v','--version=no'],['--version=no','-v'],
                      ['-h','--help=false'],['--help=false','-h'],
                      ['-v','--help=no','--version=false'],
                      ['--version=no','--help=no','printf','--help'],
                      ['-hh=no','--','printf','--version'],
                      ['-v','--','printf'],['-v','printf'],
                      ['-hT=no'],['-vT=--help'],['-Th=no'],['-Tvv=no']))
        for args in cases:
            with self.subTest(args=args),tempfile.TemporaryFile(mode='w+') as output:
                # Native help formatting requires a real fileno, not StringIO.
                normal=False
                with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
                    try:
                        options,_=parse_args(args)
                    except SystemExit:
                        pass  # Help/version/errors must not touch the clipboard.
                    else:
                        normal=not options.version
                forwarded,copied=self.recorded_launch(args)
                self.assertEqual(copied,normal,'native Boolean option semantics decide normal launch')
                expected=['--class=astro','--name=astro','--title=Astro',*args] if normal else args
                self.assertEqual(forwarded,expected)

    def test_valueless_list_prefix_short_clusters_never_copy_and_isolate_native_parser(self):
        import resource
        import sys
        for cluster in ('-ch=n','-oh=n','-cv=n','-ov=n','-ch=y','-oh=false'):
            with self.subTest(cluster=cluster):
                forwarded,copied=self.recorded_launch([cluster])
                self.assertFalse(copied,'unsupported -c/-o short-cluster prefixes must not touch the clipboard')
                self.assertEqual(forwarded,[cluster])
        # Verify the upstream Kitty 0.49.2 parser behavior in an isolated child
        # with core dumps disabled and display variables unset (Issue #3).
        env=dict(os.environ)
        env.pop('DISPLAY',None);env.pop('WAYLAND_DISPLAY',None)
        child=subprocess.run(
            [sys.executable,'+runpy','from kitty.cli import parse_args; parse_args(["-ch=n"])'],
            env=env,capture_output=True,timeout=5,
            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE,(0,0)),
        )
        self.assertNotEqual(child.returncode,0,'-ch=n is not a valid normal launch in Kitty 0.49.2')

    def test_timeout_override_is_positive_finite_and_bounded(self):
        invalid=('0','0s','.0','-1','inf','NaN','1e999','999999999999999999999999',
                 '31','30.000001','2m','1h','0.0000001','1..2','+1')
        valid=('0.1','2','2s','.001','30','30.000000','0001.5','')
        for value in (*invalid,*valid):
            with self.subTest(timeout=value),tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp)
                timeout=folder/'timeout'
                timeout.write_text('#!/usr/bin/python3\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["TEST_DIR"]).joinpath("timed").write_text(json.dumps(sys.argv[1:]))\n')
                timeout.chmod(0o755)
                for name in ('clipboard-copy','kitty'):
                    tool=folder/name;tool.write_text('#!/bin/sh\nexit 0\n');tool.chmod(0o755)
                result=subprocess.run(['/bin/sh',str(ROOT/'bin/astro')],env=dict(os.environ,PATH=str(folder),WAYLAND_DISPLAY='private-test',TEST_DIR=tmp,ASTRO_CLIPBOARD_TIMEOUT=value),capture_output=True,timeout=3)
                self.assertEqual(result.returncode,0,result.stderr)
                timed=folder/'timed'
                if value in invalid:
                    self.assertFalse(timed.exists(),'invalid override must skip clipboard initialization')
                else:
                    self.assertTrue(timed.exists())
                    actual=json.loads(timed.read_text())
                    expected=value.removesuffix('s') if value else '2'
                    self.assertEqual(actual[:3],['--kill-after=0.2','--',expected])

    def recorded_launch(self,args):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            timeout=shutil.which('timeout');assert timeout is not None
            (folder/'timeout').symlink_to(timeout)
            copy=folder/'clipboard-copy'
            copy.write_text('#!/usr/bin/python3\nimport os,sys\nfrom pathlib import Path\nPath(os.environ["TEST_DIR"]).joinpath("copied").write_bytes(sys.stdin.buffer.read())\n')
            copy.chmod(0o755)
            kitty=folder/'kitty'
            kitty.write_text('#!/usr/bin/python3\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["TEST_DIR"]).joinpath("args").write_text(json.dumps(sys.argv[1:]))\n')
            kitty.chmod(0o755)
            result=subprocess.run(['/bin/sh',str(ROOT/'bin/astro'),*args],env=dict(os.environ,PATH=str(folder),WAYLAND_DISPLAY='private-test',TEST_DIR=tmp),capture_output=True,timeout=3)
            self.assertEqual(result.returncode,0,result.stderr)
            return json.loads((folder/'args').read_text()),(folder/'copied').exists()

    def test_information_and_utility_dispatch_never_copies(self):
        for args in (['--config','/dev/null','--version'],['--hold','-v'],
                     ['--title=private','--help'],['+runpy','print("private")'],
                     ['+','kitten','--help'],['@','--help'],
                     ['--replay-commands','private-dump']):
            with self.subTest(args=args):
                forwarded,copied=self.recorded_launch(args)
                self.assertFalse(copied)
                self.assertEqual(forwarded,args,'utility dispatch must retain the initial subcommand')

    def test_option_operands_and_program_arguments_are_not_information_flags(self):
        from kitty.cli import parse_args
        for args in (['--title','--version','printf','--version'],
                     ['--title=--version','printf','--help'],
                     ['--class=--help','printf','--version'],
                     ['--','printf','--version'],['printf','--version'],
                     ['-e','printf','--version'],['--version=no'],
                     ['-1e','printf','--version'],['-1T','--version','printf'],
                     ['-T1','printf','--version'],['-v=no','printf','--version'],
                     ['--config=NONE','--','--version']):
            with self.subTest(args=args):
                options,_=parse_args(args)
                self.assertFalse(options.version,'expected behavior comes from native Kitty parsing')
                forwarded,copied=self.recorded_launch(args)
                self.assertTrue(copied,'only the Kitty option prefix controls information mode')
                self.assertEqual(forwarded,['--class=astro','--name=astro','--title=Astro',*args])

    def test_native_kitty_operand_options_are_all_recognized(self):
        from kitty.cli import parse_args,parse_option_spec
        definitions,_=parse_option_spec()
        for definition in definitions:
            if isinstance(definition,str) or definition.type.startswith('bool'):
                continue
            for alias in definition.aliases:
                if alias=='--replay-commands': continue
                value='normal' if alias=='--start-as' else '--version'
                forms=([alias,value,'printf','--version'],[alias+'='+value,'printf','--version'])
                for args in forms:
                    with self.subTest(args=args):
                        options,rest=parse_args(args)
                        self.assertFalse(options.version)
                        self.assertEqual(rest,['printf','--version'])
                        forwarded,copied=self.recorded_launch(args)
                        self.assertTrue(copied)
                        self.assertEqual(forwarded[3:],args)

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
