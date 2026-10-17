#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ten CPU-only Astro cat actions; greet until typing without consuming input."""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import random
import select
import signal
import sys
import termios
import time

EFFECTS = ('First contact', 'Cursor hunt', 'Star jump', 'Tail chase',
           'Cat nap', 'Zoomies', 'Grooming', 'Yarn physics',
           'Box inspector', 'Window watch')
# Keep the reference portrait and the original, owner-liked Zoomies sprite.
CAT = (
    r'      /\             /\      ',
    r'     /^^\__..M..__/^^\     ',
    r'    / .  / /|\ \  . \    ',
    r'   /_/__/   |   \__\_\   ',
    r'   |   ----     _@_/   |   ',
    r'  /    .     v     .    \  ',
    r' /  ===\  ._ Y _.  /===  \ ',
    r'<  -----\__ \|/ __/-----  >',
    r' \___    /  ---  \    ___/ ',
    r'    \_/ /   |||   \ \_/   ',
    r'      \/   /|||\   \/     ',
    r'       \__/ ||| \__/      ',
    r'          \_|||_/         ',
)
RUNNER = (r'    /\_/\                 ', r'   ( -.@ )___             ',
          r'   / >v<     `-.          ', r'  /     ___     \____     ',
          r' (_____/   \_____)   `~~   ')


def _pose(value: str) -> tuple[str, ...]:
    return tuple(value.strip('\n').splitlines())


# Each action has its own silhouette and articulated poses. Never mirror a pose:
# the only open green eye is always on the image-right of Astro's face.
SCENES = (
    (_pose(r'''
     /\_/\
    ( -.@ )
     > v <
    /|   |\
   / | M | \
  (_/|___|\_)
     /   \
    (_) (_)
'''), _pose(r'''
     /\_/\
    ( -.@ )  /
     > v < _/
    /|   |/
   / | M |
  (_/|___|_
     /   \
    (_) (_)
'''), _pose(r'''
     /\_/\
    ( -.@ )
     > v <
    /|   |\
   / | M | \_
  (_/|___|   _)
     /   \
    (_) (_)
''')),
    (_pose(r'''
      /\_/\
     ( -.@ )____
    _/ >v<  ___ `-.
   /__  __ /   \___)~~
      \/  \/
'''), _pose(r'''
      /\_/\
     ( -.@ )____
   __/ >v<  ___ `-.
  (__    __/   \___)~~
      \_/
'''), _pose(r'''
      /\_/\
     ( -.@ )____
    _/ >v<  ___ `-.  ~
   (__   _/    \___)~
      \_/ \
''')),
    (_pose(r'''
        /\_/\
       ( -.@ )
     __/>v<  \__
    /   /M\     \
   (_/ /   \ \___)~~
      (_) (_)
'''), _pose(r'''
         /\_/\
        ( -.@ )
    ___/ >v<   \___
   (_   / M \      _)~
     \_/     \____/~~
'''), _pose(r'''
        /\_/\
       ( -.@ )
      / >v<  \___
    _/  /M\      \
   (__/     \___ _)~~
                \_)
''')),
    (_pose(r'''
       /\_/\
      ( -.@ )
       > v <
      /| M |\
     ( |   | )
      \|___|/   __
      (_) (_)__(_ )
'''), _pose(r'''
       /\_/\
      ( -.@ )
       > v <
      /| M |\    __
     ( |   | )  (_ )
      \|___|/____/
      (_) (_)
'''), _pose(r'''
       /\_/\
      ( -.@ )
       > v <   ___
      /| M |\ (_  )
     ( |   | ) / /
      \|___|/__/
      (_) (_)
''')),
    (_pose(r'''
       /\_/\
    __( -.- )___
  .'   >v<   M  `.
 /    .------.    \
(____(________)____)~~
'''), _pose(r'''
       /\_/\
    __( -.- )___
  .'   >v<   M  `.
 /    .-------.   \
(____(_________)___)~
''')),
    (RUNNER, _pose(r'''
    /\_/\
   ( -.@ )___
   / >v<     `-.
  /  __     __  \____
 (__/  \___/  \__)   `~
''')),
    (_pose(r'''
       /\_/\
      ( -.@ )
       > v <
      /| M |\
     (_|   | )
       |___|/___
       (_) (_)__)
'''), _pose(r'''
       /\_/\
      ( -.@ )
       > v <_
      /| M /_)
     (_|   |/
       |___|/___
       (_) (_)__)
'''), _pose(r'''
       /\_/\
      ( -.@ )
       > v /_)
      /| M |/
     (_|   |
       |___|/___
       (_) (_)__)
''')),
    (_pose(r'''
      _       _
     (_)     (_)
       \ /M\ /
     /\_\   /_/\
    (   -.@     )
     \__>v<___/~~
'''), _pose(r'''
          _
         (_)
      _ / M\__
     (_)    __)\
     /\_\   /_/\
    (   -.@     )
     \__>v<___/~~
'''), _pose(r'''
      _
     (_)
      \__ /M\ _
       (_\   (_)
     /\_\   /_/\
    (   -.@     )
     \__>v<___/~~
''')),
    (_pose(r'''
        /\_/\
       ( -.@ )
    ___/>v< \___
   /  (_)  (_)  /|
  +------------+ |
  |   ASTRO    | /
  +------------+
'''), _pose(r'''
         /\_/\
        ( -.@ )
    ____/>v<\___
   /   (_) (_)  /|
  +------------+ |
  |   ASTRO    | /
  +------------+
'''), _pose(r'''

        /\_/\
    ___( -.@ )__
   /    >v<     /|
  +------------+ |
  |   ASTRO    | /
  +------------+
''')),
    (_pose(r'''
        /\_/\
       ( -.@ )
        > v <
       /| M |\
      ( |   | )
       \|___|/___
       (_) (_)___)
'''), _pose(r'''
         /\_/\
        ( -.@ )
         > v <
       /| M |\
      ( |   | )
       \|___|/____
       (_) (_)____)
''')),
)


