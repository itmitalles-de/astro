// SPDX-License-Identifier: GPL-3.0-or-later
import test from 'node:test';
import assert from 'node:assert/strict';
import { drawZoomies, zoomiesPose } from '../../site/ascii-zoomies.mjs';

const frame = (changes = {}) => ({
  width: 550, height: 380, time: 0, energy: 0,
  pointerX: 0, pointerY: 0, intro: 1, still: false, flow: 0, ...changes,
});
const palette = new Set(['#bdae93', '#d8d4ce', '#fabd2f', '#bc8ed1', '#504945']);

function recording(input, failCat = false) {
  const marks = [], heads = [], calls = [];
  const context = {
    globalAlpha: 0.43, fillStyle: '#123456', font: '17px monospace', stack: [],
    save() { this.stack.push([this.globalAlpha, this.fillStyle, this.font]); },
    restore() { [this.globalAlpha, this.fillStyle, this.font] = this.stack.pop(); },
  };
  const helpers = {
    glyph(char, x, y, size, color, alpha = 1) {
      calls.push('glyph');
      marks.push({ char, x, y, size, color, alpha });
      context.globalAlpha = alpha;
      context.fillStyle = color;
      context.font = `${size}px monospace`;
    },
    cat(head) {
      calls.push('cat');
      heads.push(head);
      context.globalAlpha = 0.17;
      if (failCat) throw new Error('cat failed');
    },
  };
  return { marks, heads, calls, context, draw: () => drawZoomies(context, input, helpers) };
}

test('whole head and body remain bounded with positive finite scale across scene sizes', () => {
  const sizes = [[320, 290], [390, 320], [550, 380], [1160, 500], [1160, 290], [320, 500]];
  for (const [width, height] of sizes) {
    for (const time of [0, 0.1, 0.7, 1.3, 3, 6, 17, 125, 1e12]) {
      for (const energy of [0, 0.5, 1]) {
        for (const intro of [0, 1]) {
          const pose = zoomiesPose(frame({ width, height, time, energy, intro, pointerX: 99, pointerY: -99 }));
          for (const value of Object.values(pose)) assert.ok(Number.isFinite(value), JSON.stringify(pose));
          assert.ok(pose.scale > 0);
          assert.ok(Math.abs(pose.scale * Math.min(width * 0.35, height * 0.41) - pose.unit) < 1e-9);
          // A conservative whole-head box includes the canonical ears/ruff, depth and tiny scatter.
          assert.ok(pose.x - pose.unit * 1.3 >= 0);
          assert.ok(pose.x + pose.unit * 1.3 <= width);
          assert.ok(pose.y - pose.unit * 1.3 >= 0);
          assert.ok(pose.y + pose.unit * 1.3 <= height);
          // Tail, torso, legs and paws occupy a wider/lower envelope than the head.
          assert.ok(pose.x - pose.unit * 1.92 >= 0);
          assert.ok(pose.x + pose.unit * 1.92 <= width);
          assert.ok(pose.y + pose.unit * 2.05 <= height);
        }
      }
    }
  }
});

test('idle cat traverses the floor, reverses without a flipped head, and takes small jumps', () => {
  const poses = Array.from({ length: 161 }, (_, i) => zoomiesPose(frame({ time: i * 0.05 })));
  const xs = poses.map(pose => pose.x);
  const leaps = poses.map(pose => pose.leap);
  assert.ok(Math.max(...xs) - Math.min(...xs) > 90, 'substantial travel rather than portrait bobbing');
  assert.ok(Math.max(...leaps) - Math.min(...leaps) > 5, 'visible idle hop');
  assert.deepEqual(new Set(poses.map(pose => pose.direction)), new Set([1, -1]));
  assert.ok(poses.every(pose => pose.scale > 0));
  assert.ok(new Set(poses.map(pose => pose.stride.toFixed(2))).size > 20);
});

