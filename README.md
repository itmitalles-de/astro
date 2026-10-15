# Astro

Astro turns [kitty](https://sw.kovidgoyal.net/kitty/) into a workspace for
agent CLIs such as Claude Code, Codex and Hermes. It is not a fork of kitty's
source code: it is a configuration plus a title-bar extension that runs inside
an unmodified kitty.

## Features

**Pane controls in every title bar**

| Control | Action |
| --- | --- |
| `+→` / `+↓` | Open a terminal to the right / below in the current directory |
| `✧↓` | Open Codex below, sized to six rows |
| `▦` | Cycle the pane's group: none → 1 → 2 → 3 → 4 → none (colored) |
| `\|↔\|` | Give every pane of this group the same width |
| `⇕` | Give every pane of this group the same height |
| copy | Copy the selection |
| `>_` | Copy the last shell command with its output |
| keyboard | Show kitty's keyboard shortcuts in a separate tab |
| zoom | Zoom the pane (stack layout) and back |
| `✕` | Close the pane (asks when a job is running) |

- **Groups:** equalizing changes only the panes of the clicked pane's group;
  every other pane keeps its size. On an ungrouped pane the buttons equalize
  the whole tab along that axis only.
- **Folding:** when the title would otherwise be cut, all controls except close
  fold behind `‹`. Click it to unfold; they fold again when the pointer leaves
  the title bar.
- **Hover hints:** the title bar describes the control under the pointer.
  Hints are English or German, following the system locale; put `de` or `en`
  into `~/.config/kitty/pane_controls_lang` to pin a language.

**Agent-aware panes**

- Panes running `claude`, `codex` or `hermes` get a colored badge
  (✻ Claude, ›_ Codex, ☤ Hermes). Codex session ids give way to the working
  directory.
- A red dot marks a pane whose program rang the bell (an agent finished or
  waits for input); `•` marks background output since the pane last had focus.

**Configuration** (`config/kitty.conf`)

- Splits layout with proportional sizing, a 3 × 3 agent workspace session
  (`config/sessions/default.conf`) plus a monitor column.
- Gruvbox colors, rounded tabs (shown from two tabs on), dimmed inactive panes,
  beam cursor with a short trail, hover-only link underlines.
- Desktop notification when a long shell command finishes in an unfocused
  pane; trailing spaces are stripped when copying from TUIs.

## Requirements

- kitty **0.49.2**. The title-bar mouse handler, `Window._title_bar_screen`
  and the splits layout internals are not public APIs; check Astro after every
  kitty upgrade.
- Linux with kitty on X11 (`linux_display_server x11`, also under Xwayland).
  On native Wayland everything except the hover hints works.
- Optional: Python 3 with [fontTools](https://github.com/fonttools/fonttools)
  to rebuild the icon font.

## Install

```sh
git clone https://github.com/itmitalles-de/astro.git
cd astro
./install.sh
```

The installer copies `config/` into `~/.config/kitty` (or
`$KITTY_CONFIG_DIRECTORY`), moves replaced files into a timestamped backup
folder and installs the icon font into `~/.local/share/fonts`. Restart kitty
afterwards.

## Icon font

All controls use one outline icon font, `fonts/AstroPaneControls.ttf`
(private use area U+E900–U+E90E). Edit the paths in
`tools/build_pane_icons.py` and rebuild it with:

```sh
python3 tools/build_pane_icons.py fonts/AstroPaneControls.ttf
```

The build is reproducible byte for byte.

## License

Copyright (C) 2026 itmitalles.de

Astro is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. See [LICENSE](LICENSE).
