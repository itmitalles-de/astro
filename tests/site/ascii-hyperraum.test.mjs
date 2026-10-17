// SPDX-License-Identifier: GPL-3.0-or-later
import test from 'node:test';
import assert from 'node:assert/strict';
import { drawHyperraum, hyperraumPose } from '../../site/ascii-hyperraum.mjs';
import { createCatPoints, projectCatPoint } from '../../site/ascii-model.mjs';

const frame = (changes = {}) => ({
  width: 1160, height: 610, time: 4, energy: 0, pointerX: 0, pointerY: 0,
  intro: 1, still: false, flow: 0, ...changes,
});
const palette = new Set(['#bdae93', '#d8d4ce', '#fabd2f', '#bc8ed1', '#504945']);
function capture(input) {
  const glyphs = [], cats = [], order = [];
  // The artist must use the shared ASCII helpers, never canvas geometry/state.
  const context = new Proxy({}, { get() { throw new Error('Unexpected canvas access'); } });
  drawHyperraum(context, input, {
    glyph: (char, x, y, size, color, alpha = 1) => {
      glyphs.push({ char, x, y, size, color, alpha }); order.push('glyph');
    },
    cat: pose => { cats.push(pose); order.push('cat'); },
  });
  return { glyphs, cats, order };
}

test('the desktop corridor retains legible bright ASCII structure rather than vanishing behind the portrait',()=>{
  for(const time of [4,8,13]){
    const visible=capture(frame({time})).glyphs.filter(g=>g.alpha>=.4&&g.size>=8);
    assert(visible.length>=32,`Too little legible corridor structure at ${time}s: ${visible.length} glyphs`);
  }
});

test('Hyperraum anchors a whole positive-scale head at desktop right and mobile center', () => {
  for (const width of [320, 390, 600, 1160]) {
    const height = width <= 600 ? 290 : 610;
    const pose = hyperraumPose(frame({ width, height }));
    assert.equal(pose.mobile, width <= 600);
    assert(pose.scale > 0);
    assert(Math.abs(pose.x / width - (pose.mobile ? .5 : .77)) < .025);
    assert(Math.abs(pose.y / height - .47) < .025);
    assert(pose.bounds.left >= 0 && pose.bounds.right <= width);
    assert(pose.bounds.top >= 0 && pose.bounds.bottom <= height);
    if (!pose.mobile) assert(pose.bounds.left >= width * .52);
  }
});

test('stacked tablet heroes center the artwork even when their canvas is wider than 600px',()=>{
  const pose=hyperraumPose(frame({width:680,height:320,stacked:true}));
  assert.equal(pose.mobile,true);
  assert(Math.abs(pose.x/680-.5)<.025);
});

test('the canonical head stays inside the conservative pose bounds during drift and rush', () => {
  const points = createCatPoints(38);
  for (const [width, height] of [[320, 290], [390, 290], [1160, 610]]) {
    for (const time of [0, 3, 19, 45]) for (const energy of [0, 1]) {
      for (const pointerX of [-1, 1]) {
        const input = frame({ width, height, time, energy, pointerX, pointerY: -1 });
        const pose = hyperraumPose(input);
        for (const point of points) {
          const projected = projectCatPoint(point, { ...input, scatter: pose.scatter });
          const x = pose.x + (projected.x - width * .5) * pose.scale;
          const y = pose.y + (projected.y - height * .5) * pose.scale;
          assert(x >= pose.bounds.left && x <= pose.bounds.right, `head x ${x}`);
          assert(y >= pose.bounds.top && y <= pose.bounds.bottom, `head y ${y}`);
        }
      }
    }
  }
});

test('still scenes ignore clock, pointer, energy, intro and flow completely', () => {
  const a = frame({ still: true });
  const b = frame({ still: true, time: 818, energy: 1, pointerX: -1, pointerY: 1, intro: 0, flow: 90 });
  assert.deepEqual(hyperraumPose(a), hyperraumPose(b));
  assert.deepEqual(capture(a), capture(b));
  assert(capture(a).glyphs.length > 90, 'still mode needs a complete tunnel composition');
});

test('gentle camera drift and flow move the tunnel, energy expands it without breaking the face', () => {
  const idle = hyperraumPose(frame());
  const later = hyperraumPose(frame({ time: 12 }));
  const rush = hyperraumPose(frame({ energy: 1 }));
  assert.notEqual(idle.vanishingX, later.vanishingX);
  assert.notEqual(idle.vanishingY, later.vanishingY);
  assert(rush.speed > idle.speed * 3);
  assert(rush.portalScale > idle.portalScale * 1.5);
  assert(rush.scatter > idle.scatter && rush.scatter <= .09);
  assert(Math.abs(rush.scale / idle.scale - 1) < .05);
  assert.deepEqual(hyperraumPose(frame({ energy: 0 })), idle, 'energy settles without retained state');
  assert.notDeepEqual(capture(frame()), capture(frame({ flow: 2 })));
  assert.notDeepEqual(capture(frame()), capture(frame({ time: 12 })));
});

