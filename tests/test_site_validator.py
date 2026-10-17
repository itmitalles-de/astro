# SPDX-License-Identifier: GPL-3.0-or-later
"""Failure-path coverage for the offline Pages artifact gate."""
import importlib.util
from pathlib import Path
import shutil
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('astro_site_validator', ROOT / '.github/check-site.py')
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class SiteArtifactTests(unittest.TestCase):
    def artifact(self, folder):
        site = Path(folder) / 'site'
        shutil.copytree(ROOT / 'site', site)
        return site

    def test_missing_dynamic_artwork_module_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            site = self.artifact(folder)
            self.assertIn("import('./ascii-scene.mjs')", (site / 'app.mjs').read_text())
            (site / 'ascii-scene.mjs').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing local asset: ./ascii-scene.mjs'):
                validator.check(site)

    def test_js_module_dependencies_are_checked_as_well_as_mjs(self):
        with tempfile.TemporaryDirectory() as folder:
            site = self.artifact(folder)
            (site / 'feature.js').write_text("export { feature } from './missing-feature.mjs';\n")
            with self.assertRaisesRegex(ValueError, 'Missing local asset: ./missing-feature.mjs'):
                validator.check(site)

    def test_external_scripts_cannot_be_added_to_the_csp(self):
        with tempfile.TemporaryDirectory() as folder:
            site = self.artifact(folder)
            html = site / 'index.html'
            html.write_text(html.read_text().replace("script-src 'self'", "script-src 'self' https:"))
            with self.assertRaisesRegex(ValueError, 'CSP.*script-src'):
                validator.check(site)

    def test_stylesheets_must_be_self_hosted_too(self):
        with tempfile.TemporaryDirectory() as folder:
            site = self.artifact(folder)
            html = site / 'index.html'
            html.write_text(html.read_text().replace('href="style.css"', 'href="https://example.invalid/theme.css"'))
            with self.assertRaisesRegex(ValueError, 'link must be self-hosted'):
                validator.check(site)

    def test_even_unreferenced_files_cannot_escape_the_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            site = self.artifact(folder)
            outside = Path(folder) / 'private-fixture.txt'
            outside.write_text('private test fixture, not a real credential\n')
            (site / 'leftover.txt').symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'escapes the artifact'):
                validator.check(site)

    def test_special_files_are_rejected_before_any_asset_read_can_block(self):
        with tempfile.TemporaryDirectory() as folder:
            site = self.artifact(folder)
            os.mkfifo(site / 'leftover.css')
            executable = shutil.which('python3')
            assert executable is not None
            try:
                result = subprocess.run([executable, str(ROOT / '.github/check-site.py'), str(site)],
                                        capture_output=True, text=True, timeout=1)
            except subprocess.TimeoutExpired:
                self.fail('the static artifact checker blocked while opening a FIFO')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Non-regular artifact entry', result.stderr)

    def test_a_truncated_product_capture_is_not_accepted_as_a_real_png(self):
        with tempfile.TemporaryDirectory() as folder:
            site = self.artifact(folder)
            image = site / 'assets/workspace.png'
            image.write_bytes(image.read_bytes()[:24])
            with self.assertRaisesRegex(ValueError, 'PNG'):
                validator.check(site)


if __name__ == '__main__':
    unittest.main()
