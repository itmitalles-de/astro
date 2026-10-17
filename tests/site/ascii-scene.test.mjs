// SPDX-License-Identifier: GPL-3.0-or-later
import test from 'node:test';
import assert from 'node:assert/strict';
import { sceneFixture } from './scene-fixture.mjs';

test('the exact visibility threshold starts one animation loop', async () => {
  const scene = await sceneFixture();
  scene.intersect(0);scene.intersect(.1);
  assert.equal(scene.field.dataset.motion, 'running');
  assert.equal(scene.queued.size, 1);
  scene.intersect(.1);
  assert.equal(scene.queued.size, 1, 'repeated observer delivery cannot create another loop');
});

test('DPR-only changes refresh the backing pixels without starting motion', async () => {
  const scene = await sceneFixture({ initiallyPaused: true });
  const resolution = () => [...scene.media].find(([query]) => query === `(resolution: ${devicePixelRatio}dppx)`);
  const first = resolution();
  assert.ok(first, 'observe resolution changes, not only the element CSS box');
  globalThis.devicePixelRatio = 1.5;first[1].emit('change', { matches: false });
  assert.equal(scene.canvas.width, 1740);
  const second = resolution();
  assert.ok(second, 'rearm the resolution query for the new screen');
  globalThis.devicePixelRatio = 2;second[1].emit('change', { matches: false });
  assert.equal(scene.canvas.width, 1740, 'the backing ratio stays capped at 1.5');
  globalThis.devicePixelRatio = 1;window.emit('resize');
  assert.equal(scene.canvas.width, 1160, 'browser resize also refreshes the backing pixels');
  assert.equal(scene.field.dataset.motion, 'paused');
  assert.equal(scene.queued.size, 0);
});

test('flowing glyphs reuse a bounded set of font specifications', async () => {
  const scene = await sceneFixture();
  scene.intersect(1);
  for (let frame = 0; frame < 50; frame++) scene.step();
  assert.ok(scene.fonts.size <= 100, `${scene.fonts.size} distinct fonts in 50 frames churn the Canvas font cache`);
});
