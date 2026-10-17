// SPDX-License-Identifier: GPL-3.0-or-later
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import { messages } from '../../site/content.mjs';

const appURL = new URL('../../site/app.mjs', import.meta.url);
const preferencesURL = new URL('../../site/preferences.js', import.meta.url);
const html = await readFile(new URL('../../site/index.html', import.meta.url), 'utf8');
const preferencesSource = await readFile(preferencesURL, 'utf8');
let instance = 0;

class Element {
  constructor() {
    this.dataset = {}; this.style = {}; this.attributes = new Map();
    this.children = []; this.listeners = new Map(); this.textContent = '';
  }
  addEventListener(name, handler) { this.listeners.set(name, handler); }
  setAttribute(name, value) { this.attributes.set(name, value); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  querySelector(selector) {
    const match = selector.match(/^\[data-pane="(\d+)"\]$/);
    if (!match) return null;
    const find = node => node.dataset?.pane === match[1] ? node : node.children?.map(find).find(Boolean) ?? null;
    return find(this);
  }
  focus() { document.activeElement = this; }
}

// Run the actual bootstrap and app with private DOM, clipboard and timer fixtures.
// Node test files have separate processes; each test restores every replaced global.
async function appFixture(t, { locales = ['en-US'], saved = {}, blockedStorage = false, loadApp = true } = {}) {
  const original = new Map();
  const install = (name, descriptor) => {
    original.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, ...descriptor });
  };
  const nodes = new Map();
  for (const selector of ['#layout-diagram', '#split-right', '#split-below', '#diagram-status', '#language-toggle',
    '#theme', '#whole-span', '#reset-layout', '#copy-install', '#install-commands', '#copy-status', '#ascii-art',
    'meta[name=description]', 'meta[property="og:title"]', 'meta[property="og:description"]', 'meta[name=theme-color]']) {
    nodes.set(selector, new Element());
  }
  const hero = new Element(); hero.dataset.i18n = 'hero1';
  hero.textContent = html.match(/data-i18n="hero1">([^<]+)/)[1];
  const button = nodes.get('#copy-install'); button.dataset.i18n = 'copy'; button.textContent = messages.en.copy;
  const commands = html.match(/<code>(git clone[\s\S]*?)<\/code>/)[1];
  nodes.get('#install-commands').textContent = commands;
  const canvas = { getContext: () => null };
  nodes.get('#ascii-art').querySelector = selector => selector === 'canvas' ? canvas : null;
  const ranges = [];
  const selection = { text: '', removeAllRanges() { this.text = ''; }, addRange(range) { this.text = range.element.textContent; } };
  const doc = {
    documentElement: { lang: html.match(/<html lang="([^"]+)"/)[1], dataset: {} },
    querySelector(selector) { assert(nodes.has(selector), `Missing fixture element: ${selector}`); return nodes.get(selector); },
    querySelectorAll: selector => selector === '[data-i18n]' ? [hero, button] : [],
    createElement: () => new Element(),
    createRange() { const range = { selectNodeContents(element) { this.element = element; } }; ranges.push(range); return range; },
  };
  const writes = [], pending = [], timers = new Map(), storage = new Map(Object.entries(saved));
  let timerId = 0;
  const clipboard = { writeText(text) {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    writes.push({ text, resolve, reject }); return promise;
  } };
  install('document', { value: doc });
  install('navigator', { value: { languages: locales, clipboard } });
  install('location', { value: { search: '?variant=zoomies' } });
  install('matchMedia', { value: () => ({ matches: true, addEventListener() {} }) });
  install('getSelection', { value: () => selection });
  install('setTimeout', { value: callback => { const id = ++timerId; timers.set(id, callback); return id; } });
  install('clearTimeout', { value: id => timers.delete(id) });
  install('AstroPreferences', { value: undefined, writable: true });
  install('localStorage', blockedStorage ? { get() { throw new DOMException('Blocked', 'SecurityError'); } } : {
    value: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) },
  });
  t.after(async () => {
    writes.forEach(write => write.resolve());
    await Promise.allSettled(pending);
    // Let the optional dynamic artwork import finish against its null context.
    await new Promise(resolve => setImmediate(resolve));
    for (const [name, descriptor] of original) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor); else delete globalThis[name];
    }
  });
  vm.runInThisContext(preferencesSource, { filename: preferencesURL.pathname });
  if (loadApp) await import(`${appURL.href}?fixture=${++instance}`);
  const click = selector => {
    const result = Promise.resolve(nodes.get(selector).listeners.get('click')({}));
    pending.push(result); return result;
  };
  const feedback = () => ({
    label: button.textContent, status: nodes.get('#copy-status').textContent,
    busy: button.getAttribute('aria-busy'), timers: timers.size,
    selected: selection.text, focused: doc.activeElement, ranges: ranges.length,
  });
  return { nodes, doc, hero, writes, timers, storage, selection, clipboard, click, feedback };
}

