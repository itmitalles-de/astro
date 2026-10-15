#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the self-contained wordmark and raster icons with system PyGObject."""
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SVG = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG)


def build_logo():
    source = ET.parse(ROOT / 'assets/astro.svg').getroot()
    logo = ET.Element(f'{{{SVG}}}svg', width='1040', height='280', viewBox='0 0 1040 280', role='img')
    ET.SubElement(logo, f'{{{SVG}}}title').text = 'Astro — quiet company, sharp tools'
    icon = ET.SubElement(logo, f'{{{SVG}}}g', transform='translate(12 12) scale(.5)')
    for child in source:
        if child.tag.rsplit('}', 1)[-1] not in ('title', 'desc'):
            icon.append(child)
    word = ET.SubElement(logo, f'{{{SVG}}}g', {'transform': 'translate(326 76)', 'fill': 'none', 'stroke': '#d0cfcc', 'stroke-width': '11', 'stroke-linecap': 'square', 'stroke-linejoin': 'round'})
    letters = [
        'M0 100 30 0 60 100M12 64H48',
        'M60 4H16Q0 4 0 20V31Q0 46 16 49L44 54Q60 57 60 72V83Q60 100 44 100H0',
        'M0 0H60M30 0V100',
        'M0 100V0H38Q60 0 60 22V28Q60 50 38 50H0M34 50 66 100',
        'M16 0H44Q60 0 60 16V84Q60 100 44 100H16Q0 100 0 84V16Q0 0 16 0',
    ]
    for i, letter in enumerate(letters):
        ET.SubElement(word, f'{{{SVG}}}path', d=letter, transform=f'translate({i*134} 0)')
    ET.SubElement(logo, f'{{{SVG}}}path', {'d': 'M326 217h70', 'stroke': '#2a7bde', 'stroke-width': '5'})
    text = ET.SubElement(logo, f'{{{SVG}}}text', {'x': '421', 'y': '223', 'fill': '#5e5c64', 'font-family': 'monospace', 'font-size': '17', 'letter-spacing': '2'})
    text.text = 'QUIET COMPANY. SHARP TOOLS.'
    ET.indent(logo, space='  ')
    ET.ElementTree(logo).write(ROOT / 'assets/astro-logo.svg', encoding='unicode', xml_declaration=False)


def build_icons():
    import gi
    import cairo
    gi.require_version('Rsvg', '2.0')
    from gi.repository import Rsvg
    source = Rsvg.Handle.new_from_file(str(ROOT / 'assets/astro.svg'))
    for size in (32, 64, 128, 256, 512):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        rectangle = Rsvg.Rectangle()
        rectangle.x = rectangle.y = 0
        rectangle.width = rectangle.height = size
        source.render_document(cairo.Context(surface), rectangle)
        surface.write_to_png(str(ROOT / f'assets/astro-{size}.png'))


if __name__ == '__main__':
    build_logo()
    build_icons()
