#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Install Astro into the current user's kitty configuration.
#
# Existing files that Astro replaces are moved to a timestamped backup
# directory next to the kitty configuration first.
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
config_dir=${KITTY_CONFIG_DIRECTORY:-${XDG_CONFIG_HOME:-$HOME/.config}/kitty}
font_dir=${XDG_DATA_HOME:-$HOME/.local/share}/fonts/astro-pane-controls
supported=0.49.2

if command -v kitty >/dev/null 2>&1; then
    version=$(kitty --version | awk '{print $2}')
    if [ "$version" != "$supported" ]; then
        echo "Warning: Astro is tested with kitty $supported, found $version." >&2
        echo "The pane controls use internal kitty APIs and may not work." >&2
    fi
else
    echo "Warning: kitty not found on PATH." >&2
fi

mkdir -p "$config_dir/sessions" "$font_dir"
backup="$config_dir/astro-backup-$(date +%Y%m%d-%H%M%S)"
for file in kitty.conf window_title_bar.py sessions/default.conf; do
    if [ -e "$config_dir/$file" ]; then
        mkdir -p "$backup/$(dirname "$file")"
        mv "$config_dir/$file" "$backup/$file"
    fi
    cp "$here/config/$file" "$config_dir/$file"
done
cp "$here/fonts/AstroPaneControls.ttf" "$font_dir/"
if command -v fc-cache >/dev/null 2>&1; then
    fc-cache -f "$font_dir"
fi

[ -d "$backup" ] && echo "Previous files moved to $backup"
echo "Astro installed in $config_dir. Restart kitty to load it."
