# SPDX-License-Identifier: GPL-3.0-or-later
"""Paste clipboard screenshots as private files without changing the clipboard."""
import os
from pathlib import Path
import select
import shlex
import subprocess
import tempfile
import time

from kittens.tui.handler import result_handler

MAX_IMAGE_BYTES = 64 * 1024 * 1024


def read_bounded(command: list[str], limit: int, timeout: float) -> bytes:
    """Bound clipboard output while reading, not after buffering the whole image."""
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    assert process.stdout is not None
    deadline = time.monotonic() + timeout
    data = bytearray()
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
                raise subprocess.TimeoutExpired(command, timeout)
            chunk = os.read(process.stdout.fileno(), min(65536, limit - len(data) + 1))
            if not chunk:
                status = process.wait(timeout=max(0, deadline - time.monotonic()))
                if status:
                    raise subprocess.CalledProcessError(status, command)
                return bytes(data)
            data.extend(chunk)
            if len(data) > limit:
                raise ValueError('Clipboard output exceeds the size limit')
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=1)


def clipboard_image() -> str:
    """Return a saved PNG path, or an empty string for native text fallback."""
    if os.environ.get('WAYLAND_DISPLAY'):
        types_cmd = ['wl-paste', '--list-types']
        image_cmd = ['wl-paste', '--no-newline', '--type', 'image/png']
    else:
        types_cmd = ['xclip', '-selection', 'clipboard', '-out', '-target', 'TARGETS']
        image_cmd = ['xclip', '-selection', 'clipboard', '-out', '-target', 'image/png']
    saved = None
    try:
        types = read_bounded(types_cmd, 64 * 1024, 2)
        if b'image/png' not in types.splitlines():
            return ''
        data = read_bounded(image_cmd, MAX_IMAGE_BYTES, 5)
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):
            return ''
        cache = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'astro' / 'clipboard'
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        cache.chmod(0o700)
        # Unique files must survive subsequent copies and the kitten process.
        with tempfile.NamedTemporaryFile(prefix='screenshot-', suffix='.png', dir=cache, delete=False) as image:
            saved = Path(image.name)
            image.write(data)
        # Closing/flushing the file must succeed before handing its path to a CLI.
        return str(saved.resolve())
    except (OSError, ValueError, subprocess.SubprocessError):
        if saved is not None:
            try:
                saved.unlink(missing_ok=True)
            except OSError:
                pass
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
