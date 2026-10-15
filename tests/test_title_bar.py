# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('astro_title_bar', Path(__file__).resolve().parents[1] / 'config/window_title_bar.py')
assert spec is not None and spec.loader is not None
bar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bar)


class StickyControlsTests(unittest.TestCase):
    def test_pointer_leaving_or_entering_other_pane_keeps_controls_expanded(self):
        for old, target in [((1, 'copy'), None), ((1, 'copy'), (2, 'close')), (None, None)]:
            with self.subTest(old=old, target=target):
                state = {'expanded': {1}, 'hover': old, 'agent_scan': float('inf')}
                boss = SimpleNamespace(**{bar._STATE_ATTR: state})
                with patch.object(bar.fdt, 'get_boss', return_value=boss), patch.object(bar, '_pointer_target', return_value=target), patch.object(bar, '_refresh_title_bars'):
                    bar._poll_hover()
                self.assertEqual(state['expanded'], {1})
                self.assertEqual(state['hover'], target)

    def test_explicit_toggle_still_closes_and_opens_controls(self):
        state = {'expanded': {1}}
        boss = SimpleNamespace(**{bar._STATE_ATTR: state}, set_active_window=lambda *a, **k: None)
        window = SimpleNamespace(id=1)
        with patch.object(bar, '_refresh_title_bars'):
            bar._activate(boss, window, 'collapse')
            self.assertEqual(state['expanded'], set())
            bar._activate(boss, window, 'expand')
            self.assertEqual(state['expanded'], {1})


if __name__ == '__main__':
    unittest.main()
