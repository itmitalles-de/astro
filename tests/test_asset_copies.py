# SPDX-License-Identifier: GPL-3.0-or-later
"""The web mascot must remain an exact copy of the canonical app mascot."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('astro_asset_checks', ROOT / 'tools/check_assets.py')
assert SPEC is not None and SPEC.loader is not None
assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assets)


class BrandCopyTests(unittest.TestCase):
    def test_web_brand_copies_are_checked_before_regeneration(self):
        self.assertTrue(callable(getattr(assets, 'check_brand_copies', None)),
                        'asset checks must detect stale copies of the canonical mascot')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(ROOT / 'assets', root / 'assets')
            shutil.copytree(ROOT / 'site/assets', root / 'site/assets')
            (root / 'site/assets/astro.svg').write_text('<svg>stale mascot</svg>')
            with patch.object(assets, 'ROOT', root), self.assertRaisesRegex(ValueError, 'site/assets/astro.svg'):
                assets.check_brand_copies()


if __name__ == '__main__':
    unittest.main()
