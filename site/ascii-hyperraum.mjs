// SPDX-License-Identifier: GPL-3.0-or-later
// Hyperraum: a character-built flight corridor, not a second mascot renderer.
// All animation/lifecycle state belongs to the shared controller.
const TAU = Math.PI * 2;
const GOLD = '#fabd2f', PURPLE = '#bc8ed1', CREAM = '#d8d4ce', INK = '#504945';
const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const finite = (value, fallback = 0) => Number.isFinite(value) ? value : fallback;
const fraction = value => value - Math.floor(value);
const roundCorner = value => Math.sign(value) * Math.pow(Math.abs(value), .78);

/** Pure framing, including a conservative whole-head envelope in CSS pixels. */
export function hyperraumPose(frame = {}) {
  const width = clamp(finite(frame.width, 1), 1, 20000);
  const height = clamp(finite(frame.height, 1), 1, 20000);
  const mobile = typeof frame.stacked==='boolean' ? frame.stacked : width <= 600;
  // A composed still ignores every mutable input, not just the clock.
  const time = frame.still ? 6 : finite(frame.time);
  const flow = frame.still ? 0 : finite(frame.flow);
  const energy = frame.still ? 0 : clamp(finite(frame.energy));
  const pointerX = frame.still ? 0 : clamp(finite(frame.pointerX), -1, 1);
  const pointerY = frame.still ? 0 : clamp(finite(frame.pointerY), -1, 1);
  const x = width * (mobile ? .5 : .77) + Math.sin(time * .17) * width * .002
    + pointerX * width * .0015;
  const y = height * .47 + Math.sin(time * .21) * height * .005 + pointerY * height * .002;
  const base = Math.min(width * .35, height * .41);
  const padding = Math.min(6, width * .015, height * .015);
  // The factor 1.25 includes canonical ears/ruff, glyph size, shared idle yaw,
  // pointer translation and our deliberately small facial scatter envelope.
  const roomX = Math.min(x - (mobile ? 0 : width * .54), width - x) - padding;
  const roomY = Math.min(y, height - y) - padding;
  const scale = Math.min(mobile ? .90 : .84, roomX / (base * 1.25), roomY / (base * 1.25))
    * (1 - energy * .015);
  const radius = base * scale * 1.25 + padding;
  return {
    width, height, mobile, time, flow, energy, x, y, scale,
    scatter: energy * .075,
    bounds: { left: x - radius, right: x + radius, top: y - radius, bottom: y + radius },
    headSize: base * scale,
    vanishingX: x + Math.sin(time * .23) * base * .035 + pointerX * base * .018,
    vanishingY: y + Math.cos(time * .19) * base * .026 + pointerY * base * .014,
    phase: fraction(time * .022 + flow * .12),
    speed: 1 + energy * 5,
    portalScale: 1 + energy * .85,
  };
}

/**
 * Fixed work: <=1372 environment glyph attempts desktop, <=652 mobile.
 * No retained particles, randomness, canvas paths, green ink or browser APIs.
 */
