import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WebsiteValidationTests(unittest.TestCase):
    def test_footer_links_to_the_existing_publisher_notices(self):
        html = (ROOT / 'site/index.html').read_text()
        for path in ('impressum.html', 'datenschutz.html'):
            self.assertTrue(f'https://itmitalles.de/{path}' in html, f'Missing publisher notice: {path}')

    def test_first_launch_does_not_require_local_bin_on_path(self):
        html = (ROOT / 'site/index.html').read_text()
        self.assertTrue('"$HOME/.local/bin/astro"</code>' in html, 'First launch must use the absolute per-user launcher path')

    def test_shipped_website_passes_static_validation(self):
        # sys.executable is Kitty when this suite runs through kitty +runpy.
        result = subprocess.run(
            ['python3', str(ROOT / '.github/check-site.py'), str(ROOT / 'site')],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
