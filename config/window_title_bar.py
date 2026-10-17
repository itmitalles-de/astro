# SPDX-License-Identifier: GPL-3.0-or-later
"""Astro: per-pane controls for kitty 0.49.2.

Install as window_title_bar.py with `watcher window_title_bar.py`,
`window_title_template "{custom}"`, and `window_title_bar_min_windows 1`.
Drawing and watcher entry points are native. The title mouse handler and
Window._title_bar_screen are internal APIs; verify clicks after kitty upgrades.
"""

from __future__ import annotations

import re
import sys
from types import MethodType
from typing import Any

from kitty import fast_data_types as fdt


_STATE_ATTR = "_kitty_pane_buttons_state_v1"
_BUTTON_RIGHT_MARGIN_CELLS = 1
_BAD_TITLE_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_PROMPT_MARKER = re.compile(r"\x1b\]133;([AC])([^\x1b\x07]*)(?:\x1b\\|\x07)")
# Pane groups cycle none -> 1 -> ... -> 4 -> none; Gruvbox bright colors
# reserved for functional pane grouping, independent of the neutral agent titles.
_GROUP_COLORS = ("211;134;155", "184;187;38", "131;165;152", "251;73;52")
# Agent CLIs by foreground process name: badge glyph, name and color (None
# keeps the title color). Agent names inherit the terminal's neutral title color.
_AGENTS = {
    "claude": ("\u273b", "Claude", None),
    "codex": ("\u203a_", "Codex", None),
    "hermes": ("\u2624", "Hermes", None),
    "agy": ("\u203a_", "agy", None),
}
_AGENT_CACHE_SECONDS = 2.0
_UUID = re.compile(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.I)
_LEADING_SYMBOLS = re.compile(r"^[^\w~/.]+")
_ATTENTION_COLOR = "251;73;52"
_HOVER_POLL_SECONDS = 0.12
_REPORTED_FAILURES: set[str] = set()


def _language() -> str:
    # pane_controls_lang ("de" or "en") overrides the system locale.
    import os

    from kitty.constants import config_dir

    try:
        with open(os.path.join(config_dir, "pane_controls_lang")) as f:
            chosen = f.read().strip().lower()
        if chosen in ("de", "en"):
            return chosen
    except OSError:
        pass
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if value := os.environ.get(name):
            return "de" if value.lower().startswith("de") else "en"
    return "en"


_LANGUAGE = _language()
_TOOLTIPS = {
    "add_right": {"de": "Rechts · Shift: Spalte", "en": "Right · Shift: column"},
    "add_below": {"de": "Unten · Shift: Zeile", "en": "Below · Shift: row"},
    "group": {"de": "Gruppe {group} · Klick: nächste", "en": "Group {group} · click: next"},
    "equal_width": {"de": "Gruppe: gleich breit", "en": "Group: equal widths"},
    "equal_height": {"de": "Gruppe: gleich hoch", "en": "Group: equal heights"},
    "copy": {"de": "Auswahl kopieren", "en": "Copy selection"},
    "copy_command": {"de": "Befehl + Ausgabe kopieren", "en": "Copy command + output"},
    "shortcuts": {"de": "Tastenkürzel", "en": "Shortcuts"},
    "zoom": {"de": "Vergrößern", "en": "Zoom"},
    "restore": {"de": "Verkleinern", "en": "Restore"},
    "close": {"de": "Schließen", "en": "Close"},
    "expand": {"de": "Mehr Buttons", "en": "More buttons"},
    "collapse": {"de": "Einklappen", "en": "Fold buttons"},
}
_MESSAGES = {
    "no_command": {
        "de": "Noch kein Shell-Befehl erkannt. Bitte einen Befehl mit aktiver Kitty-Shell-Integration ausführen.",
        "en": "No shell command detected yet. Run a command with kitty shell integration active.",
    },
    "equalize_unavailable": {
        "de": "Gleiche Größen sind in dieser Aufteilung ohne Änderung anderer Bereiche oder Unterschreitung einer Terminalzelle nicht möglich. Aufteilung unverändert.",
        "en": "Cannot equalize these panes in this split layout while preserving other panes and at least one terminal cell. Layout unchanged.",
    },
    "shortcuts_title": {"de": "Tastenkürzel · Esc schließen", "en": "Keyboard shortcuts · Esc closes"},
}


def _message(key: str) -> str:
    return _MESSAGES[key][_LANGUAGE]


def _report_failure(error: Exception) -> None:
    message = f"Astro pane controls unavailable: {error}"
    if message not in _REPORTED_FAILURES:
        _REPORTED_FAILURES.add(message)
        print(message, file=sys.stderr)