test('the artist calls the canonical unmirrored cat once, after its ASCII environment', () => {
  for (const energy of [0, .5, 1]) {
    const input = frame({ energy });
    const result = capture(input);
    const pose = hyperraumPose(input);
    assert.deepEqual(result.cats, [{ x: pose.x, y: pose.y, scale: pose.scale, scatter: pose.scatter }]);
    assert.equal(result.order.at(-1), 'cat');
    assert(result.glyphs.length > 90);
    assert(result.glyphs.some(g => g.color === '#fabd2f'));
    assert(result.glyphs.some(g => g.color === '#bc8ed1'));
    assert(result.glyphs.some(g => '/\\-_=|'.includes(g.char)), 'perspective streaks, not vertical rain');
  }
});

test('desktop text column is strictly glyph-free, including the whole-head safety box', () => {
  for (const time of [0, 5, 18]) for (const energy of [0, 1]) {
    const input = frame({ time, energy, pointerX: -1, pointerY: 1, flow: 3 });
    const { glyphs } = capture(input);
    assert(glyphs.every(g => g.x - g.size * .5 >= input.width * .52));
    assert(hyperraumPose(input).bounds.left >= input.width * .52);
    assert(glyphs.some(g => g.x > input.width * .9), 'depth must reach the canvas edge');
  }
});

test('all glyphs are finite visible printable ASCII in the non-green palette', () => {
  for (const [width, height] of [[320, 290], [390, 290], [1160, 610]]) {
    for (const energy of [0, .2, 1]) {
      const input = frame({ width, height, energy, flow: 9, time: 17 });
      const { glyphs } = capture(input);
      for (const g of glyphs) {
        assert.match(g.char, /^[\x21-\x7e]$/);
        assert(palette.has(g.color));
        assert([g.x, g.y, g.size, g.alpha].every(Number.isFinite));
        assert(g.x >= 0 && g.x <= width && g.y >= 0 && g.y <= height);
        assert(g.size > 0 && g.alpha > 0 && g.alpha <= 1);
      }
    }
  }
});

test('fixed independent mobile density and bounded work stay below 1400 glyphs', () => {
  let mobileMax = 0, desktopMax = 0;
  for (const width of [320, 390, 1160]) for (const time of [0, 4, 8, 16, 32]) {
    for (const energy of [0, .5, 1]) {
      const count = capture(frame({ width, height: width < 600 ? 290 : 610, time, energy })).glyphs.length;
      assert(count > 35 && count < 1400, `${width}px: ${count} glyphs`);
      if (width < 600) mobileMax = Math.max(mobileMax, count);
      else desktopMax = Math.max(desktopMax, count);
    }
  }
  assert(mobileMax < desktopMax, `${mobileMax} mobile versus ${desktopMax} desktop`);
});

test('floor travel remains continuous across a full tunnel phase wrap', () => {
  for (const boundary of [{ time: 1 / .022, flow: 0 }, { time: 4, flow: 1024 }]) {
    const before = capture(frame({ time: boundary.time - .00001, flow: boundary.flow - .00001 }))
      .glyphs.filter(g => g.color === '#504945');
    const after = capture(frame({ time: boundary.time + .00001, flow: boundary.flow + .00001 }))
      .glyphs.filter(g => g.color === '#504945');
    assert(before.length > 0);
    assert.equal(before.length, after.length);
    for (let i = 0; i < before.length; i++) {
      assert(Math.abs(before[i].x - after[i].x) < .05);
      assert(Math.abs(before[i].y - after[i].y) < .05);
    }
  }
});

test('bounded pointer and hostile numeric inputs cannot leak non-finite values', () => {
  for (const input of [
    frame({ width: 0, height: 0, time: NaN, energy: Infinity, pointerX: -Infinity, flow: NaN }),
    frame({ width: NaN, height: Infinity, pointerY: NaN, intro: -Infinity }),
    frame({ time: 1e20, energy: -2, pointerX: 100, pointerY: -100, flow: 1e20 }),
  ]) {
    const pose = hyperraumPose(input);
    assert(pose.scale > 0);
    for (const value of Object.values(pose)) if (typeof value === 'number') assert(Number.isFinite(value));
    const result = capture(input);
    assert.equal(result.cats.length, 1);
    for (const g of result.glyphs) assert([g.x, g.y, g.size, g.alpha].every(Number.isFinite));
  }
  assert.deepEqual(
    hyperraumPose(frame({ pointerX: 50, pointerY: -50 })),
    hyperraumPose(frame({ pointerX: 1, pointerY: -1 })),
  );
});
