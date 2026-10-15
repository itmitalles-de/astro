#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""One entry point for source checks, Kitty tests and optional private integration."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

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
    for file in ('install.sh','bin/astro'):run(['/bin/sh','-n',file])
    run(['/bin/bash','-n','config/astro.bash'])
    run(['/bin/bash','-n','config/astro_prompt.bash'])
    shellcheck=shutil.which('shellcheck')
    if shellcheck:
        run([shellcheck,'install.sh','bin/astro','config/astro.bash','config/astro_prompt.bash'])
    elif args.require_shellcheck:
        parser.error('ShellCheck is required but not installed')
    else:
        print('SKIP: ShellCheck is not installed',flush=True)
    env=dict(os.environ)
    env.pop('DISPLAY',None);env.pop('WAYLAND_DISPLAY',None)
    run([args.kitty,'+runpy',TESTS],env=env)
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