def frame(effect: int, t: float, width: int = 64, height: int = 24) -> list[str]:
    """Render an actual looping cat action, not a recolored portrait backdrop."""
    width, height = max(1, width), max(1, height)
    grid = [[' '] * width for _ in range(height)]

    def put(x: int, y: int, char: str) -> None:
        if 0 <= x < width and 1 <= y < height-1:
            grid[y][x] = char

    def text(x: int, y: int, value: str) -> None:
        for i, char in enumerate(value):
            put(x+i, y, char)

    def line(x0: int, y0: int, x1: int, y1: int) -> None:
        steps = max(1, abs(x1-x0), abs(y1-y0))
        for i in range(steps+1):
            put(round(x0+(x1-x0)*i/steps), round(y0+(y1-y0)*i/steps), '.')

    phase = t % 8.0
    poses = SCENES[effect]
    pose_index = int(t*(10 if effect == 5 else 3)) % len(poses)
    portrait = poses[pose_index]
    art_width = max(map(len, portrait))
    left = (width-art_width)//2
    ground = max(3, height-5)
    top = max(2, ground-len(portrait))

    # A restrained stage: almost all movement belongs to Astro and his props.
    if effect not in (2,9):
        text(max(0,width//2-15),ground, '_'*min(30,width))
    if effect == 0:
        if phase < 2:
            left = round(-art_width+(width+art_width)/2*(phase/2))
        elif phase > 6:
            left += round((width+art_width)/2*((phase-6)/2))
        if 2 < phase < 6:
            text(min(width-7,left+art_width+1),max(2,top+1),'mrrp?')
    elif effect == 1:
        mouse_x=round(width*.68+math.sin(t*1.8)*width*.16)
        left=max(0,min(width-art_width,mouse_x-art_width-3))
        top+=int(math.sin(t*5)>0)
        text(mouse_x,ground-1,'+_')
        if pose_index==1:
            text(min(width-4,mouse_x+2),ground-2,'!')
    elif effect == 2:
        jump=max(0.0,math.sin(t*2.0))
        top=max(2,top-round(jump*min(7,height*.3)))
        left=max(0,min(width-art_width,left+round(math.sin(t)*width*.12)))
        text(width//2-1,2,'*')
        text(width//2-5,3,'.   .')
        text(max(0,width//2-14),ground,'____'+' '*20+'____')
        if jump>.75:
            text(min(width-2,left+art_width),top+2,'*')
    elif effect == 3:
        left+=round(math.sin(t*3)*2)
        if pose_index==2:
            text(min(width-4,left+art_width),top+2,'?!')
        text(max(0,left-4),ground-1,'..' if int(t*5)%2 else ' .')
    elif effect == 4:
        # Breathing changes the curled silhouette; the sleep letters rise away.
        rise=int(t*2)%4
        text(left+art_width-3,max(2,top-1-rise),'z' if rise<2 else 'Z')
        text(left+art_width+1,max(2,top-2),'z')
    elif effect == 5:
        # Retain the original Zoomies timing, movement and recognizable sprite.
        left=round((math.sin(t*3.4)+1)*max(0,width-art_width)/2)
        top=max(3,height//2-2)+int(math.sin(t*15)>0)
        ground=min(height-3,height//2+5)
        for i in range(3):
            text(max(0,left-6-i*3),top+2+i%2,'--')
        text(max(0,width//2-15),ground,'_'*min(30,width))
    elif effect == 6:
        top+=int(math.sin(t*2.6)>.8)
        if pose_index==2:
            text(min(width-3,left+art_width+1),top+1,'*')
    elif effect == 7:
        ball_x=round(width/2+math.sin(t*2.7)*min(13,width*.3))
        ball_y=max(2,top-2-round(abs(math.sin(t*2.7))*4))
        line(left+art_width//2,top,ball_x,ball_y)
        text(ball_x-1,ball_y,'(O)')
    elif effect == 8:
        if pose_index==2:
            text(left+art_width+1,top+2,'?')
        else:
            text(left-3,ground-1,'~' if int(t*4)%2 else '-')
    elif effect == 9:
        window_left=max(0,width//2-15)
        window_right=min(width-1,width//2+15)
        for y in range(2,ground+1):
            put(window_left,y,'|'); put(window_right,y,'|')
        text(window_left,2,'+'+'-'*max(0,window_right-window_left-1)+'+')
        text(window_left,ground,'='*(window_right-window_left+1))
        text(window_left+1,6,'-'*max(0,window_right-window_left-1))
        bird_x=round(window_left+3+(math.sin(t*1.2)+1)*max(1,window_right-window_left-7)/2)
        text(bird_x,4,'v' if int(t*5)%2 else '~')

    # Blank only the sprite's own rectangle before painting it over the stage.
    for y,row in enumerate(portrait):
        for x in range(art_width):
            put(left+x,top+y,row[x] if x<len(row) else ' ')
    label=f' A S T R O  /  {effect+1:02d} '
    footer=EFFECTS[effect]+'  /  type to begin'
    if len(footer)>width:
        footer=EFFECTS[effect]
    for y,value in ((0,label),(height-1,footer)):
        value=value[:width]
        x=max(0,(width-len(value))//2)
        for i,char in enumerate(value):
            grid[y][x+i]=char
    return [''.join(row) for row in grid]


# GNOME text/accents follow the terminal; the cat retains its fur and eye colors.
COLORS = {'fur': '189;165;133', 'cream': '208;207;204', 'eye': '184;187;106',
          'nose': '211;134;155', 'dim': '94;92;100', 'sky': '42;123;222'}


def ansi_frame(rows: list[str], colors: bool = True, previous: list[str] | None = None) -> str:
    """Paint only changed rows; unchanged labels and empty space cost no output."""
    output=[]
    for y,row in enumerate(rows):
        if previous is not None and y<len(previous) and row==previous[y]:
            continue
        output.append(f'\x1b[{y+1};1H')
        prior_role=None
        is_label='A S T R O' in row or any(name in row for name in EFFECTS)
        for char in row:
            role=('cream' if is_label else
                  'eye' if char=='@' else 'nose' if char in 'vY' else
                  'sky' if char in '*+oO' else 'dim' if char in '.:01~' else
                  'fur' if char in '/\\^M' else 'cream')
            if colors and role!=prior_role:
                output.append(f'\x1b[38;2;{COLORS[role]}m')
                prior_role=role
            output.append(char)
    return ''.join(output)+('\x1b[0m' if colors and output else '')


def play(effect: int, duration: float | None = None) -> None:
    """Loop until input; observe readability without consuming the first byte."""
    if not sys.stdin.isatty() or not sys.stdout.isatty() or os.environ.get('TERM')=='dumb':
        return
    size=os.get_terminal_size(sys.stdout.fileno())
    if size.columns<34 or size.lines<16:
        return
    old=termios.tcgetattr(sys.stdin.fileno())
    settings=termios.tcgetattr(sys.stdin.fileno())
    settings[3]&=~(termios.ICANON|termios.ECHO|termios.ISIG)
    settings[6][termios.VMIN],settings[6][termios.VTIME]=1,0
    old_handlers={}
    def interrupted(signum,_frame):
        raise InterruptedError
    try:
        for sig in (signal.SIGTERM,signal.SIGHUP):
            old_handlers[sig]=signal.signal(sig,interrupted)
        termios.tcsetattr(sys.stdin.fileno(),termios.TCSANOW,settings)
        sys.stdout.write('\x1b[?1049h\x1b[?25l\x1b[?7l')
        started=time.monotonic()
        previous=None
        geometry=None
        while duration is None or time.monotonic()-started<duration:
            if select.select([sys.stdin],[],[],0)[0]:
                break
            size=os.get_terminal_size(sys.stdout.fileno())
            if size.columns<34 or size.lines<16:
                break
            width,height=min(80,size.columns-1),min(26,size.lines-1)
            if geometry!=size:
                sys.stdout.write('\x1b[2J')
                previous=None
                geometry=size
            rows=frame(effect,time.monotonic()-started,width,height)
            canvas=[' '*max(0,(size.columns-width)//2)+row for row in rows]
            canvas=['']*max(0,(size.lines-height)//2)+canvas
            sys.stdout.write(ansi_frame(canvas,'NO_COLOR' not in os.environ,previous))
            sys.stdout.flush()
            previous=canvas
            select.select([sys.stdin],[],[],1/12)
    except (InterruptedError,KeyboardInterrupt,OSError):
        pass
    finally:
        termios.tcsetattr(sys.stdin.fileno(),termios.TCSANOW,old)
        sys.stdout.write('\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l')
        sys.stdout.flush()
        for sig,handler in old_handlers.items():
            signal.signal(sig,handler)


def next_effect(state: object, rng: random.Random) -> tuple[int, dict]:
    """Use every effect once per shuffled bag, without mutating stored state."""
    order = state.get('order') if isinstance(state, dict) else None
    cursor = state.get('cursor') if isinstance(state, dict) else None
    valid = (isinstance(order, list) and len(order) == 10 and
             all(type(value) is int for value in order) and
             sorted(order) == list(range(10)) and type(cursor) is int and
             0 <= cursor <= 10)
    previous = None
    if valid:
        assert isinstance(order, list) and type(cursor) is int
        order = order.copy()
        if cursor == 10:
            previous = order[-1]
    else:
        order, cursor = list(range(10)), 10
    if cursor == 10:
        order, cursor = list(range(10)), 0
        rng.shuffle(order)
        if order[0] == previous:
            order[0], order[1] = order[1], order[0]
    return order[cursor], {'order': order, 'cursor': cursor+1}


def choose_effect() -> int:
    """Serialize simultaneous pane starts; recover from corrupt/read-only cache."""
    import fcntl
    import json
    import stat
    try:
        cache = Path(os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache')/'astro'
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(cache/'intro-cycle.json', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'r+', encoding='utf-8') as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return random.randrange(10)
            deadline = time.monotonic() + .2
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        return random.randrange(10)
                    time.sleep(.005)
            handle.seek(0)
            try:
                state = json.loads(handle.read(8192))
            except ValueError:
                state = {}
            effect, state = next_effect(state, random.SystemRandom())
            handle.seek(0)
            handle.truncate()
            json.dump(state, handle)
            handle.flush()
            return effect
    except OSError:
        return random.randrange(10)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--effect',type=int,choices=range(1,11))
    parser.add_argument('--duration',type=float,default=None,help='Optional finite preview; default waits for typing')
    parser.add_argument('--list',action='store_true')
    args=parser.parse_args()
    if args.list:
        for i,name in enumerate(EFFECTS,1):
            print(f'{i:02d}  {name}')
        return
    if os.environ.get('ASTRO_ANIMATION','').lower() in ('off','0','false') or os.environ.get('REDUCE_MOTION')=='1':
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty() or os.environ.get('TERM')=='dumb':
        return
    size=os.get_terminal_size(sys.stdout.fileno())
    if size.columns<34 or size.lines<16:
        return
    effect=args.effect-1 if args.effect else choose_effect()
    duration=None if args.duration is None else min(10.0,max(0.0,args.duration))
    play(effect,duration)


if __name__=='__main__':
    main()