def _install(boss: Any) -> dict[str, Any]:
    for name in ("handle_window_title_bar_mouse", "set_active_window", "combine"):
        if not callable(getattr(boss, name, None)):
            raise RuntimeError(f"kitty API {name} is missing")
    for name in ("wcswidth", "truncate_point_for_length", "get_options"):
        if not callable(getattr(fdt, name, None)):
            raise RuntimeError(f"kitty API {name} is missing")

    state = getattr(boss, _STATE_ATTR, None)
    if state is None:
        state = {"original": boss.handle_window_title_bar_mouse, "pressed": {}}
        setattr(boss, _STATE_ATTR, state)
    # Window id -> group number; kept on the boss so reloads keep groups.
    state.setdefault("groups", {})
    # Panes whose folded controls are open, the last drawn controls per pane,
    # and the (window id, control) under the pointer.
    state.setdefault("expanded", set())
    state.setdefault("cells", {})
    state.setdefault("hover", None)
    # Restore native rendering when reloading the earlier pixel-offset version.
    original_update = state.pop("original_update_title_bar", None)
    if original_update is not None:
        from kitty.window import Window
        Window.update_title_bar = original_update
    # runpy loads the watcher and renderer separately, and reloads the renderer.
    # Always reuse the saved native handler; never wrap an earlier wrapper.
    current = boss.handle_window_title_bar_mouse
    if getattr(current, "__func__", None) is not _handle_title_bar_mouse:
        boss.handle_window_title_bar_mouse = MethodType(_handle_title_bar_mouse, boss)
        # Kitty reports no pointer motion over title bars to Python, so hints
        # poll the pointer while a kitty window has focus. Restart the timer
        # with this module's code after a reload.
        _stop_hover_timer(boss)
        # The boss outlives renderer modules: never retain an old native backend.
        pointer = state.pop("pointer", None)
        try:
            close = getattr(pointer, "close", None)
            if callable(close):
                close()
            elif getattr(pointer, "_display", None):
                # The earlier implementation owned a private XOpenDisplay connection.
                import ctypes
                pointer._lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
                pointer._lib.XCloseDisplay.restype = ctypes.c_int
                pointer._lib.XCloseDisplay(pointer._display)
                pointer._display = None
        except Exception as error:
            _report_failure(error)
        finally:
            state["timer"] = fdt.add_timer(_poll_hover, _HOVER_POLL_SECONDS, True)
    return state


_INSTALLED_FOR: list[Any] = []


def _ensure_installed(boss: Any) -> dict[str, Any]:
    # runpy gives the watcher and the renderer separate module globals, so each
    # copy installs once; both copies run identical code.
    if not _INSTALLED_FOR or _INSTALLED_FOR[0] is not boss:
        _install(boss)
        _INSTALLED_FOR[:] = [boss]
    return getattr(boss, _STATE_ATTR)


def on_load(boss: Any, data: dict[str, Any]) -> None:
    _ensure_installed(boss)


def _available_columns(bar: Any) -> int:
    columns = int(bar.screen.columns)
    if not hasattr(bar, "geometry") or not getattr(bar, "cell_width", 0):
        raise RuntimeError("kitty title-bar geometry API is missing")
    columns = min(columns, max(0, int((bar.geometry.right - bar.geometry.left) / bar.cell_width)))
    return columns


def _group_sgr(group: int | None) -> str:
    return _color_sgr(_GROUP_COLORS[group - 1]) if group else "\x1b[22;39m"


def _color_sgr(color: str | None, bold: bool = False) -> str:
    weight = "1" if bold else "22"
    return f"\x1b[{weight};38;2;{color}m" if color else f"\x1b[{weight};39m"


def _agent_title(window: Any, title: str, state: dict[str, Any]) -> tuple[str | None, str]:
    """Return the agent CLI running in the pane and its cleaned-up title."""
    import os
    import time

    cache = state.setdefault("agents", {})
    now = time.monotonic()
    cached = cache.get(window.id)
    if cached is not None and cached[1] == title and now - cached[0] < _AGENT_CACHE_SECONDS:
        return cached[2], cached[3]
    agent = _detect_agent(window)
    agy_title = _agy_session_title(window) if agent == "agy" else None
    shown = agy_title or title
    if agent is not None:
        # Drop spinners and status glyphs that agents put in front of OSC titles.
        if agy_title is None:
            shown = _LEADING_SYMBOLS.sub("", shown).strip()
        defaults = {"claude": ("claude", "claude code"), "codex": ("codex",),
                    "hermes": ("hermes", "hermes agent"), "agy": ("agy",)}
        if shown.lower() in defaults[agent]:
            shown = ""
        if agent == "codex" and (not shown or _UUID.fullmatch(shown)):
            # Codex titles itself with a session id; the directory says more.
            cwd = window.cwd_of_child or ""
            shown = "~" if cwd == os.path.expanduser("~") else os.path.basename(cwd.rstrip("/"))
    cache[window.id] = (now, title, agent, shown)
    return agent, shown


def _detect_agent(window: Any) -> str | None:
    import os

    try:
        pgrp = os.tcgetpgrp(window.child.child_fd)
        with open(f"/proc/{pgrp}/comm") as f:
            name = f.read().strip()
    except (OSError, TypeError, AttributeError):
        return None
    return name if name in _AGENTS else None


