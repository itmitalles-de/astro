// SPDX-License-Identifier: GPL-3.0-or-later
// This is an explanatory layout diagram, not a browser terminal emulator.
export const MAX_PANES = 6;
export const initialLayout = () => ({
  axis: 'columns', ratio: .6,
  children: [{ id: 1 }, { axis: 'rows', ratio: .5, children: [{ id: 2 }, { id: 3 }] }],
});
export const leaves = node => node.children ? node.children.flatMap(leaves) : [node];
export function splitLayout(tree, selected, axis, fullSpan = false) {
  if (leaves(tree).length >= MAX_PANES) throw new RangeError('Diagram pane limit reached');
  if (!['columns', 'rows'].includes(axis)) throw new RangeError('Unknown split direction');
  if (!leaves(tree).some(n => n.id === selected)) throw new RangeError('Unknown pane');
  const added = { id: Math.max(...leaves(tree).map(n => n.id)) + 1 };
  if (fullSpan) {
    const share = node => {
      if (!node.children) return node.id === selected ? 1 : 0;
      const weights = node.axis === axis ? [node.ratio, 1 - node.ratio] : [1, 1];
      return node.children.reduce((sum, child, i) => sum + weights[i] * share(child), 0);
    };
    return { axis, ratio: 1 / (1 + share(tree)), children: [tree, added] };
  }
  const visit = node => {
    if (!node.children) return node.id === selected ? { axis, ratio: .5, children: [node, added] } : node;
    const children = node.children.map(visit);
    return children.every((child, i) => child === node.children[i]) ? node : { ...node, children };
  };
  return visit(tree);
}
