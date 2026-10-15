# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CodexThemeTests(unittest.TestCase):
    def test_terminal_chrome_uses_paper_and_codex_blue_without_changing_layout(self):
        options = {}
        for line in (ROOT/'config/kitty.conf').read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                key, value = line.split(maxsplit=1)
                options[key] = value
        for key in ['foreground','cursor','selection_foreground','window_title_bar_active_foreground','active_tab_foreground','color7','color15']:
            self.assertEqual(options[key], '#d8d4ce', key)
        self.assertEqual(options['active_border_color'], '#63a8f8')
        self.assertEqual(options['window_title_bar_active_background'], '#242426')
        self.assertEqual(options['background'], '#191919')
        self.assertEqual(options['shell'], '/bin/bash --login')
        self.assertIn('splits:', options['enabled_layouts'])

    def test_agent_badges_share_the_neutral_paper_title_color(self):
        spec = importlib.util.spec_from_file_location('astro_title_theme', ROOT/'config/window_title_bar.py')
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(set(module._AGENTS), {'claude','codex','hermes'})
        for glyph, name, override in module._AGENTS.values():
            self.assertTrue(glyph and name)
            self.assertIsNone(override, 'agent names must inherit the Codex-style Paper title')


if __name__ == '__main__':
    unittest.main()