def _agy_session_title(window: Any) -> str | None:
    """Read only the title annotation for this process's held session lock.

    agy keeps /rename in a protobuf-text annotation without updating OSC titles.
    The open presence lock identifies the pane's session even when several
    agy processes share a working directory. Never guess from recent files.
    """
    import json
    import os
    import stat

    try:
        pgrp = os.tcgetpgrp(window.child.child_fd)
        with os.scandir(f"/proc/{pgrp}/fd") as descriptors:
            for entry in descriptors:
                try:
                    lock = os.readlink(entry.path)
                except OSError:
                    continue  # Descriptors can close while agy is working.
                if not lock.startswith("/") or not lock.endswith(".lock"):
                    continue
                directory, filename = os.path.split(lock)
                root, directory = os.path.split(directory)
                session, suffix = os.path.splitext(filename)
                if (directory != "presence" or suffix != ".lock"
                        or not _UUID.fullmatch(session)
                        or os.path.basename(root) != "antigravity-cli"):
                    continue
                path = os.path.join(root, "annotations", session + ".pbtxt")
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW)
                with os.fdopen(fd, encoding="utf-8", errors="replace") as f:
                    if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                        continue
                    annotation = f.read(16384)
                match = re.search(r'^\s*title\s*:\s*("(?:[^"\\]|\\.)*")', annotation, re.M)
                if match:
                    return _BAD_TITLE_CHARS.sub("", json.loads(match[1])).strip() or None
    except (OSError, ValueError, TypeError, AttributeError):
        pass  # Missing or changing annotations must never break pane controls.
    return None


def _scan_agents(boss: Any, state: dict[str, Any]) -> set[int]:
    """Return visible panes whose agent changed since their title was drawn.

    Agents rename their process after start and often keep the title, so
    title changes alone miss them.
    """
    cache = state.setdefault("agents", {})
    changed = set()
    for manager in boss.os_window_map.values():
        tab = manager.active_tab
        if tab is None:
            continue
        for group in tab.windows.iter_all_layoutable_groups(only_visible=True):
            for window in group.windows:
                cached = cache.get(window.id)
                if cached is None:
                    continue
                agent = _detect_agent(window)
                if cached[2] != agent:
                    del cache[window.id]
                    changed.add(window.id)
                elif agent == "agy":
                    # /rename changes the annotation, not the terminal title.
                    del cache[window.id]
                    if _agent_title(window, cached[1], state)[1] != cached[3]:
                        changed.add(window.id)
    return changed


def _styled(segments: list[tuple[str, str]], columns: int) -> tuple[str, int]:
    """Join (text, sgr) segments, truncated to `columns` cells."""
    plain = "".join(text for text, _ in segments)
    keep = fdt.truncate_point_for_length(plain, columns)
    parts, used = [], 0
    for text, sgr in segments:
        piece = text[:max(0, keep - used)]
        used += len(text)
        if piece:
            parts.extend((sgr, piece, "\x1b[22;23;39m"))
    return "".join(parts), fdt.wcswidth(plain[:keep])


def _tooltip(action: str, is_zoomed: bool, group: int | None) -> str:
    if action == "zoom" and is_zoomed:
        action = "restore"
    text = _TOOLTIPS[action][_LANGUAGE]
    return text.format(group=group or "–")


def _button_cells(bar: Any, is_zoomed: bool = False, title_width: int = 0,
                  expanded: bool = False) -> list[tuple[str, int, int, str]]:
    columns = _available_columns(bar)
    if columns < 1:
        return []
    # One outline family, identical canvas and stroke width for every control.
    # Codepoints and paths are defined in build_pane_icons.py.
    labels = [("add_right", "\ue906\ue900 "), ("add_below", "\ue906\ue901 "),
              ("group", "\ue90a "),
              ("equal_width", "\ue90b "), ("equal_height", "\ue90c "), ("copy", "\ue902 "),
              ("copy_command", "\ue907 "), ("shortcuts", "\ue908 "),
              ("zoom", ("\ue905" if is_zoomed else "\ue903") + " "), ("close", "\ue904 ")]
    right_margin = _BUTTON_RIGHT_MARGIN_CELLS if columns >= 6 else 0
    separator = " "

    def total_width() -> int:
        return sum(fdt.wcswidth(label) for _, label in labels) + len(separator) * (len(labels) - 1)

    # Fold everything except close behind a toggle when the title would be cut.
    keep = 0
    if total_width() + 1 + title_width > columns - right_margin:
        if expanded:
            labels.insert(0, ("collapse", "\ue90e "))
            keep = 1
        else:
            labels = [("expand", "\ue90d "), labels[-1]]
    if total_width() > columns - right_margin:
        separator = ""
    if total_width() > columns - right_margin:
        labels = [(action, label.rstrip()) for action, label in labels]
    while len(labels) > keep and total_width() > columns - right_margin:
        # Preserve the toggle and the rightmost controls in narrow panes.
        labels.pop(keep)
    cursor = columns - right_margin - total_width()
    cells = []
    for action, label in labels:
        end = cursor + fdt.wcswidth(label)
        cells.append((action, cursor, end, label))
        cursor = end + len(separator)
    return cells


