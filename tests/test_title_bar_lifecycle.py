# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

PATH=Path(__file__).resolve().parents[1]/'config/window_title_bar.py'


def renderer(name):
    spec=importlib.util.spec_from_file_location(name,PATH)
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class TitleBarLifecycleTests(unittest.TestCase):
    def test_failed_pointer_cleanup_does_not_disable_hover_timer(self):
        first=renderer('astro_failure_first');second=renderer('astro_failure_second')
        boss=SimpleNamespace(handle_window_title_bar_mouse=lambda *args: None,set_active_window=lambda *args: None,combine=lambda *args: None)
        with patch.object(first.fdt,'add_timer',side_effect=[101,202]),patch.object(first.fdt,'remove_timer'),patch.object(second,'_report_failure') as report:
            state=first._ensure_installed(boss)
            state['pointer']=SimpleNamespace(close=Mock(side_effect=RuntimeError('simulated cleanup failure')))
            failure=None
            try:second._ensure_installed(boss)
            except Exception as error:failure=error
            self.assertIsNone(failure,'native cleanup errors must not break pane controls')
            self.assertEqual(state.get('timer'),202)
            report.assert_called_once()

    def test_reload_releases_cached_pointer_backend(self):
        first=renderer('astro_pointer_first');second=renderer('astro_pointer_second')
        boss=SimpleNamespace(handle_window_title_bar_mouse=lambda *args: None,set_active_window=lambda *args: None,combine=lambda *args: None)
        with patch.object(first.fdt,'add_timer',return_value=101),patch.object(first.fdt,'remove_timer'):
            state=first._ensure_installed(boss)
            pointer=SimpleNamespace(close=Mock())
            state['pointer']=pointer
            second._ensure_installed(boss)
            pointer.close.assert_called_once_with()
            self.assertIsNone(state.get('pointer'))

    def test_unavailable_pointer_switches_timer_to_agent_scan_interval(self):
        module=renderer('astro_adaptive_timer')
        window=SimpleNamespace(id=1)
        tab=SimpleNamespace(windows=SimpleNamespace(iter_all_layoutable_groups=lambda **kw:[]))
        boss=SimpleNamespace(handle_window_title_bar_mouse=lambda *args: None,set_active_window=lambda *args: None,
                             combine=lambda *args: None,os_window_map={1:SimpleNamespace(active_tab=tab)})
        with patch.object(module.fdt,'add_timer',side_effect=[101,202]) as add,patch.object(module.fdt,'remove_timer') as remove,patch.object(module.fdt,'current_focused_os_window_id',return_value=1),patch.object(module,'_X11Pointer',side_effect=RuntimeError('no display')),patch.object(module,'_report_failure'):
            state=module._ensure_installed(boss)
            self.assertEqual(state['timer'],101)
            with self.assertRaises(module._NoPointer):
                module._pointer_target(boss,state)
            self.assertIs(state['pointer'],False)
            self.assertEqual(state['timer'],202)
            remove.assert_called_once_with(101)
            self.assertEqual(add.call_args_list[1].args,(module._poll_hover,module._AGENT_CACHE_SECONDS,True))

    def test_watcher_renderer_and_reload_keep_one_timer_and_native_handler(self):
        first=renderer('astro_lifecycle_first');second=renderer('astro_lifecycle_second')
        native=lambda *args: None
        boss=SimpleNamespace(handle_window_title_bar_mouse=native,set_active_window=lambda *args: None,combine=lambda *args: None)
        with patch.object(first.fdt,'add_timer',side_effect=[101,202]) as add,patch.object(first.fdt,'remove_timer') as remove:
            state=first._ensure_installed(boss)
            first._ensure_installed(boss)
            self.assertEqual(add.call_count,1)
            reloaded=second._ensure_installed(boss)
            second._ensure_installed(boss)
            self.assertIs(reloaded,state)
            self.assertIs(state['original'],native)
            self.assertIs(boss.handle_window_title_bar_mouse.__func__,second._handle_title_bar_mouse)
            self.assertEqual(state['timer'],202)
            self.assertEqual(add.call_count,2)
            remove.assert_called_once_with(101)


if __name__=='__main__':
    unittest.main()
