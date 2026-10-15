# SPDX-License-Identifier: GPL-3.0-or-later
# Keep the familiar user@host:path$ layout; only change its color roles.
if [[ $- == *i* && -n ${KITTY_WINDOW_ID-} && ${ASTRO_PROMPT-} != off ]]; then
    if [[ ${TERM-} == dumb || -n ${NO_COLOR+x} ]]; then
        PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w\$ '
    else
        _astro_title=''
        case ${TERM-} in
            xterm*|rxvt*) _astro_title='\[\e]0;${debian_chroot:+($debian_chroot)}\u@\h: \w\a\]' ;;
        esac
        # Use GNOME's ANSI palette, not a second custom RGB theme.
        # Every non-printing escape is bracketed for correct readline wrapping.
        PS1="$_astro_title"'${debian_chroot:+($debian_chroot)}\[\e[37m\]\u\[\e[90m\]@\[\e[37m\]\h\[\e[90m\]:\[\e[37m\]\w\[\e[94m\]\$\[\e[0m\] '
        unset _astro_title
    fi
fi