test('failed quick recopy restores truthful feedback and can recover on another success', async t => {
  const f = await appFixture(t);
  const first = f.click('#copy-install'); f.writes[0].resolve(); await first;
  assert.equal(f.feedback().label, messages.en.copied);
  assert.equal(f.timers.size, 1);
  const second = f.click('#copy-install'); f.writes[1].reject(new Error('Denied')); await second;
  assert.equal(f.feedback().label, messages.en.copy);
  assert.equal(f.feedback().status, messages.en.copyUnavailable);
  assert.equal(f.feedback().busy, null);
  assert.equal(f.timers.size, 0);
  assert.equal(f.selection.text, f.nodes.get('#install-commands').textContent);
  assert.strictEqual(f.doc.activeElement, f.nodes.get('#install-commands'));
  const third = f.click('#copy-install'); f.writes[2].resolve(); await third;
  assert.equal(f.feedback().label, messages.en.copied);
  assert.equal(f.feedback().status, messages.en.copySuccess);
  assert(f.writes.every(write => write.text === f.nodes.get('#install-commands').textContent));
});

test('a pending retry clears old success feedback and cannot be reset by an obsolete timer', async t => {
  const f = await appFixture(t);
  const first = f.click('#copy-install'); f.writes[0].resolve(); await first;
  const obsoleteReset = [...f.timers.values()][0];
  const second = f.click('#copy-install');
  assert.equal(f.feedback().label, messages.en.copy);
  assert.equal(f.feedback().status, '');
  assert.equal(f.feedback().busy, 'true');
  assert.equal(f.timers.size, 0);
  f.writes[1].resolve(); await second;
  obsoleteReset();
  assert.equal(f.feedback().label, messages.en.copied);
  const reset = [...f.timers.values()][0]; reset();
  assert.equal(f.feedback().label, messages.en.copy);
});

for (const older of ['resolve', 'reject']) for (const newer of ['resolve', 'reject']) for (const order of ['older-first', 'newer-first']) {
  test(`overlapping copies keep only the latest feedback: ${older}/${newer}/${order}`, async t => {
    const f = await appFixture(t);
    const first = f.click('#copy-install'), second = f.click('#copy-install');
    assert.equal(f.writes.length, 2, 'a pending request must not silently discard a new click');
    const settle = (index, outcome) => f.writes[index][outcome](outcome === 'reject' ? new Error('Denied') : undefined);
    if (order === 'older-first') {
      settle(0, older); await first;
      assert.equal(f.feedback().busy, 'true');
      assert.equal(f.feedback().label, messages.en.copy);
      assert.equal(f.feedback().status, '');
      assert.equal(f.feedback().ranges, 0, 'obsolete failures must not select or focus commands');
      settle(1, newer); await second;
    } else {
      settle(1, newer); await second;
      const latest = f.feedback();
      settle(0, older); await first;
      assert.deepEqual(f.feedback(), latest, 'obsolete completion must not alter feedback, focus, selection or timers');
    }
    assert.equal(f.feedback().busy, null);
    assert.equal(f.feedback().label, newer === 'resolve' ? messages.en.copied : messages.en.copy);
    assert.equal(f.feedback().status, newer === 'resolve' ? messages.en.copySuccess : messages.en.copyUnavailable);
    assert.equal(f.timers.size, newer === 'resolve' ? 1 : 0);
  });
}

test('unavailable clipboard leaves a reusable manual-copy path and releases busy state', async t => {
  const f = await appFixture(t);
  delete f.clipboard.writeText;
  for (let i = 0; i < 2; i++) {
    await f.click('#copy-install');
    assert.equal(f.feedback().busy, null);
    assert.equal(f.feedback().label, messages.en.copy);
    assert.equal(f.feedback().status, messages.en.copyUnavailable);
    assert.equal(f.selection.text, f.nodes.get('#install-commands').textContent);
  }
});

