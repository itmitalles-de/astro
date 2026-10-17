# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep the explanatory diagram aligned with the supported native split API."""
import json
import importlib
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeDiagramParityTests(unittest.TestCase):
    def test_all_ordinary_addition_sequences_through_six_panes_match_kitty(self):
        try:
            splits = importlib.import_module('kitty.layout.splits')
            Pair, Splits = splits.Pair, splits.Splits
        except ImportError:
            self.skipTest('Run through kitty +runpy to exercise the native layout API')
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is needed for the optional native/website parity check')

        def native(tree):
            if 'id' in tree:
                return tree['id']
            pair = Pair(tree['axis'] == 'columns')
            pair.bias = tree['ratio']
            pair.one, pair.two = map(native, tree['children'])
            return pair

        def model(pair):
            if isinstance(pair, int):
                return {'id': pair}
            return {'axis': 'columns' if pair.horizontal else 'rows', 'ratio': pair.bias,
                    'children': [model(pair.one), model(pair.two)]}

        def ids(tree):
            return [tree['id']] if 'id' in tree else [wid for child in tree['children'] for wid in ids(child)]

        cases = []

        def walk(tree, remaining):
            if not remaining:
                return
            for selected in ids(tree):
                for axis in ('columns', 'rows'):
                    layout = Splits(0, 0, 'split_axis=auto;proportional=yes;equalize_on_window_close=yes')
                    layout.pairs_root = native(tree)
                    layout.split_and_add_window(layout.pairs_root.pair_for_window(selected), selected,
                                                max(ids(tree)) + 1, axis == 'columns', True)
                    expected = model(layout.pairs_root)
                    cases.append({'tree': tree, 'selected': selected, 'axis': axis, 'expected': expected})
                    walk(expected, remaining - 1)

        for axis, other in (('columns', 'rows'), ('rows', 'columns')):
            walk({'axis': axis, 'ratio': .6, 'children': [{'id': 1},
                  {'axis': other, 'ratio': .5, 'children': [{'id': 2}, {'id': 3}]}]}, 3)
        script = '''
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const { splitLayout, MAX_PANES } = await import(pathToFileURL(process.argv[1]).href);
assert.equal(MAX_PANES, 6, 'update this native contract if the playground limit changes');
const cases = JSON.parse(readFileSync(0, 'utf8'));
function freeze(tree) {
  if (tree.children) { tree.children.forEach(freeze);Object.freeze(tree.children); }
  return Object.freeze(tree);
}
function compare(actual, expected) {
  assert.equal(actual.axis, expected.axis);assert.equal(actual.id, expected.id);
  if (!expected.children) return;
  assert.ok(Math.abs(actual.ratio - expected.ratio) < 1e-12, `${actual.ratio} != ${expected.ratio}`);
  actual.children.forEach((child, i) => compare(child, expected.children[i]));
}
for (const sample of cases) {
  const before = JSON.stringify(sample.tree);
  freeze(sample.tree);
  compare(splitLayout(sample.tree, sample.selected, sample.axis), sample.expected);
  assert.equal(JSON.stringify(sample.tree), before);
}
console.log(cases.length);
'''
        result = subprocess.run([node, '--input-type=module', '-e', script, str(ROOT / 'site/ui-state.mjs')],
                                input=json.dumps(cases), text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(int(result.stdout), len(cases))
        self.assertGreater(len(cases), 1000)


if __name__ == '__main__':
    unittest.main()
