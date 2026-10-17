import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
const modelURL = new URL('../../site/ui-state.mjs', import.meta.url);

test('ordinary split matches Kitty proportional sizing without mutating the original tree', async () => {
  assert.ok(existsSync(modelURL), 'the layout diagram needs an immutable split model');
  const { initialLayout, splitLayout, leaves } = await import(modelURL.href);
  const old = initialLayout();
  const before = JSON.stringify(old);
  const next = splitLayout(old, 1, 'columns', false);
  assert.equal(JSON.stringify(old), before);
  assert.equal(leaves(next).length, 4);
  // Kitty 0.49.2, proportional=yes: duplicate the selected pane's weight,
  // then normalize the contiguous same-axis container (.6 + .6 + .4).
  assert(Math.abs(next.ratio - .75) < 1e-12);
  assert.strictEqual(next.children[1], old.children[1]);
  assert.equal(next.children[0].axis, 'columns');
  assert.deepEqual(next.children[0].children.map(n => n.id), [1, 4]);
});

const pair = (axis, ratio, one, two) => ({ axis, ratio, children: [one, two] });
const pane = id => ({ id });
const freezeTree = node => {
  if (node.children) { node.children.forEach(freezeTree); Object.freeze(node.children); }
  return Object.freeze(node);
};
const assertLayout = (actual, expected) => {
  assert.equal(actual.axis, expected.axis);
  if (!expected.children) { assert.equal(actual.id, expected.id); return; }
  assert(Math.abs(actual.ratio - expected.ratio) < 1e-12, `${actual.ratio} !== ${expected.ratio}`);
  assert.equal(actual.children.length, expected.children.length);
  actual.children.forEach((child, i) => assertLayout(child, expected.children[i]));
};

test('ordinary splits match native row sizing on either side and keep orthogonal parents unchanged', async () => {
  const { initialLayout, splitLayout } = await import(modelURL.href);
  for (const selected of [2, 3]) {
    const tree = freezeTree(initialLayout());
    const split = pair('rows', .5, pane(selected), pane(4));
    const expected = pair('columns', .6, pane(1), selected === 2
      ? pair('rows', 2 / 3, split, pane(3)) : pair('rows', 1 / 3, pane(2), split));
    assertLayout(splitLayout(tree, selected, 'rows'), expected);
    const orthogonal = splitLayout(tree, selected, 'columns');
    assert.equal(orthogonal.ratio, .6);
    assert.equal(orthogonal.children[1].ratio, .5);
    assert.equal(orthogonal.children[1].children[selected - 2].ratio, .5);
  }
});

test('proportional sizing spans nested same-axis pairs but stops at an orthogonal ancestor', async () => {
  const { splitLayout } = await import(modelURL.href);
  // Ratios were verified with Kitty 0.49.2 Splits.split_and_add_window,
  // using split_axis=auto;proportional=yes;equalize_on_window_close=yes.
  for (const [axis, other] of [['columns', 'rows'], ['rows', 'columns']]) {
    const tree = freezeTree(pair(axis, .4, pair(axis, .25, pane(1), pane(2)),
      pair(other, .3, pane(3), pane(4))));
    const before = JSON.stringify(tree);
    const result = splitLayout(tree, 1, axis);
    assertLayout(result, pair(axis, 5 / 11,
      pair(axis, .4, pair(axis, .5, pane(1), pane(5)), pane(2)), tree.children[1]));
    assert.strictEqual(result.children[1], tree.children[1]);
    assert.equal(JSON.stringify(tree), before);

    const boundary = freezeTree(pair(other, .4, pair(axis, .25, pane(1),
      pair(axis, .6, pane(2), pane(3))), pane(4)));
    assertLayout(splitLayout(boundary, 2, axis), pair(other, .4,
      pair(axis, 5 / 29, pane(1), pair(axis, .75,
        pair(axis, .5, pane(2), pane(5)), pane(3))), pane(4)));
  }
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
