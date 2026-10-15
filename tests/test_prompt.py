# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT/'config/astro_prompt.bash'


class PromptTests(unittest.TestCase):
    def prompt(self, **extra):
        self.assertTrue(PROMPT.exists(), 'Astro prompt palette is missing')
        env = dict(os.environ, TERM='xterm-kitty', KITTY_WINDOW_ID='42')
        env.pop('NO_COLOR', None)
        env.pop('ASTRO_PROMPT', None)
        env.update(extra)
        result = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-ic', 'PS1=original; source "$1"; printf "%s" "$PS1"', 'astro-prompt-test', str(PROMPT)], env=env, capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 0)
        return result.stdout.decode()

    def test_prompt_uses_astro_colors_and_preserves_shell_placeholders(self):
        prompt = self.prompt()
        for rgb, token in [('167;111;193',r'\u'), ('154;150;143','@'),
                           ('250;189;47',r'\h'), ('154;150;143',':'),
                           ('190;189;186',r'\w'), ('202;170;104',r'\$')]:
            self.assertIn(r'\[\e[38;2;'+rgb+r'm\]'+token,prompt)
        # Exact reference colors are scoped to the prompt, not the ANSI palette.
        for placeholder in [r'\u', r'\h', r'\w', r'\$']:
            self.assertIn(placeholder, prompt)
        self.assertEqual(prompt.count(r'\['), prompt.count(r'\]'))
        self.assertTrue(prompt.endswith(r'\[\e[0m\] '))
        self.assertIn(r'\e]0;', prompt)

    def test_non_kitty_and_opt_out_leave_prompt_unchanged(self):
        self.assertEqual(self.prompt(KITTY_WINDOW_ID=''), 'original')
        self.assertEqual(self.prompt(ASTRO_PROMPT='off'), 'original')

    def test_no_color_and_dumb_terminal_get_plain_prompt(self):
        for env in [{'NO_COLOR':'1'}, {'TERM':'dumb'}]:
            prompt = self.prompt(**env)
            self.assertNotIn(r'\e', prompt)
            self.assertIn(r'\u@\h:\w\$', prompt)


if __name__ == '__main__':
    unittest.main()
