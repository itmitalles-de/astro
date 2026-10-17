import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
const modelURL = new URL('../../site/ui-state.mjs', import.meta.url);

test('ordinary split replaces only the selected pane and never mutates the original tree', async () => {
  assert.ok(existsSync(modelURL), 'the layout diagram needs an immutable split model');
  const { initialLayout, splitLayout, leaves } = await import(modelURL.href);
  const old = initialLayout();
  const before = JSON.stringify(old);
  const next = splitLayout(old, 1, 'columns', false);
  assert.equal(JSON.stringify(old), before);
  assert.equal(leaves(next).length, 4);
  assert.equal(next.ratio, old.ratio);
  assert.strictEqual(next.children[1], old.children[1]);
  assert.equal(next.children[0].axis, 'columns');
  assert.deepEqual(next.children[0].children.map(n => n.id), [1, 4]);
});

test('whole-span split wraps the unchanged tree and gives the strip the selected pane share', async () => {
  const { initialLayout, splitLayout } = await import(modelURL.href);
  for (const axis of ['columns', 'rows']) {
    const tree = initialLayout();
    const next = splitLayout(tree, 1, axis, true);
    assert.equal(next.axis, axis);
    assert.strictEqual(next.children[0], tree);
    assert.deepEqual(next.children[1], { id: 4 });
    assert.equal(next.ratio, axis === 'columns' ? 1 / 1.6 : .5);
  }
});

test('the small diagram refuses a seventh pane and rejects unknown targets and directions', async () => {
  const { initialLayout, splitLayout } = await import(modelURL.href);
  let tree = initialLayout();
  for (let i = 0; i < 3; i++) tree = splitLayout(tree, 1, 'rows', false);
  assert.throws(() => splitLayout(tree, 1, 'columns', true), /limit/i);
  assert.throws(() => splitLayout(initialLayout(), 99, 'rows'), /pane/i);
  assert.throws(() => splitLayout(initialLayout(), 1, 'diagonal'), /direction/i);
});