def draw_window_title(data: Any) -> str:
    title = _BAD_TITLE_CHARS.sub("", str(data.title))
    try:
        boss = fdt.get_boss()
        state = _ensure_installed(boss)
        window = boss.window_id_map.get(data.window_id)
        if window is None:
            return title
        bar = getattr(window, "_title_bar_screen", None)
        if bar is None:
            raise RuntimeError("kitty per-window title-bar screen API is missing")
        tab = window.tabref()
        group = state["groups"].get(window.id)
        is_zoomed = tab is not None and tab.current_layout.name == "stack"
        agent, title = _agent_title(window, title, state)
        markers: list[tuple[str, str]] = []
        if data.needs_attention:
            # The bell: an agent waits for input or finished its turn.
            markers.append(("\u25cf ", _color_sgr(_ATTENTION_COLOR, bold=True)))
        elif data.has_activity_since_last_focus and not data.is_active:
            markers.append(("\u2022 ", "\x1b[2m"))
        segments: list[tuple[str, str]] = []
        if group:
            # Name the group in the title too, so it stays visible in narrow panes.
            segments.append((f"\u25cf{group} ", _group_sgr(group)))
        if agent is not None:
            glyph, name, color = _AGENTS[agent]
            segments.append((f"{glyph} {name}", _color_sgr(color, bold=True)))
            if title:
                segments.append((" \u00b7 ", "\x1b[2m"))
        if title:
            segments.append((title, "\x1b[22;39m"))
        cells = _button_cells(bar, is_zoomed, sum(fdt.wcswidth(text) for text, _ in segments),
                              window.id in state["expanded"])
        segments = markers + segments
        state["cells"][window.id] = cells
        if not cells:
            return _styled(segments, _available_columns(bar))[0]
        hover = state["hover"]
        hovered = hover[1] if hover is not None and hover[0] == window.id else None
        if hovered is not None:
            # Kitty has no tooltips; describe the hovered control in the title.
            segments = [(_tooltip(hovered, is_zoomed, group), "\x1b[22;3;39m")]
        title, width = _styled(segments, max(0, cells[0][1] - 1))
        parts = [title, " " * (cells[0][1] - width)]
        cursor = cells[0][1]
        for action, start, end, label in cells:
            parts.append(" " * (start - cursor))
            # Controls inherit the title's foreground; the group button its color.
            parts.extend((_group_sgr(group) if action == "group" else "\x1b[22;39m", label))
            cursor = end
        parts.append("\x1b[22;39m")
        parts.append(" " * (_available_columns(bar) - cursor))
        return "".join(parts)
    except Exception as error:
        _report_failure(error)
        try:
            getattr(fdt.get_boss(), _STATE_ATTR)["cells"][data.window_id] = []
        except Exception:
            pass
        return f"Controls unavailable | {title}"


def _hit_test(window: Any, x: float, y: float) -> str | None:
    bar = getattr(window, "_title_bar_screen", None)
    if bar is None:
        return None
    # The custom drawing function is evaluated even when its result is not used.
    # Only consume clicks when the selected template displays these controls.
    options = fdt.get_options()
    template = options.window_title_template
    tab = window.tabref()
    if tab is not None and tab.active_window is window:
        active = options.active_window_title_template
        if active and active != "none":
            template = active
    if "{custom}" not in template:
        return None
    return _control_at(window, bar, x, y)


