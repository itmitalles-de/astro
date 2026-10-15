# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import unittest
from kitty.config import load_config

ROOT = Path(__file__).resolve().parents[1]


class ClipboardPolicyTests(unittest.TestCase):
    def test_clipboard_reads_are_permanent_but_primary_still_requires_permission(self):
        options = load_config(str(ROOT/'config/kitty.conf'))
        self.assertEqual(set(options.clipboard_control), {
            'write-clipboard', 'write-primary', 'read-clipboard', 'read-primary-ask',
        })


if __name__ == '__main__':
    unittest.main()
