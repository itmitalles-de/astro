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
