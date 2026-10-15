#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install one scoped Bash source block, preserving user settings and symlinks."""
from pathlib import Path
import argparse
import os
import shutil
import stat
import sys
import tempfile

BEGIN = '# >>> Astro greeting >>>'
END = '# <<< Astro greeting <<<'
BLOCK = '''# >>> Astro greeting >>>
# Only Kitty panes source Astro; other terminals are unchanged.
if [[ -n ${KITTY_WINDOW_ID-} ]]; then
    _astro_hook=${KITTY_CONFIG_DIRECTORY:-${XDG_CONFIG_HOME:-$HOME/.config}/kitty}/astro.bash
    [[ ! -r $_astro_hook ]] || source "$_astro_hook"
    unset _astro_hook
fi
# <<< Astro greeting <<<
'''


def render_hook(content: str) -> str:
    lines = content.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip('\r\n') == BEGIN]
    ends = [i for i, line in enumerate(lines) if line.rstrip('\r\n') == END]
    if not starts and not ends:
        separator = '' if not content or content.endswith('\n\n') else '\n'
        return content + separator + BLOCK
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError('Ambiguous Astro hook markers; refusing to alter bashrc')
    return ''.join(lines[:starts[0]]) + BLOCK + ''.join(lines[ends[0]+1:])


def hook_update(bashrc: Path) -> tuple[str, str]:
    # Read without universal-newline translation: preserve unrelated CRLF text.
    if bashrc.exists():
        with bashrc.open(encoding='utf-8', newline='') as handle:
            content = handle.read()
    else:
        content = ''
    updated = render_hook(content)
    if updated != content:
        target = bashrc.resolve()
        parent = target.parent
        while True:
            try:
                parent.stat()
                break
            except FileNotFoundError:
                parent = parent.parent
        if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
            raise PermissionError(f'Cannot atomically update Bash hook in {target.parent}')
        if target.exists() and not os.access(target, os.W_OK):
            raise PermissionError(f'Bash hook target is read-only: {target}')
    return content, updated


def install_hook(bashrc: Path, backup: Path) -> None:
    content, updated = hook_update(bashrc)
    if updated == content:
        return
    # Replace the resolved target, not a managed-dotfile symlink itself.
    target = bashrc.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=f'.{target.name}.astro-', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='validate without writing')
    parser.add_argument('bashrc', type=Path)
    parser.add_argument('backup', type=Path, nargs='?')
    args = parser.parse_args()
    if not args.check and args.backup is None:
        parser.error('backup path is required unless --check is used')
    try:
        if args.check:
            hook_update(args.bashrc)
        else:
            install_hook(args.bashrc, args.backup)
    except (OSError, ValueError) as error:
        print(f'Error: {error}', file=sys.stderr)
        raise SystemExit(1) from error
