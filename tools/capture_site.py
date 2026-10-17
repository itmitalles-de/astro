#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture real Astro on a private Xvfb with labeled, sanitized example content."""
import argparse
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import time
import select

ROOT=Path(__file__).resolve().parents[1]


def main():
    from PIL import ImageGrab
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xvfb',default=shutil.which('Xvfb'))
    parser.add_argument('--kitty',default=shutil.which('kitty'))
    parser.add_argument('--output',type=Path,default=ROOT/'site/assets/workspace.png')
    parser.add_argument('--evidence',type=Path)
    args=parser.parse_args()
    if not args.xvfb or not args.kitty:parser.error('Kitty, Xvfb and Pillow with XCB support are required')
    with tempfile.TemporaryDirectory(prefix='astro-site-capture-') as folder:
        folder=Path(folder);home=folder/'home';home.mkdir()
        config=folder/'config';shutil.copytree(ROOT/'config',config)
        data=folder/'data';fonts=data/'fonts/astro';fonts.mkdir(parents=True)
        shutil.copy2(ROOT/'fonts/AstroPaneControls.ttf',fonts/'AstroPaneControls.ttf')
        project=home/'projects/stardust';project.mkdir(parents=True)
        (home/'.bashrc').write_text('source "$KITTY_CONFIG_DIRECTORY/astro.bash"\nPS1=${PS1//\\\\u/astro}\nPS1=${PS1//\\\\h/linux}\n')
        (home/'.profile').write_text('[ ! -r "$HOME/.bashrc" ] || . "$HOME/.bashrc"\n')
        (project/'README.md').write_text('# stardust\n\nA small place for big ideas.\n\nThis is an example workspace,\nrendered in the real Astro terminal.\n\n- your shell\n- your projects\n- a little company\n')
        (project/'notes.md').write_text('A few things to make.\n')
        subprocess.run(['git','-c','init.defaultBranch=main','init','--quiet',str(project)],check=True)
        subprocess.run(['git','add','.'],cwd=project,check=True)
        subprocess.run(['git','-c','user.name=Astro Demo','-c','user.email=demo@example.invalid','-c','commit.gpgsign=false','-c','core.hooksPath=/dev/null','commit','--quiet','-m','Example workspace'],cwd=project,check=True)
        (project/'notes.md').write_text('A few things to make.\nRoom for the next idea.\n')
        (project/'ideas.txt').write_text('Leave room to think.\n')
        with (folder/'capture.log').open('wb') as log:
            x=subprocess.Popen([args.xvfb,'-displayfd','1','-screen','0','1440x760x24','-nolisten','tcp'],stdout=subprocess.PIPE,stderr=log)
            kitty=None
            try:
                assert x.stdout is not None
                if not select.select([x.stdout],[],[],5)[0]:raise RuntimeError('Private Xvfb did not start')
                display=':'+x.stdout.readline().decode().strip()
                env=dict(os.environ,HOME=str(home),DISPLAY=display,WAYLAND_DISPLAY='',XDG_DATA_HOME=str(data),XDG_CACHE_HOME=str(folder/'cache'),KITTY_CONFIG_DIRECTORY=str(config),ASTRO_ANIMATION='off',ASTRO_QA_ISOLATED='1',HISTFILE=str(folder/'history'))
                socket='unix:'+str(folder/'kitty.sock')
                kitty=subprocess.Popen([args.kitty,'--config',str(config/'kitty.conf'),'--listen-on',socket,'--working-directory',str(project),'-o','startup_session=none','-o','allow_remote_control=socket-only','-o','remember_window_size=no','-o','initial_window_width=1440','-o','initial_window_height=760','-o','font_size=12','-o','background_opacity=1','-o','hide_window_decorations=yes'],env=env,stdout=log,stderr=log)
                def remote(*command):
                    result=subprocess.run([args.kitty,'@','--to',socket,*map(str,command)],env=env,capture_output=True,timeout=8)
                    if result.returncode:raise RuntimeError(result.stderr.decode())
                    return result.stdout
                def until(predicate,seconds=12):
                    end=time.monotonic()+seconds
                    while time.monotonic()<end:
                        if kitty.poll() is not None:raise RuntimeError('Private Kitty exited')
                        value=predicate()
                        if value:return value
                        time.sleep(.05)
                    raise RuntimeError('Timed out waiting for private capture state')
                until(lambda:(folder/'kitty.sock').exists())
                def windows():return json.loads(remote('ls'))[0]['tabs'][0]['windows']
                until(lambda:len(windows())==1 and windows()[0]['at_prompt'])
                first=windows()[0]['id']
                second=int(remote('launch','--location=vsplit',f'--next-to=id:{first}','--cwd=current').strip())
                third=int(remote('launch','--location=hsplit',f'--next-to=id:{second}','--cwd=current').strip())
                until(lambda:len(windows())==3 and all(w['at_prompt'] for w in windows()))
                for wid in (first,second,third):remote('kitten','--match',f'id:{wid}',str(ROOT/'tools/qa_inspect.py'))
                remote('send-text','--match',f'id:{first}','cat README.md\r')
                remote('send-text','--match',f'id:{second}','git -c color.ui=always status --short\r')
                remote('send-text','--match',f'id:{third}','env ASTRO_ANIMATION=on REDUCE_MOTION=0 python3 "$KITTY_CONFIG_DIRECTORY/astro_intro.py" --effect 6 --duration 10\r')
                runner=runpy.run_path(str(ROOT/'config/astro_intro.py'))['RUNNER']
                def complete_cat():
                    text=remote('get-text','--match',f'id:{third}').decode()
                    return all(row.rstrip() in text for row in runner)
                until(complete_cat,seconds=8)
                # Exclude personal identity: the only prompt substitutions are display labels.
                content=[remote('get-text','--match',f'id:{wid}').decode() for wid in (first,second)]
                assert all('astro@linux' in text for text in content),content
                assert all(str(Path.home()) not in text and str(folder) not in text for text in content)
                image=ImageGrab.grab(xdisplay=display)
                assert image.size==(1440,760)
                args.output.parent.mkdir(parents=True,exist_ok=True);image.save(args.output)
                evidence={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'native_kitty':subprocess.check_output([args.kitty,'--version'],text=True).strip(),'dimensions':list(image.size),'capture':'Pillow XCB, private Xvfb, no post-processing','content':'Sanitized example project; actual cat README.md, Git status and built-in Zoomies preview. No agents launched.','owner_desktop_touched':False,'output':str(args.output)}
                if args.evidence:args.evidence.write_text(json.dumps(evidence,indent=2))
                print(json.dumps(evidence,indent=2))
            except Exception:
                log.flush();print((folder/'capture.log').read_text());raise
            finally:
                for process in (kitty,x):
                    if process and process.poll() is None:
                        process.terminate()
                        try:process.wait(timeout=5)
                        except subprocess.TimeoutExpired:process.kill();process.wait()
                if x.stdout:x.stdout.close()


if __name__=='__main__':
    main()
