#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real pane-control checks on a private X server; never send desktop input."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kitty',default=shutil.which('kitty'))
    parser.add_argument('--xvfb',default=shutil.which('Xvfb'))
    parser.add_argument('--xvfb-library-path',help='optional library path for a privately extracted Xvfb')
    args=parser.parse_args()
    if not args.kitty or not args.xvfb:parser.error('kitty and Xvfb are required for this optional integration check')
    inspector=ROOT/'tools/qa_inspect.py'
    with tempfile.TemporaryDirectory(prefix='astro-smoke-') as folder:
        folder=Path(folder)
        config=folder/'config';shutil.copytree(ROOT/'config',config)
        cwd=folder/'source-cwd';cwd.mkdir()
        home=folder/'home';home.mkdir()
        (home/'.bashrc').write_text('source "$KITTY_CONFIG_DIRECTORY/astro.bash"\n')
        (home/'.profile').write_text('[ ! -r "$HOME/.bashrc" ] || . "$HOME/.bashrc"\n')
        data=folder/'data';font_dir=data/'fonts/astro';font_dir.mkdir(parents=True)
        shutil.copy2(ROOT/'fonts/AstroPaneControls.ttf',font_dir/'AstroPaneControls.ttf')
        with (folder/'log').open('wb') as log:
            xenv=dict(os.environ)
            if args.xvfb_library_path:xenv['LD_LIBRARY_PATH']=args.xvfb_library_path
            x=subprocess.Popen([args.xvfb,'-displayfd','1','-screen','0','1200x800x24','-nolisten','tcp'],env=xenv,stdout=subprocess.PIPE,stderr=log)
            kitty=None;display_handle=None;lib=None
            try:
                assert x.stdout is not None
                if not select.select([x.stdout],[],[],5)[0]:raise RuntimeError('Xvfb readiness timed out')
                display=':'+x.stdout.readline().decode().strip()
                env=dict(os.environ,DISPLAY=display,WAYLAND_DISPLAY='',HOME=str(home),XDG_DATA_HOME=str(data),KITTY_CONFIG_DIRECTORY=str(config),ASTRO_ANIMATION='off',ASTRO_QA_ISOLATED='1',HISTFILE=str(folder/'history'),XDG_CACHE_HOME=str(folder/'cache'))
                socket='unix:'+str(folder/'kitty.sock')
                kitty=subprocess.Popen([args.kitty,'--config',str(config/'kitty.conf'),'--listen-on',socket,'--working-directory',str(cwd),'-o','startup_session=none','-o','allow_remote_control=yes','-o','remember_window_size=no','-o','initial_window_width=1200','-o','initial_window_height=800','-o','font_size=10'],env=env,stdout=log,stderr=log)
                def remote(*command):
                    result=subprocess.run([args.kitty,'@','--to',socket,*map(str,command)],env=env,capture_output=True,timeout=6)
                    if result.returncode:raise AssertionError(result.stderr.decode())
                    return result.stdout
                def wait_for(predicate,seconds=10):
                    end=time.monotonic()+seconds
                    while time.monotonic()<end:
                        if kitty.poll() is not None:raise AssertionError(f'Private Kitty exited: {kitty.returncode}')
                        result=predicate()
                        if result:return result
                        time.sleep(.04)
                    raise AssertionError('Private Kitty did not reach the expected state')
                wait_for(lambda:(folder/'kitty.sock').exists())
                def windows():return json.loads(remote('ls'))[0]['tabs'][0]['windows']
                wait_for(lambda:len(windows())==1 and windows()[0]['at_prompt'])
                first=windows()[0]['id']
                pointer=json.loads(remote('kitten',str(inspector),'--probe-pointer'))
                assert pointer=={'valid_pointer':True,'invalid_pointer':None},pointer
                second=int(remote('launch','--location=vsplit',f'--next-to=id:{first}','--cwd=current').strip())
                remote('launch','--location=hsplit',f'--next-to=id:{first}','--cwd=current')
                remote('launch','--location=hsplit',f'--next-to=id:{second}','--cwd=current')
                wait_for(lambda:len(windows())==4 and all(w['at_prompt'] for w in windows()))
                seeded=json.loads(remote('kitten',str(inspector),'--seed-pointer'))
                assert seeded['pointer_seeded']
                remote('action','load_config_file',str(config/'kitty.conf'))
                remote('kitten',str(config/'reload_pane_controls.py'))
                released=json.loads(remote('kitten',str(inspector),'--verify-pointer-release'))
                assert released['pointer_released']
                def inspect():return json.loads(remote('kitten','--match',f'id:{first}',str(inspector)))
                baseline=inspect();assert 'codex_below' not in baseline['buttons']
                original_pids={w['id']:w['pid'] for w in baseline['windows']}
                xid=json.loads(remote('ls'))[0]['platform_window_id']
                lib=C.CDLL('libX11.so.6');xt=C.CDLL('libXtst.so.6')
                lib.XOpenDisplay.argtypes=[C.c_char_p];lib.XOpenDisplay.restype=C.c_void_p
                lib.XDefaultRootWindow.argtypes=[C.c_void_p];lib.XDefaultRootWindow.restype=C.c_ulong
                lib.XTranslateCoordinates.argtypes=[C.c_void_p,C.c_ulong,C.c_ulong,C.c_int,C.c_int,C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_ulong)]
                lib.XSetInputFocus.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_ulong]
                lib.XStringToKeysym.argtypes=[C.c_char_p];lib.XStringToKeysym.restype=C.c_ulong
                lib.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];lib.XKeysymToKeycode.restype=C.c_ubyte
                lib.XSync.argtypes=[C.c_void_p,C.c_int];lib.XCloseDisplay.argtypes=[C.c_void_p]
                xt.XTestFakeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong]
                xt.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
                xt.XTestFakeKeyEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
                display_handle=lib.XOpenDisplay(display.encode());assert display_handle
                ox=C.c_int();oy=C.c_int();child=C.c_ulong()
                lib.XTranslateCoordinates(display_handle,xid,lib.XDefaultRootWindow(display_handle),0,0,C.byref(ox),C.byref(oy),C.byref(child))
                shift=lib.XKeysymToKeycode(display_handle,lib.XStringToKeysym(b'Shift_L'))
                lib.XSetInputFocus(display_handle,xid,1,0)
                def click(action,use_shift):
                    before=inspect();point=before['buttons'][action]
                    xt.XTestFakeMotionEvent(display_handle,0,ox.value+round(point['x']),oy.value+round(point['y']),0)
                    if use_shift:xt.XTestFakeKeyEvent(display_handle,shift,1,0)
                    xt.XTestFakeButtonEvent(display_handle,1,1,0)
                    if use_shift:xt.XTestFakeKeyEvent(display_handle,shift,0,0)
                    xt.XTestFakeButtonEvent(display_handle,1,0,0);lib.XSync(display_handle,0)
                    wait_for(lambda:len(windows())==len(before['windows'])+1)
                    wait_for(lambda:all(w['at_prompt'] for w in windows()))
                    after=inspect();prior={w['id'] for w in before['windows']}
                    added=next(w for w in after['windows'] if w['id'] not in prior)
                    assert Path(added['cwd']).resolve()==cwd.resolve()
                    assert all(any(w['id']==wid and w['pid']==pid for w in after['windows']) for wid,pid in original_pids.items())
                    if use_shift:
                        assert after['root']['one']==before['root']
                        assert after['root']['two']==added['id']
                        assert after['root'].get('horizontal',True)==(action=='add_right')
                        others=[w for w in after['windows'] if w['id']!=added['id']]
                        if action=='add_right':
                            assert abs(added['top']-min(w['top'] for w in others))<=20
                            assert abs(added['bottom']-max(w['bottom'] for w in others))<=20
                        else:
                            assert abs(added['left']-min(w['left'] for w in others))<=12
                            assert abs(added['right']-max(w['right'] for w in others))<=12
                    else:
                        source=next(w for w in before['windows'] if w['id']==first)
                        assert abs(added['top']-source['top'])<=20
                        assert abs(added['bottom']-source['bottom'])<=20
                        assert added['bottom']-added['top']<max(w['bottom'] for w in after['windows'])*.8
                click('add_right',True);click('add_below',True);click('add_right',False)
                print(json.dumps({'private_xvfb':True,'stale_xid_safe':True,'legacy_backend_released':True,'real_mouse_clicks':True,'shift_release_preserved':True,'full_span_layouts':True,'cwd_preserved':True,'existing_pids_preserved':True,'reload_preserved_panes':True},indent=2))
            except Exception:
                log.flush();print((folder/'log').read_text());raise
            finally:
                if display_handle and lib is not None:lib.XCloseDisplay(display_handle)
                for process in (kitty,x):
                    if process and process.poll() is None:
                        process.terminate()
                        try:process.wait(timeout=5)
                        except subprocess.TimeoutExpired:process.kill();process.wait()
                if x.stdout:x.stdout.close()


if __name__=='__main__':
    main()
