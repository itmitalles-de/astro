# SPDX-License-Identifier: GPL-3.0-or-later
# Sourced by the managed .bashrc block; never wrap or replace Kitty's shell.
# Reapply the prompt to descendant shells too; only the greeting is once/pane.
if [[ $- == *i* && -n ${KITTY_WINDOW_ID-} ]]; then
    _astro_prompt=${KITTY_CONFIG_DIRECTORY:-${XDG_CONFIG_HOME:-$HOME/.config}/kitty}/astro_prompt.bash
    # The configured path is runtime-specific, rather than a static source file.
    # shellcheck disable=SC1090
    [[ ! -r $_astro_prompt ]] || source "$_astro_prompt"
    unset _astro_prompt
    # Capability-enabled tools such as nvtop (cap_perfmon) ignore user TERMINFO
    # in glibc AT_SECURE mode and fail when xterm-kitty is only in Kitty's bundle.
    if [[ ${TERM-} == xterm-kitty ]] && ! declare -F nvtop >/dev/null && ! alias nvtop >/dev/null 2>&1; then
        nvtop() { TERM=xterm-256color command nvtop "$@"; }
    fi
fi
if [[ $- == *i* && -z ${BASH_EXECUTION_STRING-} && -n ${KITTY_WINDOW_ID-} && ${ASTRO_GREETED_WINDOW-} != "$KITTY_WINDOW_ID" ]]; then
    # bash -ic command panes must start their agent/monitor without waiting.
    # Descendant shells skip the same greeting; newly created panes have a new id.
    export ASTRO_GREETED_WINDOW=$KITTY_WINDOW_ID
    _astro_intro=${KITTY_CONFIG_DIRECTORY:-${XDG_CONFIG_HOME:-$HOME/.config}/kitty}/astro_intro.py
    if [[ -r $_astro_intro ]] && command -v python3 >/dev/null 2>&1; then
        command python3 "$_astro_intro"
    fi
    unset _astro_intro
fi