test('intro and user energy add a dramatic leap and trail burst, then settle', () => {
  const resting = zoomiesPose(frame({ time: 2 }));
  const burst = zoomiesPose(frame({ time: 2, energy: 1 }));
  const intro = zoomiesPose(frame({ time: 2, intro: 0 }));
  assert.ok(burst.y < resting.y - resting.unit * 0.4);
  assert.ok(intro.y < resting.y - resting.unit * 0.4);
  assert.ok(burst.trail > resting.trail * 2);
  assert.ok(burst.scatter <= 0.08, 'keep the single canonical face recognizable');
  assert.deepEqual(zoomiesPose(frame({ time: 2, energy: 0 })), resting, 'no retained burst state');
});

test('reduced motion is a deterministic deliberate still, independent of input clocks and energy', () => {
  const baseline = zoomiesPose(frame({ still: true }));
  const varied = frame({ still: true, time: 333, flow: 123, energy: 1, intro: 0, pointerX: -1, pointerY: 1 });
  assert.deepEqual(zoomiesPose(varied), baseline);
  assert.equal(baseline.leap, 0);
  assert.equal(baseline.scatter, 0);
  const first = recording(frame({ still: true })); first.draw();
  const second = recording(varied); second.draw();
  assert.deepEqual(first.marks, second.marks);
  assert.deepEqual(first.heads, second.heads);
});

const runway = (input, char) => {
  const sample = recording(input); sample.draw();
  const pose = zoomiesPose(input);
  const y = pose.floor + pose.glyphSize * (char === '_' ? 1.6 : 2.5);
  return sample.marks.filter(mark => mark.char === char && Math.abs(mark.y - y) < 1e-9);
};

test('runway dots stay continuous at individual steps, full pattern wraps and the actor clock wrap', () => {
  const epsilon = .00001;
  for (const width of [320, 390, 550, 1160]) {
    const step = Math.max(12, width / 76);
    for (const boundary of [step / 34, 2 * step / 34, 3 * step / 34, Math.PI * 2 * 100]) {
      const before = runway(frame({ width, time: boundary - epsilon }), '.');
      const after = runway(frame({ width, time: boundary + epsilon }), '.');
      for (const mark of before.filter(mark => mark.x > step * 3 && mark.x < width - step * 3)) {
        const distance = Math.min(...after.map(next => Math.abs(mark.x - next.x)));
        assert(Math.abs(distance - epsilon * 2 * 34) < 1e-7, `${width}px at ${boundary}s: jump ${distance}`);
      }
    }
  }
});

test('every visible runway tile is covered through the entire three-step pattern period', () => {
  for (const width of [320, 390, 550, 1160]) {
    const step = Math.max(12, width / 76);
    for (const phase of [0, .2, .9, 1.5, 2.9]) {
      const input = frame({ width, time: phase * step / 34 });
      const font = zoomiesPose(input).glyphSize;
      for (const char of ['_', '.']) {
        const actual = runway(input, char);
        const expected = [];
        for (let i = 0; i < Math.ceil(width / step) + 4; i++) {
          if (char === '.' && i % 3 !== 0) continue;
          const x = i * step - phase * step + (char === '.' ? step * .4 : 0);
          const margin = char === '.' ? 6 : font;
          if (x >= margin && x <= width - margin) expected.push(x);
        }
        assert.equal(actual.length, expected.length, `${width}px, phase ${phase}, ${char}: coverage`);
        actual.forEach((mark, i) => assert(Math.abs(mark.x - expected[i]) < 1e-9));
      }
    }
  }
});

