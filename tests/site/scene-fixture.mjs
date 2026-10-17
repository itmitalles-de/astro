// SPDX-License-Identifier: GPL-3.0-or-later
// Controlled DOM/scheduler fixture; real Canvas pixels are checked in browser QA.
import { createAsciiScene } from '../../site/ascii-scene.mjs';

class Element {
  constructor() { this.dataset = {}; this.listeners = new Map(); this.attributes = {}; }
  addEventListener(name, callback, options = {}) {
    const entries = this.listeners.get(name) || [];
    entries.push({ callback, once: options.once });this.listeners.set(name, entries);
  }
  removeEventListener(name, callback) {
    this.listeners.set(name, (this.listeners.get(name) || []).filter(entry => entry.callback !== callback));
  }
  emit(name, event = {}) {
    for (const { callback, once } of [...(this.listeners.get(name) || [])]) {
      if (once) this.removeEventListener(name, callback);
      callback(event);
    }
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  getBoundingClientRect() { return { width: 1160, height: 610, top: 0, left: 0 }; }
}

export async function sceneFixture(variant, { reduced = false, initiallyPaused = false } = {}) {
  let now = 0, sequence = 0, font = '', fontWrites = 0;
  const queued = new Map(), fonts = new Set(), media = new Map(), nodes = new Map(), saved = [];
  const field = new Element(), canvas = new Element(), element = new Element();
  const context = {
    fillText() {}, setTransform() {}, fillRect() {}, translate() {}, scale() {},
    save() { saved.push({ font, fillStyle: this.fillStyle, globalAlpha: this.globalAlpha }); },
    restore() { const state = saved.pop();font = state.font;this.fillStyle = state.fillStyle;this.globalAlpha = state.globalAlpha; },
  };
  Object.defineProperty(context, 'font', { get: () => font, set(value) { font = value;fonts.add(value);fontWrites++; } });
  canvas.getContext = () => context;
  for (const selector of ['#ascii-scene', '#ascii-controls', '#ascii-pause', '#ascii-scatter', '.ascii-caption > [data-i18n]']) {
    nodes.set(selector, selector === '#ascii-scene' ? field : new Element());
  }
  element.querySelector = selector => selector === 'canvas' ? canvas : nodes.get(selector);
  const document = new Element();
  document.documentElement = { dataset: { asciiVariant: variant } };
  document.fonts = { ready: Promise.resolve() };document.hidden = false;
  globalThis.document = document;globalThis.window = new Element();globalThis.devicePixelRatio = 1;
  Object.defineProperty(globalThis, 'performance', { configurable: true, value: { now: () => now } });
  globalThis.requestAnimationFrame = callback => { const id = ++sequence;queued.set(id, callback);return id; };
  globalThis.cancelAnimationFrame = id => queued.delete(id);
  globalThis.matchMedia = query => {
    if (!media.has(query)) {
      const match = new Element();match.matches = query.includes('reduced-motion') && reduced;media.set(query, match);
    }
    return media.get(query);
  };
  let intersection, resize;
  globalThis.IntersectionObserver = class {
    constructor(callback, options) { intersection = { callback, options }; }
    observe() {}
  };
  globalThis.ResizeObserver = class { constructor(callback) { resize = callback; } observe() {} };
  const controller = await createAsciiScene({ element, translate: key => key, initiallyPaused });
  await Promise.resolve();
  return {
    field, canvas, nodes, document, media, queued, fonts, controller,
    get fontWrites() { return fontWrites; },
    intersect(ratio) { intersection.callback([{ isIntersecting: ratio > 0, intersectionRatio: ratio }]); },
    resize() { resize(); },
    step(ms = 50) { now += ms;const callbacks = [...queued.values()];queued.clear();for (const callback of callbacks) callback(now); },
  };
}
