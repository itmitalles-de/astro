# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/'tools/check.py'
spec=importlib.util.spec_from_file_location('astro_check_tests',PATH)
assert spec is not None and spec.loader is not None
check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)


class CheckRunnerTests(unittest.TestCase):
    def repository(self,folder,text):
        folder=Path(folder)
        subprocess.run(['git','init','--quiet',str(folder)],check=True,capture_output=True)
        (folder/'sample.txt').write_text(text)
        subprocess.run(['git','add','sample.txt'],cwd=folder,check=True)
        subprocess.run(['git','-c','user.name=Astro QA','-c','user.email=qa@example.invalid','-c','commit.gpgsign=false','-c','core.hooksPath=/dev/null','commit','--quiet','-m','fixture'],cwd=folder,check=True,capture_output=True)
        return folder

    def test_whitespace_is_detected_in_a_clean_checkout(self):
        self.assertTrue(hasattr(check,'check_whitespace'),'checks must inspect committed source, not only an empty working-tree diff')
        with tempfile.TemporaryDirectory() as folder:
            root=self.repository(folder,'committed trailing whitespace \n')
            empty_diff=subprocess.run(['git','diff','--check'],cwd=root,capture_output=True)
            self.assertEqual(empty_diff.returncode,0,'fixture must reproduce the old CI blind spot')
            with patch.object(check,'ROOT',root),self.assertRaisesRegex(ValueError,'trailing whitespace'):
                check.check_whitespace()

    def test_clean_committed_source_passes(self):
        self.assertTrue(hasattr(check,'check_whitespace'))
        with tempfile.TemporaryDirectory() as folder:
            root=self.repository(folder,'clean text\n')
            with patch.object(check,'ROOT',root):
                check.check_whitespace()

    def test_ci_installs_the_cairo_foreign_type_bridge(self):
        workflow=(PATH.parents[1]/'.github/workflows/checks.yml').read_text()
        packages=workflow.partition('sudo apt-get install')[2].partition('      - name:')[0].split()
        self.assertIn('python3-gi-cairo',packages,
                      'PyGObject needs the Cairo foreign-type bridge as well as pycairo to render SVGs')


if __name__=='__main__':
    unittest.main()
