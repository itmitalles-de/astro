# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class BrandTests(unittest.TestCase):
    def test_minimal_icon_has_one_explicit_eye_on_reference_side(self):
        svg = ET.parse(ROOT/'assets/astro.svg').getroot()
        shapes = [node for node in svg.iter() if node.tag.rsplit('}', 1)[-1] in {'path','rect','circle','ellipse','polygon'}]
        self.assertLessEqual(len(shapes), 12, 'keep the cat simple, with only a minimal terminal frame')
        window = svg.find(".//*[@id='terminal-window']")
        self.assertIsNotNone(window, 'logo background must look like a terminal window')
        assert window is not None
        self.assertLessEqual(float(window.get('rx','999')), 20, 'corners must only be slightly rounded')
        self.assertIsNotNone(svg.find(".//*[@id='terminal-titlebar']"))
        self.assertIsNotNone(svg.find(".//*[@id='terminal-prompt']"))
        opened = svg.find(".//*[@id='eye-open-viewer-right']")
        closed = svg.find(".//*[@id='eye-closed-viewer-left']")
        self.assertIsNotNone(opened, 'open eye must be on the reference image-right')
        self.assertIsNotNone(closed, 'closed eye must be on the reference image-left')
        self.assertFalse(any('-1' in node.get('transform','') for node in svg.iter()), 'do not mirror the reference')

    def test_ascii_portrait_and_runner_each_have_one_visible_eye(self):
        spec = importlib.util.spec_from_file_location('astro_intro',ROOT/'config/astro_intro.py')
        assert spec is not None and spec.loader is not None
        intro = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(intro)
        for art in (intro.CAT,intro.RUNNER):
            eyes = [(x,y) for y,row in enumerate(art) for x,char in enumerate(row) if char=='@']
            self.assertEqual(len(eyes),1)
            x,y=eyes[0]
            row = art[y]
            center = (row.index('(')+row.index(')'))/2 if '(' in row else len(row.rstrip())/2
            self.assertGreater(x,center, 'visible eye must be on image-right')


if __name__ == '__main__':
    unittest.main()
