# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]


class TitleBarReloadTests(unittest.TestCase):
    def test_reload_invalidates_the_native_renderer_and_redraws_existing_tabs(self):
        path=ROOT/'config/reload_pane_controls.py'
        self.assertTrue(path.exists(),'native cached title-bar renderer needs an explicit reload helper')
        spec=importlib.util.spec_from_file_location('astro_reload_controls',path)
        assert spec is not None and spec.loader is not None
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        tabs=[SimpleNamespace(update_window_title_bars=Mock()) for _ in range(3)]
        boss=SimpleNamespace(os_window_map={1:SimpleNamespace(tabs=tabs[:2]),2:SimpleNamespace(tabs=tabs[2:])})
        with patch.object(module,'clear_caches') as clear:
            module.reload_controls(boss)
        clear.assert_called_once()
        for tab in tabs:tab.update_window_title_bars.assert_called_once()

    def test_reload_shortcut_and_installer_include_the_helper(self):
        config=(ROOT/'config/kitty.conf').read_text()
        self.assertIn('map ctrl+shift+f5 combine : load_config_file : kitten reload_pane_controls.py',config)
        self.assertIn('reload_pane_controls.py',(ROOT/'install.sh').read_text())


if __name__=='__main__':
    unittest.main()
