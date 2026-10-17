# SPDX-License-Identifier: GPL-3.0-or-later
"""Group equalization against Kitty's real split and cell-layout algorithms."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import kitty.layout.base as native_base
from kitty.fast_data_types import Region
from kitty.layout.base import Layout, lgd
from kitty.layout.splits import Pair


PATH = Path(__file__).resolve().parents[1] / 'config/window_title_bar.py'
spec = importlib.util.spec_from_file_location('astro_group_equalize', PATH)
if spec is None or spec.loader is None:
    raise RuntimeError('Could not load the pane controls')
bar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bar)


def pair(horizontal, one, two, bias=.5):
    node = Pair(horizontal)
    node.one, node.two, node.bias = one, two, bias
    return node


class GeometryGroup:
    """Only the native window sink is replaced; Pair and Layout remain real."""
    def __init__(self, window_id, border=1, padding=0):
        self.id = self.active_window_id = window_id
        self.windows = [SimpleNamespace(id=window_id)]
        self.border, self.padding = border, padding

    def effective_border(self):
        return self.border

    def decoration(self, which, border_mult=1):
        return self.padding + border_mult * self.border

    def set_geometry(self, geometry):
        self.geometry = geometry


class GroupEqualizeTests(unittest.TestCase):
    def setUp(self):
        options = patch.multiple(lgd, cell_width=10, cell_height=20,
                                 draw_minimal_borders=True, alignment_x=0, alignment_y=0)
        options.start()
        self.addCleanup(options.stop)
        language = patch.object(bar, '_LANGUAGE', 'en')
        language.start()
        self.addCleanup(language.stop)
        self.viewports = {}
        self.options = SimpleNamespace(draw_minimal_borders=True,
                                       window_margin_width=(0, 0, 0, 0),
                                       draw_window_borders_for_single_window=False)
        for native_patch in (
                patch.object(native_base, 'viewport_for_window', side_effect=self.viewports.__getitem__),
                patch.object(native_base, 'get_options', return_value=self.options)):
            native_patch.start()
            self.addCleanup(native_patch.stop)

    def native_layout(self, width, height, cell_width, cell_height):
        layout = object.__new__(Layout)
        layout.os_window_id = len(self.viewports) + 1
        self.viewports[layout.os_window_id] = (
            Region((0, 0, width - 1, height - 1, width, height)), None,
            width, height, cell_width, cell_height)
        layout.name = 'splits'
        layout.blank_rects = []
        return layout

    def workspace(self, root, members, width=1000, height=1000, border=1,
                  padding: int | dict[int, int] = 0, cell_width=10, cell_height=20):
        groups = {wid: GeometryGroup(wid, border, padding.get(wid, 0) if isinstance(padding, dict) else padding)
                  for wid in root.all_window_ids()}
        layout = self.native_layout(width, height, cell_width, cell_height)
        layout.pairs_root = root

        def relayout():
            # Kitty refreshes these process-global metrics on every native layout.
            layout._set_dimensions(tab.windows)
            layout.blank_rects = []
            root.layout_pair(0, 0, width, height, groups, layout)

        tab = SimpleNamespace(current_layout=layout,
                              windows=SimpleNamespace(iter_all_layoutable_groups=lambda: iter(groups.values()),
                                                      has_more_than_one_visible_group=len(groups) > 1),
                              relayout=Mock(side_effect=relayout))
        windows = {}
        for group in groups.values():
            window = group.windows[0]
            window.tabref = lambda: tab
            windows[window.id] = window
        state = {'groups': {wid: 1 for wid in members}, 'pressed': {}, 'original': Mock()}
        boss = SimpleNamespace(**{bar._STATE_ATTR: state}, window_id_map=windows,
                               os_window_map={}, set_active_window=Mock(), show_error=Mock())
        relayout()
        return SimpleNamespace(root=root, groups=groups, tab=tab, boss=boss, windows=windows)

    def geometry(self, workspace):
        return {wid: group.geometry for wid, group in workspace.groups.items()}

    def dimensions(self, workspace):
        return {wid: (group.geometry.right - group.geometry.left,
                      group.geometry.bottom - group.geometry.top)
                for wid, group in workspace.groups.items()}

    def check_equalized(self, workspace, members, horizontal, before):
        after = self.dimensions(workspace)
        axis, other_axis = (0, 1) if horizontal else (1, 0)
        cell = lgd.cell_width if horizontal else lgd.cell_height
        sizes = [after[wid][axis] for wid in members]
        self.assertGreaterEqual(min(sizes), cell)
        self.assertLessEqual(max(sizes) - min(sizes), cell)
        for wid in after:
            if wid not in members:
                self.assertEqual(after[wid], before[wid], f'Outside pane {wid} changed dimensions')
            self.assertEqual(after[wid][other_axis], before[wid][other_axis])

    def check_rejected(self, workspace, horizontal):
        tree_before = workspace.root.serialize()
        geometry_before = self.geometry(workspace)
        with self.assertRaisesRegex(RuntimeError, 'Layout unchanged'):
            bar._equalize_group(workspace.boss, workspace.windows[1], horizontal)
        self.assertEqual(workspace.root.serialize(), tree_before)
        self.assertEqual(self.geometry(workspace), geometry_before)
        workspace.tab.relayout.assert_not_called()

    def test_infeasible_shared_outsider_preserves_tree_and_geometry_on_both_axes(self):
        for horizontal in (True, False):
            with self.subTest(horizontal=horizontal):
                root = pair(horizontal, pair(not horizontal, 1, 2), 3, .3)
                workspace = self.workspace(root, {1, 3})
                tree_before, geometry_before = root.serialize(), self.geometry(workspace)
                error = None
                try:
                    bar._equalize_group(workspace.boss, workspace.windows[1], horizontal)
                except RuntimeError as caught:
                    error = caught
                self.assertEqual(self.geometry(workspace), geometry_before,
                                 'An infeasible equalization must not resize the outside-group pane')
                self.assertEqual(root.serialize(), tree_before)
                self.assertIsInstance(error, RuntimeError)
                self.assertIn('Layout unchanged', str(error))
                workspace.tab.relayout.assert_not_called()

    def test_foreign_native_font_grid_cannot_resize_source_outsider(self):
        for horizontal in (True, False):
            with self.subTest(horizontal=horizontal):
                root = pair(horizontal, 1, pair(horizontal, 2, 3, .2), .28)
                width, height = (449, 500) if horizontal else (500, 449)
                workspace = self.workspace(root, {1, 2}, width, height, border=3, padding=3)
                before = self.dimensions(workspace)
                if horizontal:
                    self.assertEqual(workspace.groups[3].geometry.xnum, 24)
                foreign = self.workspace(pair(False, 4, 5), set(), 612, 713,
                                         cell_width=17, cell_height=29)
                self.assertNotEqual(foreign.tab.current_layout.os_window_id,
                                    workspace.tab.current_layout.os_window_id)
                self.assertEqual((lgd.cell_width, lgd.cell_height), (17, 29))
                # No source-global restoration here: the action must synchronize it.
                action = 'equal_width' if horizontal else 'equal_height'
                bar._activate(workspace.boss, workspace.windows[1], action)
                self.check_equalized(workspace, {1, 2}, horizontal, before)
                if horizontal:
                    self.assertEqual(workspace.groups[3].geometry.xnum, 24)

    def test_foreign_native_border_context_is_refreshed_on_both_axes(self):
        for horizontal in (True, False):
            with self.subTest(horizontal=horizontal), \
                    patch.object(self.options, 'draw_window_borders_for_single_window', True):
                root = pair(horizontal, 1, pair(horizontal, 2, 3, .2), .28)
                width, height = (449, 500) if horizontal else (500, 449)
                workspace = self.workspace(root, {1, 2}, width, height, border=3, padding=3)
                before = self.dimensions(workspace)
                self.assertTrue(lgd.draw_minimal_borders)
                single = Pair()
                single.one = 4
                foreign = self.workspace(single, set(), 612, 713)
                self.assertFalse(foreign.tab.windows.has_more_than_one_visible_group)
                self.assertFalse(lgd.draw_minimal_borders)
                action = 'equal_width' if horizontal else 'equal_height'
                bar._activate(workspace.boss, workspace.windows[1], action)
                self.assertTrue(lgd.draw_minimal_borders)
                self.check_equalized(workspace, {1, 2}, horizontal, before)

    def test_foreign_context_does_not_break_atomic_rejection(self):
        for horizontal in (True, False):
            with self.subTest(horizontal=horizontal):
                root = pair(horizontal, pair(not horizontal, 1, 2), 3, .3)
                workspace = self.workspace(root, {1, 3})
                self.workspace(pair(True, 4, 5), set(), 612, 713,
                               cell_width=17, cell_height=29)
                self.assertEqual((lgd.cell_width, lgd.cell_height), (17, 29))
                self.check_rejected(workspace, horizontal)
                self.assertEqual((lgd.cell_width, lgd.cell_height), (10, 20))

    def test_feasible_group_equalizes_beside_an_outsider_on_both_axes(self):
        for horizontal in (True, False):
            with self.subTest(horizontal=horizontal):
                root = pair(horizontal, pair(horizontal, 1, 2, .2), 3, .6)
                workspace = self.workspace(root, {1, 2})
                before = self.dimensions(workspace)
                bar._equalize_group(workspace.boss, workspace.windows[1], horizontal)
                self.check_equalized(workspace, {1, 2}, horizontal, before)
                self.assertNotEqual(self.dimensions(workspace)[1], before[1])
                workspace.tab.relayout.assert_called_once()

    def test_feasible_orthogonal_outsider_does_not_disable_equalization(self):
        for horizontal in (True, False):
            with self.subTest(horizontal=horizontal):
                root = pair(horizontal, pair(not horizontal, 1, 2),
                            pair(horizontal, 3, 4, .2), 1 / 3)
                width, height = (604, 1000) if horizontal else (1000, 604)
                workspace = self.workspace(root, {1, 3, 4}, width, height)
                before = self.dimensions(workspace)
                bar._equalize_group(workspace.boss, workspace.windows[1], horizontal)
                self.check_equalized(workspace, {1, 3, 4}, horizontal, before)
                self.assertNotEqual(self.dimensions(workspace)[3], before[3])
                self.assertEqual(root.one.bias, .5, 'The orthogonal split must not change')

    def test_feasible_mixed_rows_with_different_member_counts(self):
        for horizontal in (True, False):
            with self.subTest(horizontal=horizontal):
                top = pair(horizontal, pair(horizontal, 1, 2, .2), 3, .7)
                bottom = pair(horizontal, 4, 5, .35)
                root = pair(not horizontal, top, bottom, .4)
                workspace = self.workspace(root, {1, 2, 4})
                before = self.dimensions(workspace)
                bar._equalize_group(workspace.boss, workspace.windows[1], horizontal)
                self.check_equalized(workspace, {1, 2, 4}, horizontal, before)
                self.assertNotEqual(self.dimensions(workspace)[1], before[1])
                self.assertEqual(root.bias, .4)

    def test_complete_group_and_ungrouped_whole_tab_still_equalize(self):
        for horizontal in (True, False):
            for grouped in (True, False):
                with self.subTest(horizontal=horizontal, grouped=grouped):
                    root = pair(horizontal, pair(not horizontal, 1, 2, .35),
                                pair(not horizontal, 3, 4, .65), .25)
                    workspace = self.workspace(root, {1, 2, 3, 4} if grouped else set())
                    before = self.dimensions(workspace)
                    bar._equalize_group(workspace.boss, workspace.windows[1], horizontal)
                    self.check_equalized(workspace, {1, 2, 3, 4}, horizontal, before)
                    self.assertNotEqual(self.dimensions(workspace)[1], before[1])
                    self.assertEqual((root.one.bias, root.two.bias), (.35, .65))

    def test_cell_rounding_padding_and_borders_follow_native_layout(self):
        for horizontal in (True, False):
            for minimal in (True, False):
                for border in (0, 1, 3):
                    with self.subTest(horizontal=horizontal, minimal=minimal, border=border):
                        root = pair(horizontal, 1, pair(horizontal, 2, 3, .2), .2)
                        with patch.object(self.options, 'draw_minimal_borders', minimal):
                            workspace = self.workspace(root, {1, 2, 3}, 1001, 1001,
                                                       border, {1: 0, 2: 3, 3: 7})
                            before = self.dimensions(workspace)
                            bar._equalize_group(workspace.boss, workspace.windows[1], horizontal)
                            self.check_equalized(workspace, {1, 2, 3}, horizontal, before)
                            # Repeating an already equalized action must not drift biases.
                            tree, geometry = root.serialize(), self.geometry(workspace)
                            workspace.tab.relayout.reset_mock()
                            bar._equalize_group(workspace.boss, workspace.windows[1], horizontal)
                            self.assertEqual(root.serialize(), tree)
                            self.assertEqual(self.geometry(workspace), geometry)
                            workspace.tab.relayout.assert_not_called()

    def test_one_cell_difference_is_allowed_only_when_exact_sizes_do_not_fit(self):
        for horizontal in (True, False):
            with self.subTest(horizontal=horizontal):
                cell = lgd.cell_width if horizontal else lgd.cell_height
                target = 4 * cell + 1
                width, height = (target, 1000) if horizontal else (1000, target)
                root = pair(horizontal, 1, 2, .2)
                workspace = self.workspace(root, {1, 2}, width, height)
                before = self.dimensions(workspace)
                bar._equalize_group(workspace.boss, workspace.windows[1], horizontal)
                self.check_equalized(workspace, {1, 2}, horizontal, before)
                sizes = [dimensions[0 if horizontal else 1]
                         for dimensions in self.dimensions(workspace).values()]
                self.assertEqual(max(sizes) - min(sizes), cell)

    def test_insufficient_space_is_rejected_without_partial_mutation(self):
        for horizontal in (True, False):
            with self.subTest(horizontal=horizontal):
                cell = lgd.cell_width if horizontal else lgd.cell_height
                target = 2 * (cell + 6) + 1  # One pixel short of two cells, padding and borders.
                width, height = (target, 1000) if horizontal else (1000, target)
                workspace = self.workspace(pair(horizontal, 1, 2, .4), {1, 2},
                                           width, height, padding=3)
                self.check_rejected(workspace, horizontal)

    def test_conflict_in_later_branch_cannot_leave_earlier_biases_changed(self):
        for horizontal in (True, False):
            with self.subTest(horizontal=horizontal):
                top = pair(horizontal, 1, 2, .2)
                bottom = pair(horizontal, 3, 4, .8)
                workspace = self.workspace(pair(not horizontal, top, bottom), {1, 2, 3})
                self.check_rejected(workspace, horizontal)

    def test_single_group_member_is_already_equal_and_is_a_noop(self):
        workspace = self.workspace(pair(True, 1, 2, .25), {1})
        tree, geometry = workspace.root.serialize(), self.geometry(workspace)
        bar._equalize_group(workspace.boss, workspace.windows[1], True)
        self.assertEqual(workspace.root.serialize(), tree)
        self.assertEqual(self.geometry(workspace), geometry)
        workspace.tab.relayout.assert_not_called()

    def test_shared_extent_matches_exhaustive_small_native_layouts(self):
        # This tree has only one split on the selected axis. Enumerating every
        # native pixel boundary is an independent oracle for its feasible sizes.
        for horizontal in (True, False):
            cell = lgd.cell_width if horizontal else lgd.cell_height
            target = 6 * cell + 9
            width, height = (target, 1000) if horizontal else (1000, target)
            for border in (0, 1, 3):
                for padding in (0, 2):
                    for bias in (.2, .4, .6, .8):
                        with self.subTest(horizontal=horizontal, border=border, padding=padding, bias=bias):
                            root = pair(horizontal, pair(not horizontal, 1, 2), 3, bias)
                            workspace = self.workspace(root, {1, 3}, width, height, border, padding)
                            before, geometry = self.dimensions(workspace), self.geometry(workspace)
                            feasible = exact = False
                            axis = 0 if horizontal else 1
                            for first in range(target + 1):
                                root.bias = (first + root.border_width + .5) / target
                                workspace.tab.relayout()
                                dims = self.dimensions(workspace)
                                one, three = dims[1][axis], dims[3][axis]
                                if dims[2] == before[2] and min(one, three) >= cell and abs(one - three) <= cell:
                                    feasible = True
                                    exact |= one == three
                            root.bias = bias
                            workspace.tab.relayout()
                            workspace.tab.relayout.reset_mock()
                            self.assertEqual(self.geometry(workspace), geometry)
                            if feasible:
                                bar._equalize_group(workspace.boss, workspace.windows[1], horizontal)
                                self.check_equalized(workspace, {1, 3}, horizontal, before)
                                if exact:
                                    dims = self.dimensions(workspace)
                                    self.assertEqual(dims[1][axis], dims[3][axis])
                            else:
                                self.check_rejected(workspace, horizontal)

    def test_infeasibility_uses_existing_localized_mouse_error_and_clears_press(self):
        for horizontal in (True, False):
            for language in ('de', 'en'):
                with self.subTest(horizontal=horizontal, language=language):
                    root = pair(horizontal, pair(not horizontal, 1, 2), 3, .3)
                    workspace = self.workspace(root, {1, 3})
                    tree, geometry = root.serialize(), self.geometry(workspace)
                    self.workspace(pair(True, 4, 5), set(), 612, 713,
                                   cell_width=17, cell_height=29)
                    action = 'equal_width' if horizontal else 'equal_height'
                    event = (workspace.boss, 7, 1, 10, 10, bar.fdt.GLFW_MOUSE_BUTTON_LEFT, 0)
                    with patch.object(bar, '_LANGUAGE', language), \
                            patch.object(bar, '_hit_test', return_value=action), \
                            patch.object(bar, '_report_failure') as report:
                        bar._handle_title_bar_mouse(*event, bar.fdt.GLFW_PRESS)
                        bar._handle_title_bar_mouse(*event, bar.fdt.GLFW_RELEASE)
                        workspace.boss.show_error.assert_called_once_with(
                            'Astro pane controls', bar._message('equalize_unavailable'))
                        report.assert_called_once()
                        state = getattr(workspace.boss, bar._STATE_ATTR)
                        self.assertEqual(state['pressed'], {})
                        state['original'].assert_not_called()
                        # The rejected click must not poison the following input lifecycle.
                        with patch.object(bar, '_activate') as activate:
                            bar._handle_title_bar_mouse(*event, bar.fdt.GLFW_PRESS)
                            bar._handle_title_bar_mouse(*event, bar.fdt.GLFW_RELEASE)
                            activate.assert_called_once_with(workspace.boss, workspace.windows[1], action, 0)
                    self.assertEqual(root.serialize(), tree)
                    self.assertEqual(self.geometry(workspace), geometry)
                    workspace.tab.relayout.assert_not_called()


if __name__ == '__main__':
    unittest.main()
