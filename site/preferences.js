/* SPDX-License-Identifier: GPL-3.0-or-later */
(() => {
  'use strict';
  const resolveLanguage = (locales, saved) => {
    if (saved === 'de' || saved === 'en') return saved;
    return /^de(?:-|$)/i.test(locales?.[0] || 'en') ? 'de' : 'en';
  };
  const resolveTheme = (saved, systemDark) =>
    saved === 'light' || saved === 'dark' ? saved : (systemDark ? 'dark' : 'light');
  const read = key => {
    try { return globalThis.localStorage?.getItem(`astro-site.${key}`) || null; }
    catch { return null; }
  };
  const save = (key, value) => {
    try { globalThis.localStorage?.setItem(`astro-site.${key}`, value); }
    catch { /* The page remains usable when storage is disabled. */ }
  };
  globalThis.AstroPreferences = { resolveLanguage, resolveTheme, read, save };
  if (typeof document !== 'undefined') {
    document.documentElement.lang = resolveLanguage(navigator.languages, read('language'));
    document.documentElement.dataset.theme = resolveTheme(read('theme'), matchMedia('(prefers-color-scheme: dark)').matches);
  }
})();
