# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location('astro_agy_titles', Path(__file__).resolve().parents[1] / 'config/window_title_bar.py')
assert spec is not None and spec.loader is not None
bar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bar)


class AgyTitleTests(unittest.TestCase):
    def test_each_process_uses_its_own_lock_and_unicode_annotation(self):
        sessions = ['11111111-1111-1111-1111-111111111111',
                    '22222222-2222-2222-2222-222222222222']
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'antigravity-cli'
            (root / 'annotations').mkdir(parents=True)
            for session, title in zip(sessions, ['MONTU', 'Größe "zwei"']):
                (root / 'annotations' / (session + '.pbtxt')).write_text('title:' + json.dumps(title, ensure_ascii=False))
            for pid, session, title in zip([123, 456], sessions, ['MONTU', 'Größe "zwei"']):
                descriptors = [SimpleNamespace(path=f'/proc/{pid}/fd/{fd}') for fd in range(3)]
                scanner = MagicMock()
                scanner.__enter__.return_value = descriptors
                targets = ['socket:[123]', '/dev/pts/6', str(root / 'presence' / (session + '.lock'))]
                with patch('os.tcgetpgrp', return_value=pid), patch('os.scandir', return_value=scanner) as scan, patch('os.readlink', side_effect=targets):
                    window = SimpleNamespace(child=SimpleNamespace(child_fd=10))
                    self.assertEqual(bar._agy_session_title(window), title)
                    scan.assert_called_once_with(f'/proc/{pid}/fd')

    def test_missing_annotation_or_exited_process_keeps_terminal_title(self):
        window = SimpleNamespace(id=1, child=SimpleNamespace(child_fd=10))
        with patch('os.tcgetpgrp', side_effect=ProcessLookupError), patch.object(bar, '_detect_agent', return_value='agy'):
            self.assertEqual(bar._agent_title(window, 'agy', {}), ('agy', ''))
        with patch('os.tcgetpgrp', side_effect=PermissionError):
            self.assertIsNone(bar._agy_session_title(window))

    def test_real_open_lock_handles_missing_malformed_and_control_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'antigravity-cli'
            (root / 'presence').mkdir(parents=True)
            (root / 'annotations').mkdir()
            session = '11111111-1111-1111-1111-111111111111'
            annotation = root / 'annotations' / (session + '.pbtxt')
            window = SimpleNamespace(child=SimpleNamespace(child_fd=10))
            with (root / 'presence' / (session + '.lock')).open('w'), patch('os.tcgetpgrp', return_value=os.getpid()):
                self.assertIsNone(bar._agy_session_title(window))
                annotation.write_text('title:"unfinished')
                self.assertIsNone(bar._agy_session_title(window))
                annotation.write_bytes(b'raw: "\xff"\ntitle: "MONTU\\n\\u001b"\n')
                self.assertEqual(bar._agy_session_title(window), 'MONTU')
                annotation.unlink()
                os.mkfifo(annotation)
                self.assertIsNone(bar._agy_session_title(window))

    def test_explicit_rename_punctuation_is_preserved_while_osc_spinners_are_stripped(self):
        window = SimpleNamespace(id=1, child=SimpleNamespace(child_fd=10))
        with patch.object(bar, '_detect_agent', return_value='agy'), patch.object(bar, '_agy_session_title', return_value='[#42] Release'):
            self.assertEqual(bar._agent_title(window, '⠋ agy', {}), ('agy', '[#42] Release'))
        with patch.object(bar, '_detect_agent', return_value='agy'), patch.object(bar, '_agy_session_title', return_value=None):
            self.assertEqual(bar._agent_title(window, '⠋ Working', {}), ('agy', 'Working'))

    def test_rename_and_session_switch_refresh_without_an_osc_title_change(self):
        window = SimpleNamespace(id=1)
        tab = SimpleNamespace(windows=SimpleNamespace(iter_all_layoutable_groups=lambda **kw: [SimpleNamespace(windows=[window])]))
        boss = SimpleNamespace(os_window_map={1: SimpleNamespace(active_tab=tab)})
        state = {}
        with patch.object(bar, '_detect_agent', return_value='agy'), patch.object(bar, '_agy_session_title', side_effect=['MONTU', 'MONTU', 'HERMES', None]):
            self.assertEqual(bar._agent_title(window, 'agy', state), ('agy', 'MONTU'))
            self.assertEqual(bar._scan_agents(boss, state), set())
            self.assertEqual(bar._scan_agents(boss, state), {1})
            self.assertEqual(state['agents'][1][3], 'HERMES')
            self.assertEqual(bar._scan_agents(boss, state), {1})
            self.assertEqual(state['agents'][1][3], '')


if __name__ == '__main__':
    unittest.main()
