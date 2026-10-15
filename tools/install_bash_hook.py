#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install one scoped Bash source block, preserving user settings and symlinks."""
from pathlib import Path
import shutil
import sys

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


def install_hook(bashrc: Path, backup: Path) -> None:
    content = bashrc.read_text() if bashrc.exists() else ''
    if BEGIN in content or END in content:
        if content.count(BEGIN) != 1 or content.count(END) != 1:
            raise ValueError('Ambiguous Astro hook markers; refusing to alter bashrc')
        start = content.index(BEGIN)
        stop = content.index(END, start) + len(END)
        if content[stop:stop+1] == '\n':
            stop += 1
        updated = content[:start] + BLOCK + content[stop:]
    else:
        updated = content + ('\n' if content and not content.endswith('\n\n') else '') + BLOCK
    if updated == content:
        return
    if bashrc.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bashrc, backup)
    bashrc.parent.mkdir(parents=True, exist_ok=True)
    # Open the existing path so a managed dotfile symlink stays a symlink.
    with bashrc.open('w') as handle:
        handle.write(updated)


if __name__ == '__main__':
    install_hook(Path(sys.argv[1]), Path(sys.argv[2]))
