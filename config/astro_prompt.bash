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
        # Pale eye green / muted separators / warm fur taupe / cream path.
        # Every non-printing escape is bracketed for correct readline wrapping.
        PS1="$_astro_title"'${debian_chroot:+($debian_chroot)}\[\e[38;2;191;199;140m\]\u\[\e[38;2;168;153;132m\]@\[\e[38;2;189;174;147m\]\h\[\e[38;2;168;153;132m\]:\[\e[38;2;235;219;178m\]\w\[\e[38;2;191;199;140m\]\$\[\e[0m\] '
        unset _astro_title
    fi
fi
