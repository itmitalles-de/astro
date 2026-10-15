#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ten small, CPU-only Astro greetings. No terminal dependencies or key reads."""
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

EFFECTS = ('First contact', 'Tabby rain', 'Constellation', 'Orbital cat',
           'Cat nap', 'Zoomies', 'Purr waves', 'Yarn physics',
           'Whisker radar', 'Stardust')
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


def frame(effect: int, t: float, width: int = 64, height: int = 24) -> list[str]:
    """Pure deterministic ASCII frame, clipped to any requested geometry."""
    width, height = max(1, width), max(1, height)
    grid = [[' '] * width for _ in range(height)]
    cx, cy = width / 2, height / 2

    def put(x: int, y: int, char: str) -> None:
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = char

    def text(x: int, y: int, value: str) -> None:
        for i, char in enumerate(value):
            put(x + i, y, char)

    def line(x0: float, y0: float, x1: float, y1: float) -> None:
        steps = max(1, int(max(abs(x1-x0), abs(y1-y0))))
        for i in range(steps + 1):
            put(round(x0+(x1-x0)*i/steps), round(y0+(y1-y0)*i/steps), '.')

    # Sparse, deterministic star field anchors every variant in the same world.
    rng = random.Random(920)
    for i in range(max(12, width * height // 70)):
        x, y = rng.randrange(width), rng.randrange(2, max(3, height-2))
        put(x, y, '+' if (i + int(t*4)) % 9 == 0 else '.')

    if effect == 1:  # Columns fall at independent speeds, not a random flicker.
        for x in range(1, width, 4):
            head = int(t*(5+x % 5)+x*3) % max(1, height-4) + 2
            for k in range(5):
                if 2 <= head-k < height-2:
                    put(x, head-k, '01:./'[int(t*6+x+k) % 5])
    elif effect == 2:
        points = [(cx+math.cos(i*1.12+t*.28)*(width*.43), cy+math.sin(i*1.12+t*.28)*(height*.36)) for i in range(7)]
        for a, b in zip(points, points[1:] + points[:1]):
            line(*a, *b)
        for x, y in points:
            put(round(x), round(y), '*')
    elif effect == 3:
        for ring in range(3):
            for j in range(52):
                angle = j*math.tau/52 + t*(.6 if ring % 2 else -.6)
                x = round(cx+math.cos(angle)*(17+ring*4))
                y = round(cy+math.sin(angle)*(5+ring*2))
                put(x, y, 'o' if j == int(t*10+ring*8) % 52 else '.')
    elif effect == 6:
        for y in range(2, height-2):
            for x in range(width):
                radius = math.hypot((x-cx)*.5, y-cy)
                phase = (radius-t*6) % 5
                if phase < .20:
                    put(x, y, '~')
    elif effect == 8:
        angle = t*2.6
        for r in range(3, max(width, height)):
            put(round(cx+math.cos(angle)*r), round(cy+math.sin(angle)*r*.4), ':')
        for r in [9, 16, 23]:
            for j in range(60):
                a = j*math.tau/60
                put(round(cx+math.cos(a)*r), round(cy+math.sin(a)*r*.4), '.')

    portrait = RUNNER if effect == 5 else CAT
    art_width = max(map(len, portrait))
    left = (width-art_width)//2
    top = max(2, (height-len(portrait))//2)
    if effect == 5:
        left = round((math.sin(t*3.4)+1)*max(0, width-art_width)/2)
        top = max(3, height//2-2) + int(math.sin(t*15) > 0)
        for i in range(3):
            text(max(0, left-6-i*3), top+2+i % 2, '--')
    elif effect == 4:
        top += int(math.sin(t*3) > .5)
        text(left+art_width-1, max(2, top-1), 'z Z' if int(t*3) % 2 else 'Z z')
    elif effect == 7:
        ball_x = round(cx+math.sin(t*4)*(width*.32))
        ball_y = min(height-4, top+len(portrait)-1)
        line(cx, cy+3, ball_x, ball_y)
        text(ball_x, ball_y, '(@)')
    # Clear a quiet silhouette around the portrait for readable fur/whiskers.
    for y in range(top-1, top+len(portrait)+1):
        for x in range(left-1, left+art_width+1):
            put(x, y, ' ')
    for y, row in enumerate(portrait):
        for x, char in enumerate(row):
            if effect in (0, 4) and char == '@' and (effect == 4 or .42 < t % 1.4 < .68):
                char = '-'
            if effect == 9 and char != ' ':
                # Letter-shaped stardust assembles from left to right.
                progress = min(1.0, max(0.0, t/.9))
                threshold = random.Random(y*73+x*19).random()
                if threshold > progress:
                    drift = round((1-progress)*(threshold*12-6))
                    put(left+x+drift, top+y-int((1-progress)*4), '.')
                    continue
            put(left+x, top+y, char)
    if effect == 7:
        ball_x = round(cx+math.sin(t*4)*(width*.32))
        ball_y = min(height-4, top+len(portrait))
        text(ball_x-1, ball_y, '(@)')
    # Frame typography is quiet; the mascot carries the identity.
    for y in [0, height-1]:
        grid[y] = [' '] * width
    label = f' A S T R O  /  {effect+1:02d} '
    text(max(0, (width-len(label))//2), 0, label)
    footer = EFFECTS[effect] + '  /  ready when you are'
    if len(footer) > width:
        footer = EFFECTS[effect]
    text(max(0, (width-len(footer))//2), height-1, footer)
    return [''.join(row) for row in grid]


# Paper/blue chrome follows the terminal; the cat retains its fur and eye colors.
COLORS = {'fur': '189;165;133', 'cream': '216;212;206', 'eye': '184;187;106',
          'nose': '211;134;155', 'dim': '153;150;143', 'sky': '99;168;248'}


def ansi_frame(rows: list[str], colors: bool = True) -> str:
    """Paint complete rows without scrolling, leaving the last column alone."""
    output = []
    for y, row in enumerate(rows):
        output.append(f'\x1b[{y+1};1H')
        previous = None
        is_label = 'A S T R O' in row or any(name in row for name in EFFECTS)
        for char in row:
            role = ('cream' if is_label else
                    'eye' if char == '@' else 'nose' if char in 'vY' else
                    'sky' if char in '*+o' else 'dim' if char in '.:01~' else
                    'fur' if char in '/\\^M' else 'cream')
            if colors and role != previous:
                output.append(f'\x1b[38;2;{COLORS[role]}m')
                previous = role
            output.append(char)
    return ''.join(output) + ('\x1b[0m' if colors else '')


def play(effect: int, duration: float = 1.25) -> None:
    """Return immediately on input, preserving every byte for the next shell."""
    if not sys.stdin.isatty() or not sys.stdout.isatty() or os.environ.get('TERM') == 'dumb':
        return
    size = os.get_terminal_size(sys.stdout.fileno())
    if size.columns < 34 or size.lines < 16:
        return
    old = termios.tcgetattr(sys.stdin.fileno())
    settings = termios.tcgetattr(sys.stdin.fileno())
    settings[3] &= ~(termios.ICANON | termios.ECHO)
    # Disable ISIG temporarily too: Ctrl+C is queued for the shell, not lost.
    settings[3] &= ~termios.ISIG
    settings[6][termios.VMIN], settings[6][termios.VTIME] = 1, 0
    old_handlers = {}
    def interrupted(signum, _frame):
        raise InterruptedError
    try:
        for sig in (signal.SIGTERM, signal.SIGHUP):
            old_handlers[sig] = signal.signal(sig, interrupted)
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, settings)
        sys.stdout.write('\x1b[?1049h\x1b[?25l\x1b[?7l')
        started = time.monotonic()
        while (elapsed := time.monotonic()-started) < duration:
            if select.select([sys.stdin], [], [], 0)[0]:
                break
            size = os.get_terminal_size(sys.stdout.fileno())
            if size.columns < 34 or size.lines < 16:
                break
            # At most 80 x 26 characters, centered in large terminals.
            width, height = min(80, size.columns-1), min(26, size.lines-1)
            rows = frame(effect, elapsed, width, height)
            # Use a centered viewport rather than filling a large monitor.
            canvas = [' '*max(0, (size.columns-width)//2)+row for row in rows]
            prefix = ['']*max(0, (size.lines-height)//2)
            sys.stdout.write(ansi_frame(prefix+canvas, 'NO_COLOR' not in os.environ))
            sys.stdout.flush()
            select.select([sys.stdin], [], [], 1/16)
    except (InterruptedError, KeyboardInterrupt, OSError):
        pass
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, old)
        sys.stdout.write('\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l')
        sys.stdout.flush()
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


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
    try:
        cache = Path(os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache')/'astro'
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (cache/'intro-cycle.json').open('a+', encoding='utf-8') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--effect', type=int, choices=range(1, 11))
    parser.add_argument('--duration', type=float, default=1.25)
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    if args.list:
        for i, name in enumerate(EFFECTS, 1):
            print(f'{i:02d}  {name}')
        return
    if os.environ.get('ASTRO_ANIMATION', '').lower() in ('off', '0', 'false') or os.environ.get('REDUCE_MOTION') == '1':
        return
    # Non-interactive commands must have no terminal output or cache side effects.
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return
    size = os.get_terminal_size(sys.stdout.fileno())
    if size.columns < 34 or size.lines < 16:
        return
    effect = args.effect-1 if args.effect else choose_effect()
    play(effect, min(10.0, max(0.0, args.duration)))


if __name__ == '__main__':
    main()