for (const blockedStorage of [false, true]) {
  test(`partial main-module failure preserves English fallback and early appearance: storage blocked=${blockedStorage}`, async t => {
    const f = await appFixture(t, { locales: ['de-DE'], blockedStorage, loadApp: false });
    assert.equal(f.doc.documentElement.lang, 'en');
    assert.equal(f.hero.textContent, messages.en.hero1);
    assert.equal(f.doc.documentElement.dataset.theme, 'dark');
    assert.equal(f.doc.documentElement.dataset.asciiVariant, 'zoomies');
  });
}

for (const [locales, saved, expected, blockedStorage] of [
  [['de-DE'], {}, 'de', false],
  [['en-US'], { 'astro-site.language': 'de' }, 'de', false],
  [['de-DE'], { 'astro-site.language': 'en' }, 'en', false],
  [['de-DE'], { 'astro-site.language': '<invalid>' }, 'de', false],
  [['de-DE'], {}, 'de', true],
]) {
  test(`app applies desired locale ${expected}: browser=${locales[0]}, saved=${saved['astro-site.language']}, blocked=${blockedStorage}`, async t => {
    const f = await appFixture(t, { locales, saved, blockedStorage });
    assert.equal(f.doc.documentElement.lang, expected);
    assert.equal(f.hero.textContent, messages[expected].hero1);
    assert.equal(f.feedback().label, messages[expected].copy);
    await f.click('#language-toggle');
    const next = expected === 'de' ? 'en' : 'de';
    assert.equal(f.doc.documentElement.lang, next);
    assert.equal(f.hero.textContent, messages[next].hero1);
    if (!blockedStorage) assert.equal(f.storage.get('astro-site.language'), next);
  });
}

test('copy completions and reset labels use the current locale after a pending language change', async t => {
  const f = await appFixture(t);
  const copy = f.click('#copy-install');
  await f.click('#language-toggle');
  f.writes[0].resolve(); await copy;
  assert.equal(f.feedback().label, messages.de.copied);
  assert.equal(f.feedback().status, messages.de.copySuccess);
  await f.click('#language-toggle');
  assert.equal(f.feedback().label, messages.en.copy);
  assert.equal(f.feedback().status, '');
  [...f.timers.values()][0]();
  assert.equal(f.feedback().label, messages.en.copy);
});

test('layout diagram supports arrow, Home and End keyboard navigation across panes', async t => {
  const f = await appFixture(t);
  await f.click('#split-right');
  const diagram = f.nodes.get('#layout-diagram');
  const keydown = key => {
    let prevented = false;
    diagram.listeners.get('keydown')({ key, preventDefault() { prevented = true; } });
    return prevented;
  };
  // Splitting pane 1 right in the 3-pane initial layout produces leaves [1, 4, 2, 3] with pane 4 selected.
  assert.equal(f.nodes.get('#diagram-status').textContent, '4 panes. Pane 4 selected.');
  assert.equal(keydown('ArrowRight'), true);
  assert.equal(f.nodes.get('#diagram-status').textContent, '4 panes. Pane 2 selected.');
  assert.equal(f.doc.activeElement?.dataset.pane, '2');
  assert.equal(keydown('ArrowDown'), true);
  assert.equal(f.nodes.get('#diagram-status').textContent, '4 panes. Pane 3 selected.');
  assert.equal(f.doc.activeElement?.dataset.pane, '3');
  assert.equal(keydown('ArrowRight'), true);
  assert.equal(f.nodes.get('#diagram-status').textContent, '4 panes. Pane 1 selected.');
  assert.equal(f.doc.activeElement?.dataset.pane, '1');
  assert.equal(keydown('End'), true);
  assert.equal(f.nodes.get('#diagram-status').textContent, '4 panes. Pane 3 selected.');
  assert.equal(f.doc.activeElement?.dataset.pane, '3');
  assert.equal(keydown('Home'), true);
  assert.equal(f.nodes.get('#diagram-status').textContent, '4 panes. Pane 1 selected.');
  assert.equal(keydown('ArrowLeft'), true);
  assert.equal(f.nodes.get('#diagram-status').textContent, '4 panes. Pane 3 selected.');
  assert.equal(keydown('ArrowUp'), true);
  assert.equal(f.nodes.get('#diagram-status').textContent, '4 panes. Pane 2 selected.');
  assert.equal(keydown('Tab'), false);
});
