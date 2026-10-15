# SPDX-License-Identifier: GPL-3.0-or-later
# Sourced by the managed .bashrc block; never wrap or replace Kitty's shell.
if [[ $- == *i* && -n ${KITTY_WINDOW_ID-} && ${ASTRO_GREETED_WINDOW-} != "$KITTY_WINDOW_ID" ]]; then
    # Descendant shells skip the same greeting; newly created panes have a new id.
    export ASTRO_GREETED_WINDOW=$KITTY_WINDOW_ID
    _astro_intro=${KITTY_CONFIG_DIRECTORY:-${XDG_CONFIG_HOME:-$HOME/.config}/kitty}/astro_intro.py
    if [[ -r $_astro_intro ]] && command -v python3 >/dev/null 2>&1; then
        command python3 "$_astro_intro"
    fi
    unset _astro_intro
fi
