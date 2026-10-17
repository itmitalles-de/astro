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


class SplitControlsTests(unittest.TestCase):
    def test_codex_launcher_is_not_a_title_bar_control(self):
        title_bar=SimpleNamespace(screen=SimpleNamespace(columns=200),
                                  geometry=SimpleNamespace(left=0,right=1600),cell_width=8)
        actions=[item[0] for item in bar._button_cells(title_bar,expanded=True)]
        self.assertEqual(actions[:2],['add_right','add_below'])
        self.assertNotIn('codex_below',actions)
        self.assertNotIn('codex_below',bar._TOOLTIPS)

    def test_shift_is_captured_on_mouse_press(self):
        from unittest.mock import Mock
        state={'original':Mock(),'pressed':{}}
        window=SimpleNamespace(id=2)
        boss=SimpleNamespace(**{bar._STATE_ATTR:state},window_id_map={2:window},
                             set_active_window=Mock(),os_window_map={7:SimpleNamespace(recent_title_bar_mouse_events=[])})
        with patch.object(bar,'_hit_test',return_value='add_right'), patch.object(bar,'_activate') as activate:
            bar._handle_title_bar_mouse(boss,7,2,1,1,bar.fdt.GLFW_MOUSE_BUTTON_LEFT,
                                        bar.fdt.GLFW_MOD_SHIFT,bar.fdt.GLFW_PRESS)
            bar._handle_title_bar_mouse(boss,7,2,1,1,bar.fdt.GLFW_MOUSE_BUTTON_LEFT,
                                        0,bar.fdt.GLFW_RELEASE)
        activate.assert_called_once_with(boss,window,'add_right',bar.fdt.GLFW_MOD_SHIFT)

    def test_full_span_split_preserves_existing_tree_and_sizes(self):
        from unittest.mock import Mock
        from kitty.layout.splits import Pair
        self.assertTrue(hasattr(bar,'_launch_full_span'),'whole-row/column launcher is missing')
        for horizontal in (True,False):
            for single in (False,True):
                with self.subTest(horizontal=horizontal,single=single):
                    root=Pair(True)
                    if single:
                        root.one=2
                        fraction=1.0
                    else:
                        left=Pair(False); left.one=1; left.two=2; left.bias=.4
                        right=Pair(False); right.one=3; right.two=4; right.bias=.6
                        root.one=left; root.two=right; root.bias=.35
                        fraction=.35 if horizontal else .6
                    before=root.serialize()
                    layout=SimpleNamespace(name='splits',pairs_root=root)
                    tab=SimpleNamespace(current_layout=layout,relayout=Mock())
                    tab.windows=SimpleNamespace(group_for_window=lambda window:SimpleNamespace(id=window.id))
                    source=SimpleNamespace(id=2,tabref=lambda:tab)
                    added=SimpleNamespace(id=5)
                    def launch(*args,**kwargs):
                        pair=layout.pairs_root.pair_for_window(2)
                        pair.split_and_add(2,5,horizontal,True)
                        return added
                    with patch('kitty.launch.launch',side_effect=launch):
                        bar._launch_full_span(SimpleNamespace(),source,horizontal)
                    result=layout.pairs_root
                    self.assertEqual(result.horizontal,horizontal)
                    self.assertEqual(result.one.serialize(),before)
                    self.assertEqual(result.two,5)
                    self.assertAlmostEqual(result.bias,1/(1+fraction))
                    self.assertEqual(set(result.all_window_ids()),{2,5} if single else {1,2,3,4,5})
                    tab.relayout.assert_called_once()

    def test_regular_and_control_clicks_keep_the_local_split(self):
        import inspect
        from unittest.mock import Mock
        self.assertIn('modifiers',inspect.signature(bar._activate).parameters)
        for action,location in [('add_right','vsplit'),('add_below','hsplit')]:
            for modifiers in (0,bar.fdt.GLFW_MOD_CONTROL):
                boss=SimpleNamespace(set_active_window=Mock(),combine=Mock())
                tab=SimpleNamespace(current_layout=SimpleNamespace(name='splits'))
                window=SimpleNamespace(id=2,tabref=lambda:tab)
                bar._activate(boss,window,action,modifiers)
                boss.combine.assert_called_once_with(
                    f'launch --cwd=current --location={location} --next-to=id:2 --source-window=id:2',
                    window_for_dispatch=window,dispatch_type='MouseEvent',raise_error=True)

    def test_keyboard_kitten_entrypoint_dispatches_pane_actions_and_reports_errors(self):
        from unittest.mock import Mock
        window=SimpleNamespace(id=2)
        boss=SimpleNamespace(**{bar._STATE_ATTR:{'groups':{}}},window_id_map={2:window},show_error=Mock())
        self.assertTrue(getattr(bar.handle_result,'no_ui',False))
        with patch.object(bar,'_activate') as activate:
            bar.handle_result(['window_title_bar.py','full_right'],None,2,boss)
            bar.handle_result(['window_title_bar.py','full_below'],None,2,boss)
            bar.handle_result(['window_title_bar.py','group'],None,2,boss)
            bar.handle_result(['window_title_bar.py','equal_width'],None,2,boss)
            bar.handle_result(['window_title_bar.py','equal_height'],None,2,boss)
            bar.handle_result(['window_title_bar.py','copy_command'],None,2,boss)
            bar.handle_result(['window_title_bar.py','shortcuts'],None,2,boss)
        self.assertEqual(activate.call_args_list,[
            unittest.mock.call(boss,window,'add_right',bar.fdt.GLFW_MOD_SHIFT),
            unittest.mock.call(boss,window,'add_below',bar.fdt.GLFW_MOD_SHIFT),
            unittest.mock.call(boss,window,'group'),
            unittest.mock.call(boss,window,'equal_width'),
            unittest.mock.call(boss,window,'equal_height'),
            unittest.mock.call(boss,window,'copy_command'),
            unittest.mock.call(boss,window,'shortcuts'),
        ])
        with patch.object(bar,'_activate',side_effect=RuntimeError('equalize failed')),patch.object(bar,'_report_failure') as report:
            bar.handle_result(['window_title_bar.py','equal_width'],None,2,boss)
        report.assert_called_once()
        boss.show_error.assert_called_once_with('Astro pane controls','equalize failed')


if __name__ == '__main__':
    unittest.main()
