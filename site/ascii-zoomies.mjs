// SPDX-License-Identifier: GPL-3.0-or-later
// Front-facing Astro at full tilt: the canonical head is owned by helpers.cat.
const TAU = Math.PI * 2;
const colors = {
  fur: '#bdae93', cream: '#d8d4ce', gold: '#fabd2f',
  purple: '#bc8ed1', ink: '#504945',
};
const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const finite = (value, fallback = 0) => Number.isFinite(value) ? value : fallback;

/** Pure pose; dimensions are CSS pixels, time/flow are supplied simulation clocks. */
export function zoomiesPose(frame = {}) {
  const width = finite(frame.width) > 0 ? frame.width : 320;
  const height = finite(frame.height) > 0 ? frame.height : 290;
  const still = Boolean(frame.still);
  // All clock multipliers are hundredths: wrapping here is continuous and also
  // keeps trigonometry finite for extremely old simulation clocks.
  const time = still ? 0 : Math.max(0, finite(frame.time)) % (TAU * 100);
  const flow = still ? 0 : finite(frame.flow) % (TAU * 100);
  const burst = still ? 0 : Math.max(clamp(finite(frame.energy)), 1 - clamp(finite(frame.intro, 1)));
  const pointer = still ? 0 : clamp(finite(frame.pointerX), -1, 1);
  const unit = Math.min(width * 0.19, height * 0.205, 104);
  const baseScale = Math.min(width * 0.35, height * 0.41);
  const margin = Math.min(12, width * 0.035, height * 0.035);
  const travel = Math.max(0, Math.min(width * 0.24, width * 0.5 - unit * 1.92 - margin));
  const phase = time * 0.9 + flow * 0.22;
  const gait = time * 10 + flow * 0.6;
  const floor = height * 0.88;
  const leap = still ? 0 : unit * (Math.max(0, Math.sin(time * 2.4 + flow * 0.4)) ** 2 * 0.12 + burst * 0.5);
  const x = width * 0.5 + travel * (Math.sin(phase) * 0.88 + Math.cos(phase) * burst * 0.1) + pointer * Math.min(3, travel * 0.02);
  return {
    width, height, time, unit, floor, x,
    y: floor - unit * 1.92 - leap,
    scale: unit / baseScale,
    leap, burst, phase: gait,
    direction: still || Math.cos(phase) >= 0 ? 1 : -1,
    stride: still ? 0 : Math.sin(gait),
    tail: still ? 0.15 : Math.sin(time * 3.2 + flow * 0.6) * (0.6 + burst * 0.4),
    trail: still ? 0 : 0.3 + burst * 0.7,
    scatter: burst * 0.08,
    glyphSize: clamp(unit * 0.115, 7, 11),
  };
}

