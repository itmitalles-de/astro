# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the uniform outline font used by Astro's pane title controls.

Run with Python and fontTools to regenerate the font after editing paths:
`python3 build_pane_icons.py [OUTPUT.ttf]` (default: the user font directory).
The installed font is a runtime asset; Kitty does not run this generator.
"""

import sys
from math import cos, hypot, pi, sin
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen


FAMILY = "Astro Pane Controls"
OUTPUT = Path.home() / ".local/share/fonts/astro-pane-controls/AstroPaneControls.ttf"
# 2026-10-15 00:00 UTC in seconds since 1904-01-01, the OpenType epoch.
FONT_TIMESTAMP = 3874867200
SCALE = 43.75
STROKE_RADIUS = 1.4 * SCALE / 2

# Every icon shares a 24-unit canvas and a 4..20 bounding box on both axes.
PATHS = {
    "right": [[(4, 12), (20, 12)], [(12, 4), (20, 12), (12, 20)]],
    "below": [[(12, 4), (12, 20)], [(4, 12), (12, 20), (20, 12)]],
    "copy": [
        [(8, 15), (4, 15), (4, 4), (15, 4), (15, 8)],
        [(8, 8), (20, 8), (20, 20), (8, 20), (8, 8)],
    ],
    "expand": [
        [(4, 9), (4, 4), (9, 4)], [(15, 4), (20, 4), (20, 9)],
        [(20, 15), (20, 20), (15, 20)], [(9, 20), (4, 20), (4, 15)],
    ],
    "close": [[(4, 4), (20, 20)], [(4, 20), (20, 4)]],
    "restore": [
        [(4, 9), (9, 9), (9, 4)], [(15, 4), (15, 9), (20, 9)],
        [(20, 15), (15, 15), (15, 20)], [(9, 20), (9, 15), (4, 15)],
    ],
    "plus": [[(4, 12), (20, 12)], [(12, 4), (12, 20)]],
    "command": [
        [(4, 4), (20, 4), (20, 20), (4, 20), (4, 4)],
        [(8, 8), (12, 12), (8, 16)], [(14, 16), (17, 16)],
    ],
    "keyboard": [
        [(4, 6), (20, 6), (20, 18), (4, 18), (4, 6)],
        [(7, 9), (8, 9)], [(11, 9), (12, 9)], [(15, 9), (17, 9)],
        [(7, 12), (8, 12)], [(11, 12), (12, 12)], [(15, 12), (17, 12)],
        [(8, 15), (16, 15)],
    ],
    # Four-point spark for the Codex pane.
    "spark": [[(12, 4), (14, 10), (20, 12), (14, 14), (12, 20), (10, 14), (4, 12), (10, 10), (12, 4)]],
    # Pane groups: a 2x2 set of panes, then equal widths and equal heights.
    "group": [
        [(4, 4), (10, 4), (10, 10), (4, 10), (4, 4)], [(14, 4), (20, 4), (20, 10), (14, 10), (14, 4)],
        [(4, 14), (10, 14), (10, 20), (4, 20), (4, 14)], [(14, 14), (20, 14), (20, 20), (14, 20), (14, 14)],
    ],
    "equal_width": [
        [(4, 4), (4, 20)], [(20, 4), (20, 20)], [(7.5, 12), (16.5, 12)],
        [(10.5, 9), (7.5, 12), (10.5, 15)], [(13.5, 9), (16.5, 12), (13.5, 15)],
    ],
    "equal_height": [
        [(4, 4), (20, 4)], [(4, 20), (20, 20)], [(12, 7.5), (12, 16.5)],
        [(9, 10.5), (12, 7.5), (15, 10.5)], [(9, 13.5), (12, 16.5), (15, 13.5)],
    ],
    # Unfold the folded controls to the left; fold them back to the right.
    "unfold": [[(15, 4), (7, 12), (15, 20)]],
    "fold": [[(9, 4), (17, 12), (9, 20)]],
}


def point(x, y):
    # Match Ubuntu Sans Mono's vertical metrics; center icons in its line box.
    return (500 + (x - 12) * SCALE, 340 + (12 - y) * SCALE)


def circle(pen, center):
    cx, cy = center
    radius = STROKE_RADIUS
    pen.moveTo((cx + radius, cy))
    for i in range(8):
        middle = -(i + 0.5) * pi / 4
        end = -(i + 1) * pi / 4
        control_radius = radius / cos(pi / 8)
        pen.qCurveTo(
            (cx + control_radius * cos(middle), cy + control_radius * sin(middle)),
            (cx + radius * cos(end), cy + radius * sin(end)),
        )
    pen.closePath()


def glyph(paths):
    pen = TTGlyphPen(None)
    for path in paths:
        vertices = [point(*p) for p in path]
        for (ax, ay), (bx, by) in zip(vertices, vertices[1:]):
            length = hypot(bx - ax, by - ay)
            nx, ny = -(by - ay) * STROKE_RADIUS / length, (bx - ax) * STROKE_RADIUS / length
            pen.moveTo((ax + nx, ay + ny))
            pen.lineTo((bx + nx, by + ny))
            pen.lineTo((bx - nx, by - ny))
            pen.lineTo((ax - nx, ay - ny))
            pen.closePath()
        for vertex in set(vertices):
            circle(pen, vertex)
    result = pen.glyph()
    if result.numberOfContours:
        result.flags[0] |= 0x40  # OVERLAP_SIMPLE: rounded strokes share contours.
    return result


def main():
    builder = FontBuilder(1000, isTTF=True)
    names = [".notdef", *PATHS]
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap({0xE900 + i: name for i, name in enumerate(PATHS)})
    builder.setupGlyf({".notdef": TTGlyphPen(None).glyph(), **{name: glyph(paths) for name, paths in PATHS.items()}})
    glyf = builder.font["glyf"]
    for name in names:
        glyf[name].recalcBounds(glyf)
    builder.setupHorizontalMetrics({name: (1000, glyf[name].xMin if glyf[name].numberOfContours else 0) for name in names})
    builder.setupHorizontalHeader(ascent=940, descent=-260)
    builder.setupNameTable({
        "familyName": FAMILY, "styleName": "Regular", "uniqueFontIdentifier": FAMILY + " Regular 1.0",
        "fullName": FAMILY + " Regular", "psName": "AstroPaneControls-Regular", "version": "Version 1.0",
    })
    builder.setupOS2(sTypoAscender=940, sTypoDescender=-260, usWinAscent=940, usWinDescent=260, usWeightClass=400)
    builder.setupPost()
    # Fixed timestamps keep the generated font byte-for-byte reproducible.
    builder.font["head"].created = builder.font["head"].modified = FONT_TIMESTAMP
    builder.font.recalcTimestamp = False
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    builder.save(output)
    print(output)


if __name__ == "__main__":
    main()