test('artist emits bounded printable ASCII in the permitted palette, with one whole head last', () => {
  for (const [width, height] of [[320, 290], [550, 380], [1160, 500]]) {
    for (const time of [0, 0.4, 2, 4.7]) {
      const input = frame({ width, height, time, energy: 1, intro: 0 });
      const { marks, heads, calls, context, draw } = recording(input);
      draw();
      assert.equal(heads.length, 1);
      assert.equal(calls.at(-1), 'cat', 'body and effects never paint over the face');
      assert.deepEqual(heads[0], {
        x: zoomiesPose(input).x, y: zoomiesPose(input).y,
        scale: zoomiesPose(input).scale, scatter: zoomiesPose(input).scatter,
      });
      assert.ok(marks.length > 150, 'actual whole-cat/floor/trail artist');
      assert.ok(marks.length < 950, `bounded glyph budget: ${marks.length}`);
      for (const mark of marks) {
        assert.match(mark.char, /^[\x21-\x7e]$/);
        assert.ok(palette.has(mark.color), mark.color);
        assert.ok([mark.x, mark.y, mark.size, mark.alpha].every(Number.isFinite));
        assert.ok(mark.size >= 5 && mark.size <= 13);
        assert.ok(mark.alpha >= 0 && mark.alpha <= 1);
        assert.ok(mark.x - mark.size * 0.5 >= 0 && mark.x + mark.size * 0.5 <= width);
        assert.ok(mark.y - mark.size * 0.5 >= 0 && mark.y + mark.size * 0.5 <= height);
      }
      assert.equal(context.globalAlpha, 0.43);
      assert.equal(context.fillStyle, '#123456');
      assert.equal(context.font, '17px monospace');
      assert.equal(context.stack.length, 0);
    }
  }
});

test('legs and tail animate, floor/paw marks exist, and bursts increase the ASCII trail', () => {
  const idle = recording(frame({ time: 1 })); idle.draw();
  const moved = recording(frame({ time: 1.3 })); moved.draw();
  const burst = recording(frame({ time: 1, energy: 1 })); burst.draw();
  assert.notDeepEqual(idle.marks, moved.marks);
  assert.ok(idle.marks.some(mark => mark.char === '_'));
  assert.ok(idle.marks.some(mark => mark.char === '('));
  assert.ok(idle.marks.some(mark => mark.char === '#'));
  assert.ok(burst.marks.filter(mark => mark.color === '#fabd2f').length >
    idle.marks.filter(mark => mark.color === '#fabd2f').length + 20);
  const localPoints = (sample, input, char) => {
    const pose = zoomiesPose(input);
    return sample.marks.filter(mark => mark.char === char).map(mark => [
      (mark.x - pose.x) / pose.unit, (mark.y - pose.y) / pose.unit,
    ]);
  };
  assert.notDeepEqual(localPoints(idle, frame({ time: 1 }), '('),
    localPoints(moved, frame({ time: 1.3 }), '('), 'feet articulate, not just translate');
  assert.notDeepEqual(localPoints(idle, frame({ time: 1 }), '#'),
    localPoints(moved, frame({ time: 1.3 }), '#'), 'tail geometry changes');
});

test('renderer is repeatable, does not mutate frame, and restores context when a helper fails', () => {
  const input = Object.freeze(frame({ time: 7, energy: 0.7, flow: 5 }));
  const first = recording(input); first.draw();
  const second = recording(input); second.draw();
  assert.deepEqual(first.marks, second.marks);
  assert.deepEqual(first.heads, second.heads);
  const broken = recording(input, true);
  assert.throws(broken.draw, /cat failed/);
  assert.equal(broken.context.globalAlpha, 0.43);
  assert.equal(broken.context.stack.length, 0);
});

test('missing and non-finite optional inputs use safe deterministic defaults', () => {
  const normal = zoomiesPose(frame());
  const omitted = zoomiesPose({ width: 550, height: 380 });
  assert.deepEqual(omitted, normal);
  const invalid = zoomiesPose(frame({
    width: 0, height: NaN, time: Infinity, flow: NaN,
    energy: Infinity, pointerX: NaN, pointerY: Infinity, intro: NaN,
  }));
  for (const value of Object.values(invalid)) assert.ok(Number.isFinite(value));
  assert.ok(invalid.scale > 0);
  assert.deepEqual(zoomiesPose(frame({ energy: -100, intro: 100 })), normal);
  for (const input of [
    frame({ time: Number.MAX_VALUE, flow: Number.MAX_VALUE, energy: 100 }),
    frame({ width: 1, height: 1, time: -100, flow: -100, pointerX: -100 }),
  ]) {
    const pose = zoomiesPose(input);
    for (const value of Object.values(pose)) assert.ok(Number.isFinite(value));
    assert.ok(pose.scale > 0);
  }
});