/** Draw only ASCII glyphs, then exactly one complete, unmirrored Astro head. */
export function drawZoomies(context, frame, helpers) {
  const pose = zoomiesPose(frame);
  const { width, height, x, y, unit, floor, glyphSize: font, direction, burst } = pose;
  // The shared glyph/head painters change font, color and alpha. Do not leak any
  // of those changes, including when an embedding renderer throws.
  context.save();
  try {
    const glyph = (char, px, py, size, color, alpha = 1) => {
      if (px < size || px > width - size || py < size || py > height - size) return;
      helpers.glyph(char, px, py, size, color, alpha);
    };
    const local = (char, px, py, color, alpha = 1, size = font) =>
      glyph(char, x + px * unit, y + py * unit, size, color, alpha);

    // A runway rather than a starfield. The moving seam and paired paw marks
    // give the bounded side-to-side travel a clear ground reference.
    const floorStep = Math.max(12, width / 76);
    // Dots repeat every three tiles. Use their full period and the unwrapped
    // simulation clock, independently of the actor's trigonometric clock wrap.
    const floorPeriod = floorStep * 3 / 34;
    const floorShift = frame.still ? 0 : (Math.max(0, finite(frame.time)) % floorPeriod) * 34;
    for (let i = 0; i < Math.ceil(width / floorStep) + 3; i++) {
      const px = i * floorStep - floorShift;
      glyph('_', px, floor + font * 1.6, font, colors.ink, 0.75);
      if (i % 3 === 0) glyph('.', px + floorStep * 0.4, floor + font * 2.5, 6, colors.gold, 0.35);
    }
    for (let i = 0; i < 7; i++) {
      const px = x - direction * (unit * (0.82 + i * 0.42));
      const alpha = 0.38 * (1 - i / 8);
      glyph(':', px, floor + font * (i % 2 ? 0.2 : 0.65), font, colors.fur, alpha);
      glyph('.', px + direction * font * 0.7, floor + font * (i % 2 ? 0.65 : 0.2), 6, colors.gold, alpha);
    }
    // A compact landing shadow remains on the floor when the entire cat leaps.
    for (let i = -7; i <= 7; i++) {
      glyph(i % 3 ? '.' : ':', x + i * font * 0.75, floor + font * 0.3,
        font, colors.ink, 0.65 - Math.abs(i) * 0.055);
    }

    if (pose.trail > 0) {
      const count = Math.round(9 + pose.trail * 18);
      for (let row = 0; row < 4; row++) {
        for (let i = 0; i < count; i++) {
          const distance = 1.15 + i * 0.09;
          const wave = Math.sin(i * 0.65 + pose.time * 2) * 0.025;
          const px = x - direction * unit * distance;
          const py = y + unit * ((row - 1) * 0.32 + wave);
          glyph(i % 6 === 0 ? (direction > 0 ? '>' : '<') : (i % 3 ? '-' : '='),
            px, py, font, row % 2 ? colors.gold : colors.purple,
            (0.13 + burst * 0.48) * (1 - i / count));
        }
      }
    }
    if (burst > 0.02) {
      for (let i = 0; i < 40; i++) {
        const angle = i * 2.39996 + pose.time * 0.4;
        const radius = 1.4 + (i % 5) * 0.12 + burst * 0.25;
        local(i % 4 ? '+' : '*', Math.cos(angle) * radius,
          Math.sin(angle) * radius * 0.83, i % 3 ? colors.gold : colors.purple,
          burst * (0.35 + (i % 4) * 0.12), 6 + (i % 3));
      }
    }

    // A thick, curling tail stays on the viewer's left; direction never mirrors
    // the cat. Its tip wags independently of the diagonally paired footfalls.
    for (let i = 0; i <= 25; i++) {
      const t = i / 25;
      const tx = -0.45 - 1.24 * Math.sin(t * Math.PI * 0.7) + pose.tail * 0.12 * t;
      const ty = 1 + Math.sin(t * Math.PI * 1.4) * 0.35 - t * 0.92 +
        Math.sin(t * Math.PI) * pose.tail * 0.16;
      local(i % 5 < 2 ? '=' : '#', tx, ty, i % 5 < 2 ? colors.ink : colors.fur, 0.95);
      local(':', tx, ty - 0.075, colors.fur, 0.8);
      if (i < 21) local('.', tx, ty + 0.07, colors.cream, 0.68);
    }

    // Four articulated legs: hind pair first, then the chest, then front pair.
    // ASCII samples follow two straight bone segments, never canvas line art.
    const leg = (side, hind) => {
      const gait = pose.phase + (side > 0 ? Math.PI : 0) + (hind ? Math.PI : 0);
      const swing = frame.still ? 0 : Math.sin(gait);
      const lift = frame.still ? 0 : Math.max(0, Math.cos(gait)) * 0.2;
      const tuck = burst * 0.17;
      const rootX = side * (hind ? 0.49 : 0.32);
      const rootY = hind ? 1.12 : 1.02;
      const kneeX = side * 0.56 + swing * 0.15;
      const kneeY = 1.48 - tuck;
      const footX = side * (hind ? 0.83 : 0.45) + swing * 0.23;
      const footY = 1.91 - lift - tuck;
      const color = hind ? colors.fur : colors.cream;
      for (let i = 0; i <= 10; i++) {
        const t = i / 10;
        const first = t < 0.5;
        const a = first ? rootX : kneeX, b = first ? kneeX : footX;
        const c = first ? rootY : kneeY, d = first ? kneeY : footY;
        const mix = first ? t * 2 : (t - 0.5) * 2;
        const px = a + (b - a) * mix, py = c + (d - c) * mix;
        local(b > a ? '\\' : '/', px - 0.045, py, color, hind ? 0.65 : 0.95);
        local(i % 4 === 0 ? '=' : ':', px + 0.045, py, i % 4 === 0 ? colors.ink : color, 0.9);
      }
      const paw = '(==)';
      for (let i = 0; i < paw.length; i++) {
        local(paw[i], footX + (i - 1.5) * font * 0.57 / unit, footY,
          i === 0 || i === 3 ? colors.fur : color, hind ? 0.75 : 1);
      }
    };
    leg(-1, true); leg(1, true);
    const rowStep = font * 0.83 / unit, colStep = font * 0.66 / unit;
    for (let py = 0.72, row = 0; py < 1.59; py += rowStep, row++) {
      for (let px = -0.68; px <= 0.68; px += colStep) {
        const radius = (px / 0.65) ** 2 + ((py - 1.13) / 0.46) ** 2;
        if (radius > 1) continue;
        const ruff = Math.abs(px) < 0.31 && py < 1.31;
        const stripe = !ruff && row % 4 === 1;
        local(stripe ? '=' : radius > 0.78 ? '#' : ruff ? ':' : '%', px, py,
          stripe ? colors.ink : ruff ? colors.cream : colors.fur);
      }
    }
    leg(-1, false); leg(1, false);

    // One complete head, positive scale, fixed orientation. Keep scatter small
    // enough that the ears, missing-eye stroke and single open eye stay legible.
    helpers.cat({ x, y, scale: pose.scale, scatter: pose.scatter });
  } finally {
    context.restore();
  }
}
