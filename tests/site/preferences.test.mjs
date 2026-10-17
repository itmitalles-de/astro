import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';

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