export function drawHyperraum(_context, frame, helpers) {
  const pose = hyperraumPose(frame);
  const { width, height, mobile, time, energy, headSize, vanishingX: cx, vanishingY: cy } = pose;
  const radialX = width * (mobile ? .47 : .235);
  const radialY = height * .50;
  const rings = mobile ? 6 : 8, segments = mobile ? 44 : 88;
  const lanes = mobile ? 16 : 22, steps = mobile ? 8 : 10;
  const floorRows = mobile ? 4 : 5, floorColumns = mobile ? 22 : 28;

  function glyph(char, x, y, size, color, alpha) {
    size *= mobile ? 1.10 : 1.22;
    // Preserve the editorial LEFT 52% even at peak rush. The additional 2%
    // feather is art-side only; copy never depends on an opaque CSS overlay.
    const copyEdge = mobile ? 0 : width * .52;
    if (x - size * .5 < copyEdge || x + size * .5 > width
      || y - size * .6 < 0 || y + size * .6 > height) return;
    const feather = mobile ? 1 : clamp((x - size * .5 - width * .54) / (width * .09));
    const dx = (x - pose.x) / (headSize * .90);
    const dy = (y - pose.y) / (headSize * 1.06);
    // A quiet silhouette behind the canonical face preserves its single eye.
    if (dx * dx + dy * dy < 1) return;
    const opacity = alpha * feather * 2.2;
    if (opacity > .012) helpers.glyph(char, x, y, size, color, clamp(opacity));
  }

  // Nested rounded polygon gates grow toward the viewer. Their modular wrap
  // happens behind the face or outside the field, with a smooth depth fade.
  for (let ring = 0; ring < rings; ring++) {
    const depth = fraction(ring / rings + pose.phase);
    const radius = (.24 + depth * depth * 3.25) * (1 + energy * .36);
    const fade = Math.sin(depth * Math.PI) ** 2;
    const twist = .10 * depth + Math.sin(time * .09) * .025;
    for (let i = 0; i < segments; i++) {
      const angle = i / segments * TAU + twist;
      const dx = roundCorner(Math.cos(angle)) * radialX * radius;
      const dy = roundCorner(Math.sin(angle)) * radialY * radius;
      const char = i % 8 === 0 ? '+' : Math.abs(Math.sin(angle)) > .82 ? '='
        : Math.abs(Math.cos(angle)) > .88 ? '|' : Math.sin(angle * 2) > 0 ? '\\' : '/';
      glyph(char, cx + dx, cy + dy + dx * .045, mobile ? 7 : 7.5,
        ring % 3 === 0 ? PURPLE : GOLD, (.17 + depth * .32 + energy * .17) * fade);
    }
  }

  // Radial flight lines are sampled in perspective, never vertical rain.
  // One short, spatially separated ASCII echo becomes a long exposure at rush.
  for (let lane = 0; lane < lanes; lane++) {
    const angle = lane / lanes * TAU + Math.sin(time * .07) * .035;
    const cos = Math.cos(angle), sin = Math.sin(angle);
    const char = Math.abs(sin) < .35 ? '-' : Math.abs(cos) < .25 ? '|'
      : cos * sin > 0 ? '\\' : '/';
    for (let step = 0; step < steps; step++) {
      const depth = fraction(step / steps + lane * .037 + time * .035 + pose.flow * .19);
      const radius = (.18 + depth * depth * 3.8) * (1 + energy * .50);
      const dx = cos * radialX * radius, dy = sin * radialY * radius;
      const x = cx + dx, y = cy + dy + dx * .045;
      const size = (mobile ? 6 : 6.5) + depth * 3;
      const fade = Math.sin(depth * Math.PI) ** 2;
      const alpha = (.20 + depth * .38 + energy * .18) * fade;
      glyph(lane % 4 === 0 ? '+' : energy > .15 ? char : '.', x, y, size,
        lane % 5 === 0 ? PURPLE : lane % 3 === 0 ? CREAM : GOLD, alpha);
      if (energy > .01) {
        const trail = (pose.speed - 1) * .2 * (8 + depth * 24);
        glyph(char, x - cos * trail, y - sin * trail, size, GOLD, alpha * energy * .65);
      }
    }
  }

  // A low-perspective ASCII floor gives the corridor a horizon and forward
  // direction, unlike a flat stack of orbital ellipses.
  const horizon = cy + height * .08;
  for (let row = 0; row < floorRows; row++) {
    // Scale the unwrapped clock, not the fractional ring phase: the latter
    // would make the complete floor jump at each tunnel-cycle boundary.
    const depth = fraction(row / floorRows + time * .0143 + pose.flow * .078);
    const spread = .08 + depth * depth * 1.35;
    const y = horizon + height * (.035 + depth * depth * .57);
    for (let column = 0; column < floorColumns; column++) {
      const side = column / (floorColumns - 1) * 2 - 1;
      const x = cx + side * width * spread;
      const char = column % 4 === 0 ? '+' : row % 2 === 0 ? '_' : '=';
      glyph(char, x, y + Math.abs(side) * depth * height * .025, mobile ? 6 : 7,
        column % 4 === 0 ? PURPLE : INK, (.18 + depth * .37) * Math.sin(depth * Math.PI));
    }
  }

  // The rush opens a single bright gateway, then disappears as energy settles.
  // Face scale changes by only 1.5%; almost all drama lives in the environment.
  const gateRadius = 1.02 * pose.portalScale;
  for (let i = 0; i < segments; i++) {
    const angle = i / segments * TAU;
    const dx = roundCorner(Math.cos(angle)) * radialX * gateRadius;
    const dy = roundCorner(Math.sin(angle)) * radialY * gateRadius;
    glyph(i % 4 === 0 ? '+' : ':', cx + dx, cy + dy + dx * .045,
      mobile ? 7 : 8, i % 8 === 0 ? CREAM : GOLD, .12 + energy * .63);
  }

  helpers.cat({ x: pose.x, y: pose.y, scale: pose.scale, scatter: pose.scatter });
}
