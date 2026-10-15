# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GnomeThemeTests(unittest.TestCase):
    def test_palette_matches_all_sixteen_builtin_gnome_colors(self):
        options = {}
        for line in (ROOT/'config/kitty.conf').read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                key, value = line.split(maxsplit=1)
                options[key] = value
        colors = json.loads((ROOT/'tests/fixtures/gnome-palette.json').read_text())['colors']
        self.assertEqual(len(colors),16)
        self.assertEqual([options[f'color{i}'] for i in range(16)],colors)
        self.assertEqual(options['foreground'], colors[7])
        self.assertEqual(options['background'], '#191919', 'preserve the original neutral background')
        self.assertEqual(options['active_border_color'], colors[12])
        self.assertEqual(options['bold_text_in_bright_colors'], 'no')
        self.assertEqual(options['shell'], '/bin/bash --login')
        self.assertIn('splits:', options['enabled_layouts'])

    def test_agent_badges_inherit_the_gnome_title_color(self):
        spec = importlib.util.spec_from_file_location('astro_title_theme', ROOT/'config/window_title_bar.py')
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(set(module._AGENTS), {'claude','codex','hermes'})
        for glyph, name, override in module._AGENTS.values():
            self.assertTrue(glyph and name)
            self.assertIsNone(override, 'agent names must inherit the GNOME title color')


if __name__ == '__main__':
    unittest.main()
