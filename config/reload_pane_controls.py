# SPDX-License-Identifier: GPL-3.0-or-later
"""Refresh cached pane controls without restarting Kitty or its child processes."""
from kittens.tui.handler import result_handler
from kitty.window_title_bar import clear_caches


def main(args):
    return None


def reload_controls(boss):
    # Kitty 0.49.2's regular config reload leaves this renderer cache intact.
    clear_caches()
    for manager in boss.os_window_map.values():
        for tab in manager.tabs:
            tab.update_window_title_bars()


@result_handler(no_ui=True)
def handle_result(args, answer, target_window_id, boss):
    reload_controls(boss)
