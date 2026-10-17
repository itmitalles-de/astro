#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""One entry point for source checks, Kitty tests and optional private integration."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
TESTS='import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover("tests")); raise SystemExit(not r.wasSuccessful())'


def run(command, *, env=None, timeout=120):
    print('+ '+' '.join(map(str,command)),flush=True)
    subprocess.run(command,cwd=ROOT,env=env,check=True,timeout=timeout)


def check_whitespace():
    # Compare all tracked source with an actual empty tree, including in CI's
    # clean checkout. Let Git choose its object format instead of hardcoding SHA1.
    empty=subprocess.check_output(['git','hash-object','-w','-t','tree','--stdin'],input=b'',cwd=ROOT).decode().strip()
    result=subprocess.run(['git','diff','--check',empty],cwd=ROOT,text=True,capture_output=True,timeout=30)
    if result.returncode:
        raise ValueError(result.stdout+result.stderr)


def check_shell_sources(shellcheck):
    # The lock-owning Python launcher executes this quoted shell body. Shell
    # parsers otherwise see only a valid here-document, not the installed code.
    source=(ROOT/'install.sh').read_text()
    _,marker,body=source.partition("<<'ASTRO_INSTALL_BODY'\n")
    body,end,_=body.partition('\nASTRO_INSTALL_BODY\n')
    if not marker or not end:
        raise ValueError('Cannot identify the executed installer shell body')
    with tempfile.TemporaryDirectory(prefix='astro-shell-check-') as folder:
        installer=Path(folder)/'astro-install-body.sh'
        installer.write_text('#!/bin/sh\nset -eu\n'+body+'\n')
        files=['install.sh','bin/astro',str(installer),'config/astro.bash','config/astro_prompt.bash']
        for file in files[:3]:run(['/bin/sh','-n',file])
        for file in files[3:]:run(['/bin/bash','-n',file])
        if shellcheck:run([shellcheck,*files])
        else:print('SKIP: ShellCheck is not installed',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kitty',default=shutil.which('kitty'))
    parser.add_argument('--require-shellcheck',action='store_true')
    parser.add_argument('--assets',action='store_true',help='rebuild and verify assets in a temporary clone (system Python dependencies required)')
    parser.add_argument('--integration',action='store_true',help='exercise real mouse clicks on a private Xvfb')
    parser.add_argument('--xvfb')
    parser.add_argument('--xvfb-library-path')
    args=parser.parse_args()
    if not args.kitty:parser.error('kitty 0.49.2 must be installed; its Python APIs are required')
    for directory in ('config','tools','tests'):
        for path in sorted((ROOT/directory).glob('*.py')):
            compile(path.read_bytes(),str(path),'exec',dont_inherit=True)
    shellcheck=shutil.which('shellcheck')
    if not shellcheck and args.require_shellcheck:
        parser.error('ShellCheck is required but not installed')
    check_shell_sources(shellcheck)
    env=dict(os.environ)
    env.pop('DISPLAY',None);env.pop('WAYLAND_DISPLAY',None)
    run([args.kitty,'+runpy',TESTS],env=env)
    node=shutil.which('node')
    site_tests=sorted((ROOT/'tests/site').glob('*.test.mjs'))
    if node and site_tests:run([node,'--test',*map(str,site_tests)],env=env)
    if args.assets:run(['/usr/bin/python3',str(ROOT/'tools/check_assets.py')])
    if args.integration:
        command=[sys.executable,str(ROOT/'tools/smoke_test.py'),'--kitty',args.kitty]
        if args.xvfb:command.extend(['--xvfb',args.xvfb])
        if args.xvfb_library_path:command.extend(['--xvfb-library-path',args.xvfb_library_path])
        run(command)
    check_whitespace()
    print('PASS: tracked-source whitespace, including committed and staged files',flush=True)
    print('PASS: all requested checks completed',flush=True)


if __name__=='__main__':
    try:
        main()
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired,ValueError) as error:
        print(f'FAIL: {error}',file=sys.stderr)
        raise SystemExit(1) from error
