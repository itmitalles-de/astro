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
  const path = [];
  const find = node => {
    if (!node.children) return node.id === selected;
    if (!node.children.some(find)) return false;
    path.push(node);
    return true;
  };
  find(tree);
  let container;
  for (const node of path) {
    if (node.axis !== axis) break;
    container = node;
  }
  // Match Kitty's proportional=yes: duplicate the selected leaf's weight in
  // its contiguous same-axis container, preserving every other leaf's weight.
  const weights = new Map();
  const weigh = (node, weight) => {
    if (!node.children) { weights.set(node.id, weight); return; }
    weigh(node.children[0], weight * node.ratio);
    weigh(node.children[1], weight * (1 - node.ratio));
  };
  if (container) { weigh(container, 1); weights.set(added.id, weights.get(selected)); }
  const rebalance = node => {
    if (!node.children) return { node, weight: weights.get(node.id) };
    const [one, two] = node.children.map(rebalance);
    const weight = one.weight + two.weight;
    const ratio = one.weight / weight;
    const unchanged = one.node === node.children[0] && two.node === node.children[1] && ratio === node.ratio;
    return { node: unchanged ? node : { ...node, ratio, children: [one.node, two.node] }, weight };
  };
  const visit = node => {
    if (!node.children) return node.id === selected ? { axis, ratio: .5, children: [node, added] } : node;
    const children = node.children.map(visit);
    const next = children.every((child, i) => child === node.children[i]) ? node : { ...node, children };
    return node === container ? rebalance(next).node : next;
  };
  return visit(tree);
}
