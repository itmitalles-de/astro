import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { messages } from '../../site/content.mjs';

test('both languages cover every visible text, accessible label and image description', async () => {
  const html = await readFile(new URL('../../site/index.html', import.meta.url), 'utf8');
  const keys = new Set([...html.matchAll(/data-(?:i18n|aria|alt)="([^"]+)"/g)].map(match => match[1]));
  assert.deepEqual(Object.keys(messages.en).sort(), Object.keys(messages.de).sort());
  for (const locale of ['en', 'de']) {
    for (const key of keys) assert(messages[locale][key]?.trim(), `Missing ${locale} translation: ${key}`);
  }
});

test('the Wayland FAQ reports the bounded native verification rather than an open test gap', async () => {
  const html = await readFile(new URL('../../site/index.html', import.meta.url), 'utf8');
  for (const locale of ['en', 'de']) {
    assert.match(messages[locale].faq1a, /Sway/);
    assert.match(messages[locale].faq1a, /XWayland/);
    assert.match(messages[locale].faq1a, /GNOME/);
    assert.match(messages[locale].faq1a, /X11/);
  }
  assert.ok(html.includes(messages.en.faq1a), 'the static fallback must give the same verification limits');
  for (const locale of ['en', 'de']) assert.match(messages[locale].agentsBody, /\bagy\b/);
  assert.ok(html.includes(messages.en.agentsBody), 'the static fallback must match the English agentsBody copy');
});
