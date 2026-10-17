// SPDX-License-Identifier: GPL-3.0-or-later
import { initialLayout, leaves, splitLayout, MAX_PANES } from './ui-state.mjs';
import { messages } from './content.mjs';

const preferences = globalThis.AstroPreferences;
const root = document.documentElement;
let language = preferences.resolveLanguage(navigator.languages, preferences.read('language'));
let themeChoice = ['light', 'dark'].includes(preferences.read('theme')) ? preferences.read('theme') : 'system';
const systemTheme = matchMedia('(prefers-color-scheme: dark)');
let layout = initialLayout();
let selected = 1;
let copyReset;
let asciiScene;
const t = (key, values = {}) => Object.entries(values).reduce(
  (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)), messages[language][key] || messages.en[key] || key,
);

function renderDiagram(focusPane = false) {
  const diagram = document.querySelector('#layout-diagram');
  const build = node => {
    if (node.children) {
      const split = document.createElement('div');
      split.className = `layout-split ${node.axis}`;
      for (const [index, child] of node.children.entries()) {
        const wrapper = document.createElement('div');
        wrapper.className = 'layout-child';
        wrapper.style.flexGrow = String(index === 0 ? node.ratio : 1 - node.ratio);
        wrapper.append(build(child));
        split.append(wrapper);
      }
      return split;
    }
    const pane = document.createElement('button');
    pane.type = 'button';
    pane.className = 'layout-pane';
    pane.dataset.pane = String(node.id);
    pane.setAttribute('aria-pressed', String(node.id === selected));
    const label = document.createElement('span');
    label.className = 'pane-title';
    label.textContent = `${t('pane')} ${node.id}`;
    const prompt = document.createElement('span');
    prompt.className = 'pane-prompt';
    prompt.setAttribute('aria-hidden', 'true');
    prompt.textContent = '~/project $';
    pane.append(label, prompt);
    pane.addEventListener('click', () => { selected = node.id; renderDiagram(true); });
    return pane;
  };
  diagram.replaceChildren(build(layout));
  const count = leaves(layout).length;
  const limit = count >= MAX_PANES;
  document.querySelector('#split-right').disabled = limit;
  document.querySelector('#split-below').disabled = limit;
  document.querySelector('#diagram-status').textContent = limit ? t('layoutLimit') : t('layoutStatus', { count, selected });
  if (focusPane) diagram.querySelector(`[data-pane="${selected}"]`)?.focus({ preventScroll: true });
}

function applyLanguage(next, persist = false) {
  language = next === 'de' ? 'de' : 'en';
  if (persist) preferences.save('language', language);
  for (const element of document.querySelectorAll('[data-i18n]')) element.textContent = t(element.dataset.i18n);
  for (const element of document.querySelectorAll('[data-aria]')) element.setAttribute('aria-label', t(element.dataset.aria));
  for (const element of document.querySelectorAll('[data-alt]')) element.alt = t(element.dataset.alt);
  root.lang = language;
  const toggle = document.querySelector('#language-toggle');
  toggle.textContent = language === 'en' ? 'DE' : 'EN';
  toggle.lang = language === 'en' ? 'de' : 'en';
  toggle.setAttribute('aria-label', `${toggle.textContent}: ${t('languageAction')}`);
  document.title = t('metaTitle');
  document.querySelector('meta[name=description]').content = t('metaDescription');
  document.querySelector('meta[property="og:title"]').content = t('metaTitle');
  document.querySelector('meta[property="og:description"]').content = t('metaDescription');
  document.querySelector('#copy-status').textContent = '';
  renderDiagram();
  asciiScene?.refreshLabels();
}

function applyTheme() {
  root.dataset.theme = preferences.resolveTheme(themeChoice, systemTheme.matches);
  document.querySelector('meta[name=theme-color]').content = root.dataset.theme === 'dark' ? '#191919' : '#f3f1ec';
  document.querySelector('#theme').value = themeChoice;
}

document.querySelector('#language-toggle').addEventListener('click', () => applyLanguage(language === 'en' ? 'de' : 'en', true));
document.querySelector('#theme').addEventListener('change', event => {
  themeChoice = ['light', 'dark'].includes(event.target.value) ? event.target.value : 'system';
  preferences.save('theme', themeChoice);
  applyTheme();
});
systemTheme.addEventListener('change', applyTheme);
for (const [id, axis] of [['split-right', 'columns'], ['split-below', 'rows']]) {
  document.querySelector(`#${id}`).addEventListener('click', event => {
    if (leaves(layout).length >= MAX_PANES) return;
    const fullSpan = event.shiftKey || document.querySelector('#whole-span').checked;
    layout = splitLayout(layout, selected, axis, fullSpan);
    selected = Math.max(...leaves(layout).map(pane => pane.id));
    renderDiagram();
  });
}
document.querySelector('#reset-layout').addEventListener('click', () => {
  layout = initialLayout(); selected = 1;
  document.querySelector('#whole-span').checked = false;
  renderDiagram();
});
document.querySelector('#layout-diagram').addEventListener('keydown', event => {
  const order = leaves(layout).map(pane => pane.id);
  const index = Math.max(0, order.indexOf(selected));
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
  if (step) selected = order[(index + step + order.length) % order.length];
  else if (event.key === 'Home') selected = order[0];
  else if (event.key === 'End') selected = order[order.length - 1];
  else return;
  event.preventDefault?.();
  renderDiagram(true);
});

let copyAttempt = 0;
document.querySelector('#copy-install').addEventListener('click', async () => {
  const attempt = ++copyAttempt;
  const button = document.querySelector('#copy-install');
  const code = document.querySelector('#install-commands');
  const status = document.querySelector('#copy-status');
  button.setAttribute('aria-busy', 'true');
  clearTimeout(copyReset);
  button.textContent = t('copy');
  status.textContent = '';
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard API unavailable');
    await navigator.clipboard.writeText(code.textContent);
    if (attempt !== copyAttempt) return;
    button.textContent = t('copied');
    status.textContent = t('copySuccess');
    copyReset = setTimeout(() => { if (attempt === copyAttempt) button.textContent = t('copy'); }, 2000);
  } catch {
    if (attempt !== copyAttempt) return;
    button.textContent = t('copy');
    const range = document.createRange();
    range.selectNodeContents(code);
    const selection = getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    code.focus({ preventScroll: true });
    status.textContent = t('copyUnavailable');
  } finally {
    if (attempt === copyAttempt) button.removeAttribute('aria-busy');
  }
});

applyLanguage(language);
applyTheme();

// Optional artwork must never block the site's functional controls or content.
import('./ascii-scene.mjs').then(async ({ createAsciiScene }) => {
  asciiScene = await createAsciiScene({
    element: document.querySelector('#ascii-art'), translate: t,
    initiallyPaused: preferences.read('motion') === 'paused',
    savePaused: paused => preferences.save('motion', paused ? 'paused' : 'auto'),
  });
}).catch(() => { /* The static ASCII cat remains available. */ });