def _control_at(window: Any, bar: Any, x: float, y: float) -> str | None:
    geometry = bar.geometry
    if not (geometry.left <= x < geometry.right and geometry.top <= y < geometry.bottom):
        return None
    cell = int((x - geometry.left) // bar.cell_width)
    # Hit-test exactly what was drawn last; the layout depends on the title.
    cells = getattr(fdt.get_boss(), _STATE_ATTR)["cells"].get(window.id, [])
    for action, start, end, _ in cells:
        if start <= cell < end:
            return action
    return None


def _pointer_target(boss: Any, state: dict[str, Any]) -> tuple[int, str | None] | None:
    """Return (window id, control or None) for the title bar under the pointer.

    Raises _NoPointer when the pointer position is unavailable.
    """
    if state.get("pointer") is False:
        raise _NoPointer
    os_window_id = fdt.current_focused_os_window_id()
    manager = boss.os_window_map.get(os_window_id) if os_window_id else None
    tab = manager.active_tab if manager is not None else None
    if tab is None:
        return None
    try:
        pointer = state.get("pointer")
        if pointer is None:
            pointer = state["pointer"] = _X11Pointer()
        # Raises on native Wayland, where kitty has no X11 window.
        position = pointer.query(fdt.x11_window_id(os_window_id))
    except Exception as error:
        # No X11 pointer: no hints, but agents still scan and nothing folds.
        _report_failure(error)
        state["pointer"] = False
        raise _NoPointer from error
    size = fdt.get_os_window_size(os_window_id)
    if position is None or not size or not size["width"]:
        return None
    # Title-bar geometry is in framebuffer pixels, the pointer in X11 pixels.
    scale = size["framebuffer_width"] / size["width"]
    x, y = position[0] * scale, position[1] * scale
    for group in tab.windows.iter_all_layoutable_groups(only_visible=True):
        for window in group.windows:
            bar = getattr(window, "_title_bar_screen", None)
            if bar is None:
                continue
            g = bar.geometry
            if g.left <= x < g.right and g.top <= y < g.bottom:
                return window.id, _control_at(window, bar, x, y)
    return None


class _NoPointer(Exception):
    pass


class _X11Pointer:
    """Checked XCB queries: a stale XID must never invoke Xlib's fatal handler."""

    def __init__(self) -> None:
        import ctypes

        self._ctypes = ctypes
        # Layouts from xcb/xproto.h; XIDs and cookies are always 32-bit.
        class Cookie(ctypes.Structure):
            _fields_ = [("sequence", ctypes.c_uint)]

        class Reply(ctypes.Structure):
            _fields_ = [("response_type", ctypes.c_uint8), ("same_screen", ctypes.c_uint8),
                        ("sequence", ctypes.c_uint16), ("length", ctypes.c_uint32),
                        ("root", ctypes.c_uint32), ("child", ctypes.c_uint32),
                        ("root_x", ctypes.c_int16), ("root_y", ctypes.c_int16),
                        ("win_x", ctypes.c_int16), ("win_y", ctypes.c_int16),
                        ("mask", ctypes.c_uint16), ("pad0", ctypes.c_uint8 * 2)]

        lib = ctypes.CDLL("libxcb.so.1")
        lib.xcb_connect.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
        lib.xcb_connect.restype = ctypes.c_void_p
        lib.xcb_connection_has_error.argtypes = [ctypes.c_void_p]
        lib.xcb_connection_has_error.restype = ctypes.c_int
        lib.xcb_disconnect.argtypes = [ctypes.c_void_p]
        lib.xcb_disconnect.restype = None
        lib.xcb_query_pointer.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        lib.xcb_query_pointer.restype = Cookie
        lib.xcb_query_pointer_reply.argtypes = [ctypes.c_void_p, Cookie, ctypes.POINTER(ctypes.c_void_p)]
        lib.xcb_query_pointer_reply.restype = ctypes.POINTER(Reply)
        self._lib = lib
        self._free = ctypes.CDLL(None).free
        self._free.argtypes = [ctypes.c_void_p]
        self._free.restype = None
        self._connection = lib.xcb_connect(None, None)
        if not self._connection or lib.xcb_connection_has_error(self._connection):
            self.close()
            raise RuntimeError("Cannot open the X11 display for button hints")

    def query(self, xid: int) -> tuple[int, int] | None:
        if not xid or not self._connection:
            return None
        c = self._ctypes
        error = c.c_void_p()
        cookie = self._lib.xcb_query_pointer(self._connection, xid)
        reply = self._lib.xcb_query_pointer_reply(self._connection, cookie, c.byref(error))
        try:
            if error.value or not reply or not reply.contents.same_screen:
                return None
            return reply.contents.win_x, reply.contents.win_y
        finally:
            self._free(reply)
            self._free(error)

    def close(self) -> None:
        connection = getattr(self, '_connection', None)
        if connection:
            self._connection = None
            self._lib.xcb_disconnect(connection)

    def __del__(self) -> None:
        self.close()


def _poll_hover(timer_id: int | None = None) -> None:
    # Never stop the timer on errors: a failed tick is reported once and the
    # next tick tries again.
    try:
        boss = fdt.get_boss()
        state = getattr(boss, _STATE_ATTR, None)
        if state is None:
            return
        import time

        changed = set()
        now = time.monotonic()
        if now - state.get("agent_scan", 0.0) >= _AGENT_CACHE_SECONDS:
            state["agent_scan"] = now
            _prune_closed(boss, state)
            changed = _scan_agents(boss, state)
        try:
            target = _pointer_target(boss, state)
        except _NoPointer:
            # Unknown pointer: keep hints off and leave unfolded panes open.
            _refresh_title_bars(boss, changed)
            return
        old = state["hover"]
        if target == old and not changed:
            return
        state["hover"] = target
        changed |= {w for w in (old and old[0], target and target[0]) if w}
        # Opening is deliberate: keep controls open until the collapse button
        # is clicked. Pointer drift changes hints, never the expanded state.
        _refresh_title_bars(boss, changed)
    except Exception as error:
        _report_failure(error)


def _prune_closed(boss: Any, state: dict[str, Any]) -> None:
    """Forget per-pane state of closed panes; window ids are never reused."""
    alive = boss.window_id_map
    for key in ("agents", "cells", "groups"):
        entries = state.get(key, {})
        for window_id in [w for w in entries if w not in alive]:
            del entries[window_id]
    state["expanded"] &= set(alive)


def _refresh_title_bars(boss: Any, window_ids: set[int]) -> None:
    tabs = {}
    for window_id in window_ids:
        window = boss.window_id_map.get(window_id)
        tab = window.tabref() if window is not None else None
        if tab is not None:
            tabs[id(tab)] = tab
    for tab in tabs.values():
        tab.update_window_title_bars()


def _stop_hover_timer(boss: Any) -> None:
    state = getattr(boss, _STATE_ATTR, None)
    if state is not None and state.get("timer") is not None:
        fdt.remove_timer(state.pop("timer"))


def _activate(boss: Any, window: Any, action: str, modifiers: int = 0) -> None:
    # Layout actions act on the active window, so focus the clicked pane first.
    boss.set_active_window(window, switch_os_window_if_needed=True)
    if action in ("add_right", "add_below"):
        if modifiers & fdt.GLFW_MOD_SHIFT:
            _launch_full_span(boss, window, horizontal=action == "add_right")
            return
        tab = _splits_tab(window)
        if tab is None:
            return
        location = "vsplit" if action == "add_right" else "hsplit"
        command = (
            f"launch --cwd=current --location={location} "
            f"--next-to=id:{window.id} --source-window=id:{window.id}"
        )
    elif action in ("expand", "collapse"):
        state = getattr(boss, _STATE_ATTR)
        if action == "expand":
            state["expanded"].add(window.id)
        else:
            state["expanded"].discard(window.id)
        _refresh_title_bars(boss, {window.id})
        return
    elif action == "group":
        _cycle_group(boss, window)
        return
    elif action in ("equal_width", "equal_height"):
        _equalize_group(boss, window, horizontal=action == "equal_width")
        return
    elif action == "copy":
        command = "copy_to_clipboard"
    elif action == "copy_command":
        _copy_command(window)
        return
    elif action == "shortcuts":
        _show_shortcuts(boss, window)
        return
    elif action == "zoom":
        command = "toggle_layout stack"
    elif action == "close":
        # Native confirmation for running jobs; a plain shell closes directly.
        command = "close_window_with_confirmation ignore-shell"
    else:
        return
    boss.combine(command, window_for_dispatch=window, dispatch_type="MouseEvent", raise_error=True)


def _splits_tab(window: Any) -> Any:
    tab = window.tabref()
    if tab is None:
        return None
    if tab.current_layout.name == "stack":
        tab.last_used_layout()
    if tab.current_layout.name != "splits":
        tab.goto_layout("splits", raise_exception=True)
    return tab


def _launch_full_span(boss: Any, window: Any, horizontal: bool) -> None:
    """Append one full-height column or full-width row around the old layout.

    Preserve every old split and bias, rather than redistributing an intermediate
    local split. The new strip gets the clicked pane's proportional axis share.
    """
    from kitty.layout.splits import Pair
    from kitty.launch import launch, parse_launch_args

    tab = _splits_tab(window)
    if tab is None:
        return
    layout = tab.current_layout
    source_group = tab.windows.group_for_window(window)
    path = layout.pairs_root.find_window_in_tree(source_group.id) if source_group is not None else None
    if path is None:
        raise RuntimeError("Could not find the source pane in the split layout")
    share = 1.0
    for pair, is_first in path:
        if pair.horizontal == horizontal and pair.one is not None and pair.two is not None:
            share *= pair.bias if is_first else 1.0 - pair.bias
    previous = Pair()
    previous.unserialize(layout.pairs_root.serialize(), lambda group_id: group_id)
    location = "vsplit" if horizontal else "hsplit"
    spec = parse_launch_args([
        "--cwd=current", f"--location={location}", "--bias=50",
        f"--next-to=id:{window.id}", f"--source-window=id:{window.id}",
    ])
    added = launch(boss, spec.opts, spec.args, target_tab=tab)
    group = tab.windows.group_for_window(added) if added is not None else None
    if group is None:
        raise RuntimeError("Could not open the full-span terminal")
    root = Pair(horizontal)
    root.one, root.two = previous, group.id
    root.bias = 1.0 / (1.0 + max(0.05, min(1.0, share)))
    layout.pairs_root = root
    tab.relayout()


def _cycle_group(boss: Any, window: Any) -> None:
    groups = getattr(boss, _STATE_ATTR)["groups"]
    # Forget closed panes so their ids never leak into a later equalize.
    for window_id in [w for w in groups if w not in boss.window_id_map]:
        del groups[window_id]
    group = groups.pop(window.id, 0) + 1
    if group <= len(_GROUP_COLORS):
        groups[window.id] = group
    tab = window.tabref()
    if tab is not None:
        tab.update_window_title_bars()


def _equalize_group(boss: Any, window: Any, horizontal: bool) -> None:
    """Give every pane in the clicked pane's group the same width or height.

    Panes outside the group keep their current size along that axis. An
    ungrouped pane equalizes the whole tab along that axis only. Works on the
    biases of kitty.layout.splits.Pair, like `layout_action equalize`.
    """
    from kitty.layout.base import lgd
    from kitty.layout.splits import Pair

    tab = _splits_tab(window)
    if tab is None:
        return
    root = tab.current_layout.pairs_root
    groups = getattr(boss, _STATE_ATTR)["groups"]
    wanted = groups.get(window.id)
    panes = {group.id: group for group in tab.windows.iter_all_layoutable_groups()}
    members = {group.id for group in panes.values()
               if wanted is None or any(groups.get(w.id) == wanted for w in group.windows)}
    if len(members) < 2:
        return
    # lgd is shared by all OS windows, which can have different font grids.
    tab.current_layout._set_dimensions(tab.windows)
    cell = lgd.cell_width if horizontal else lgd.cell_height
    sides = ("left", "right") if horizontal else ("top", "bottom")
    border_mult = 0 if lgd.draw_minimal_borders else 1
    decorations = {wid: sum(group.decoration(side, border_mult=border_mult) for side in sides)
                   for wid, group in panes.items()}
    current_cells = {wid: ((group.geometry.right - group.geometry.left) if horizontal else
                           (group.geometry.bottom - group.geometry.top)) // cell
                     for wid, group in panes.items()}

    def extent(pair: Any, first: bool) -> int:
        edges = pair.first_extent if first else pair.second_extent
        return (edges.right - edges.left) if horizontal else (edges.bottom - edges.top)

    def size(pair: Any) -> int:
        return pair.width if horizontal else pair.height

    bounds: dict[Any, tuple[int, int]] = {}

    def measure(node: Any, cells: int, rounding: int) -> tuple[int, int] | None:
        """Feasible pixel spans, preserving every outside pane's cell count."""
        if node is None:
            return 0, 0
        if not isinstance(node, Pair):
            count = cells if node in members else current_cells[node]
            if count < 1:
                return None
            extra = rounding if node in members else 0
            span = (decorations[node] + count * cell,
                    decorations[node] + (count + extra + 1) * cell - 1)
        elif node.one is None or node.two is None:
            span = measure(node.one if node.one is not None else node.two, cells, rounding)
        else:
            one = measure(node.one, cells, rounding)
            two = measure(node.two, cells, rounding)
            if one is None or two is None:
                return None
            if node.horizontal == horizontal:
                border = 2 * node.border_width
                span = one[0] + two[0] + border, one[1] + two[1] + border
            else:
                # Both branches share the same span: keep BOTH constraints,
                # including outsiders in an otherwise grouped subtree.
                span = max(one[0], two[0]), min(one[1], two[1])
        if span is None or span[0] > span[1]:
            return None
        bounds[node] = span
        return span

    def plan(node: Any, target: int, changes: list[tuple[Any, float]]) -> None:
        if not isinstance(node, Pair):
            return
        if node.one is None or node.two is None:
            plan(node.one if node.one is not None else node.two, target, changes)
            return
        if node.horizontal != horizontal:
            plan(node.one, target, changes)
            plan(node.two, target, changes)
            return
        bw = node.border_width
        one, two = bounds[node.one], bounds[node.two]
        lower = max(one[0], target - 2 * bw - two[1])
        upper = min(one[1], target - 2 * bw - two[0])
        first = min(upper, max(lower, extent(node, True)))
        if first != extent(node, True) or target != size(node):
            # Native layout_pair uses int(bias * size) - border pixels.
            changes.append((node, (first + bw + 0.5) / target))
        plan(node.one, first, changes)
        plan(node.two, target - first - 2 * bw, changes)

    target = size(root)
    preferred = sum(current_cells[wid] for wid in members) / len(members)
    candidates = sorted(range(1, target // cell + 1), key=lambda count: abs(count - preferred))
    # Prefer identical cell counts; permit one cell of unavoidable rounding.
    # Search is bounded by the current screen's cell count, not scrollback.
    for rounding in (0, 1):
        for cells in candidates:
            bounds.clear()
            span = measure(root, cells, rounding)
            if span is None or not span[0] <= target <= span[1]:
                continue
            changes: list[tuple[Any, float]] = []
            plan(root, target, changes)
            # Validate the entire tree before changing any live bias.
            for node, bias in changes:
                node.bias = bias
            if changes:
                tab.relayout()
            return
    raise RuntimeError(_message("equalize_unavailable"))


def _copy_command(window: Any) -> None:
    from kitty.clipboard import set_clipboard_string
    from kitty.window import CommandOutput

    cmdline = window.last_cmd_cmdline
    if not cmdline:
        raise RuntimeError(_message("no_command"))
    # Kitty 0.49.2 loses the output-start mark when a command prints nothing:
    # the next prompt replaces that line and even last_run returns older output.
    # Verify the latest prompt interval before reading the native output range.
    text = window.as_text(as_ansi=True)
    markers = [m[1] for m in _PROMPT_MARKER.finditer(text) if not m[2]]
    if len(markers) < 2:
        # The last prompt pair scrolled off screen; scan the history as well.
        text = window.as_text(as_ansi=True, add_history=True)
        markers = [m[1] for m in _PROMPT_MARKER.finditer(text) if not m[2]]
    # If the start has already left scrollback, retain Kitty's partial output.
    has_output = len(markers) < 2 or markers[-1] == "C" or markers[-2:] == ["C", "A"]
    output = window.cmd_output(CommandOutput.last_run, as_ansi=False, add_wrap_markers=False) if has_output else ""
    set_clipboard_string(cmdline + "\n" + output)


def _show_shortcuts(boss: Any, window: Any) -> None:
    import json
    from functools import partial

    from kittens.command_palette.main import collect_keys_data, handle_result
    from kitty.config import common_opts_as_dict
    from kitty.constants import config_dir, kitten_exe
    from kitty.tabs import SpecialWindow

    # A separate full-width tab keeps the native overview readable in a large
    # grid without resizing the terminal or sending input to its running job.
    options = fdt.get_options()
    data = collect_keys_data(options)
    modifiers = "+".join(name for flag, name in (
        (fdt.GLFW_MOD_CONTROL, "ctrl"), (fdt.GLFW_MOD_SHIFT, "shift"),
        (fdt.GLFW_MOD_ALT, "alt"), (fdt.GLFW_MOD_SUPER, "super"),
    ) if options.kitty_mod & flag)
    for categories in data["modes"].values():
        for entries in categories.values():
            for entry in entries:
                entry["key"] = entry["key"].replace("kitty_mod+", modifiers + "+" if modifiers else "")
    tab = boss._new_tab(SpecialWindow(
        [kitten_exe(), "command-palette"],
        stdin=json.dumps(data).encode("utf-8"),
        override_title=_message("shortcuts_title"),
        env={
            "KITTEN_RUNNING_AS_UI": "1",
            "KITTY_CONFIG_DIRECTORY": config_dir,
            "KITTY_COMMON_OPTS": json.dumps(common_opts_as_dict(options)),
            "KITTY_BASIC_COLORS": json.dumps(window.screen.color_profile.basic_colors()),
        },
    ), as_neighbor=True)
    if tab is None or tab.active_window is None:
        raise RuntimeError("Could not open keyboard shortcuts")
    palette = tab.active_window
    # Preserve native search/selection behavior, dispatching to the source pane.
    palette.actions_on_close.append(partial(boss.on_kitten_finish, window.id, handle_result))

    def restore_focus(closed_window: Any) -> None:
        if window.id in boss.window_id_map:
            boss.set_active_window(window, switch_os_window_if_needed=True)

    palette.actions_on_removal.append(restore_focus)


def _handle_title_bar_mouse(
    boss: Any, os_window_id: int, window_id: int, x: float, y: float,
    button: int, modifiers: int, action: int,
) -> None:
    state = getattr(boss, _STATE_ATTR)
    original = state["original"]
    if button != fdt.GLFW_MOUSE_BUTTON_LEFT or action not in (fdt.GLFW_PRESS, fdt.GLFW_RELEASE):
        original(os_window_id, window_id, x, y, button, modifiers, action)
        return
    window = boss.window_id_map.get(window_id)
    try:
        hit = _hit_test(window, x, y) if window is not None else None
        if action == fdt.GLFW_PRESS:
            # A fresh press cancels a previous press released outside a title bar.
            state["pressed"].pop(os_window_id, None)
            if hit is not None:
                state["pressed"][os_window_id] = (window_id, hit, modifiers)
                boss.set_active_window(window, switch_os_window_if_needed=True)
                # Keep button clicks out of native drag/double-click bookkeeping.
                manager = boss.os_window_map.get(os_window_id)
                if manager is not None:
                    manager.recent_title_bar_mouse_events.clear()
                return
        else:
            pressed = state["pressed"].pop(os_window_id, None)
            if pressed is not None:
                if pressed[:2] == (window_id, hit) and window is not None and hit is not None:
                    _activate(boss, window, hit, pressed[2] if len(pressed) > 2 else modifiers)
                return
    except Exception as error:
        _report_failure(error)
        state["pressed"].pop(os_window_id, None)
        boss.show_error("Astro pane controls", str(error))
        return
    # All ordinary title interactions retain kitty's native focus/drag/rename.
    original(os_window_id, window_id, x, y, button, modifiers, action)
