#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate generated assets in a private clone, without modifying installed files."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def check_brand_copies():
    for name in ('astro.svg', 'astro-128.png'):
        if (ROOT/'assets'/name).read_bytes() != (ROOT/'site/assets'/name).read_bytes():
            raise ValueError(f'site/assets/{name} is out of sync with the canonical app mascot')


def main():
    check_brand_copies()
    import cairo
    from fontTools.ttLib import TTFont
    with tempfile.TemporaryDirectory(prefix='astro-assets-') as folder:
        folder=Path(folder)
        for name in ('assets','tools'):
            shutil.copytree(ROOT/name,folder/name)
        (folder/'fonts').mkdir()
        env=dict(os.environ,HOME=str(folder/'private-home'))
        subprocess.run([sys.executable,str(folder/'tools/build_brand.py')],env=env,check=True,timeout=30)
        assert (folder/'assets/astro-logo.svg').read_bytes()==(ROOT/'assets/astro-logo.svg').read_bytes(),'wordmark is stale'
        for size in (32,64,128,256,512):
            for parent in (ROOT,folder):
                surface=cairo.ImageSurface.create_from_png(str(parent/f'assets/astro-{size}.png'))
                assert (surface.get_width(),surface.get_height())==(size,size)
        # The default build destination must be repository-local, never a user's fonts.
        subprocess.run([sys.executable,str(folder/'tools/build_pane_icons.py')],env=env,check=True,timeout=30)
        font=folder/'fonts/AstroPaneControls.ttf'
        first=font.read_bytes()
        subprocess.run([sys.executable,str(folder/'tools/build_pane_icons.py'),str(font)],env=env,check=True,timeout=30)
        assert font.read_bytes()==first,'font build is not reproducible'
        with TTFont(font) as fresh,TTFont(ROOT/'fonts/AstroPaneControls.ttf') as shipped:
            assert fresh.getBestCmap()==shipped.getBestCmap(),'font character map is stale'
            for name in fresh.getGlyphOrder():
                assert fresh['hmtx'][name]==shipped['hmtx'][name],f'font metrics differ: {name}'
                assert fresh['glyf'][name].getCoordinates(fresh['glyf'])[:2]==shipped['glyf'][name].getCoordinates(shipped['glyf'])[:2],f'font outline differs: {name}'
        print('PASS: SVG regeneration, all PNG dimensions, font destination, reproducibility and shipped glyphs')


if __name__=='__main__':
    main()
