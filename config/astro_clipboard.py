# SPDX-License-Identifier: GPL-3.0-or-later
"""Paste clipboard screenshots as private files without changing the clipboard."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

from kittens.tui.handler import result_handler


def clipboard_image() -> str:
    """Return a saved PNG path, or an empty string for native text fallback."""
    if os.environ.get('WAYLAND_DISPLAY'):
        types_cmd = ['wl-paste', '--list-types']
        image_cmd = ['wl-paste', '--no-newline', '--type', 'image/png']
    else:
        types_cmd = ['xclip', '-selection', 'clipboard', '-out', '-target', 'TARGETS']
        image_cmd = ['xclip', '-selection', 'clipboard', '-out', '-target', 'image/png']
    try:
        types = subprocess.run(types_cmd, capture_output=True, check=True, timeout=2).stdout
        if b'image/png' not in types.splitlines():
            return ''
        data = subprocess.run(image_cmd, capture_output=True, check=True, timeout=5).stdout
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):
            return ''
        cache = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'astro' / 'clipboard'
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        cache.chmod(0o700)
        # Unique files must survive subsequent copies and the kitten process.
        with tempfile.NamedTemporaryFile(prefix='screenshot-', suffix='.png', dir=cache, delete=False) as image:
            try:
                image.write(data)
            except OSError:
                Path(image.name).unlink(missing_ok=True)
                raise
            return str(Path(image.name).resolve())
    except (OSError, subprocess.SubprocessError):
        return ''


def main(args: list[str]) -> str:
    return clipboard_image()


@result_handler()
def handle_result(args, image_path, target_window_id, boss):
    window = boss.window_id_map.get(target_window_id)
    if window is None:
        return
    if image_path:
        window.paste_with_actions(shlex.quote(image_path) + ' ')
    else:
        # Target the clicked pane, not whichever pane is now active.
        from kitty.clipboard import get_clipboard_string
        text = get_clipboard_string()
        if text:
            window.paste_with_actions(text)
