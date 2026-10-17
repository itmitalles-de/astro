import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const preferences = new URL('../../site/preferences.js', import.meta.url);

test('language follows browser locale unless a valid saved choice overrides it', async () => {
  assert.ok(existsSync(preferences), 'the site needs a shared, testable preference resolver');
  await import(preferences.href);
  const { resolveLanguage } = globalThis.AstroPreferences;
  assert.equal(resolveLanguage(['de-DE', 'en-US'], null), 'de');
  assert.equal(resolveLanguage(['en-GB', 'de'], null), 'en');
  assert.equal(resolveLanguage(['fr-FR'], null), 'en');
  assert.equal(resolveLanguage(['de-DE'], 'en'), 'en');
  assert.equal(resolveLanguage(['en-US'], 'de'), 'de');
  assert.equal(resolveLanguage(['de-DE'], '<script>'), 'de');
});

test('theme follows the system and accepts only the explicit light/dark overrides', async () => {
  await import(preferences.href);
  assert.equal(typeof globalThis.AstroPreferences.resolveTheme, 'function');
  const { resolveTheme } = globalThis.AstroPreferences;
  assert.equal(resolveTheme('system', true), 'dark');
  assert.equal(resolveTheme(null, false), 'light');
  assert.equal(resolveTheme('light', true), 'light');
  assert.equal(resolveTheme('dark', false), 'dark');
  assert.equal(resolveTheme('invalid', true), 'dark');
});

test('early bootstrap keeps the actual fallback language while applying theme', async () => {
  const source = await readFile(preferences, 'utf8');
  for (const blocked of [false, true]) {
    const context = {
      document: { documentElement: { lang: 'en', dataset: {} } },
      navigator: { languages: ['de-DE'] },
      matchMedia: () => ({ matches: true }),
    };
    Object.defineProperty(context, 'localStorage', blocked
      ? { get() { throw new Error('Storage unavailable'); } }
      : { value: { getItem: key => key === 'astro-site.language' ? 'de' : 'light', setItem() {} } });
    vm.runInNewContext(source, context);
    assert.equal(context.document.documentElement.lang, 'en', 'English fallback is not translated by the bootstrap');
    assert.equal(context.document.documentElement.dataset.theme, blocked ? 'dark' : 'light');
    const prefs = context.AstroPreferences;
    assert.equal(prefs.resolveLanguage(context.navigator.languages, prefs.read('language')), 'de');
    assert.doesNotThrow(() => prefs.save('language', 'en'));
  }
});
