# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
import shutil
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

    def test_ci_checkout_does_not_leave_credentials_for_test_processes(self):
        workflow=(PATH.parents[1]/'.github/workflows/checks.yml').read_text()
        checkout=workflow.partition('uses: actions/checkout@')[2].partition('      - name:')[0]
        self.assertIn('persist-credentials: false',checkout)

    @unittest.skipUnless(shutil.which('shellcheck'), 'ShellCheck is optional outside full verification')
    def test_executed_installer_body_is_syntax_checked_not_only_its_wrapper(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.repository(folder,'clean fixture\n')
            for name in ('install.sh','bin/astro','config/astro.bash','config/astro_prompt.bash'):
                target=root/name
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(PATH.parents[1]/name,target)
            script=root/'install.sh'
            script.write_text(script.read_text().replace('\nASTRO_INSTALL_BODY\n', '\nif true; then\nASTRO_INSTALL_BODY\n'))
            # The broken body is quoted data to the wrapper's shell parser.
            wrapper=subprocess.run(['/bin/sh','-n',str(script)],capture_output=True)
            self.assertEqual(wrapper.returncode,0)
            def captured_run(command, *, env=None, timeout=120):
                subprocess.run(command,cwd=root,env=env,timeout=timeout,check=True,capture_output=True)
            with patch.object(check,'ROOT',root),patch.object(check.sys,'argv',['check','--kitty','/usr/bin/true','--require-shellcheck']):
                with patch.object(check,'run',side_effect=captured_run),self.assertRaises(subprocess.CalledProcessError) as failure:
                    check.main()
                self.assertIn('astro-install-body',failure.exception.cmd[-1])


if __name__=='__main__':
    unittest.main()
