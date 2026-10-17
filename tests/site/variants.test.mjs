import test from 'node:test';
import assert from 'node:assert/strict';
import '../../site/preferences.js';

test('only the three requested variants can select a hero composition, with a safe Orbit default',()=>{
  const {resolveVariant}=globalThis.AstroPreferences;
  for(const value of ['orbit','zoomies','hyperraum'])assert.equal(resolveVariant(value),value);
  for(const value of [null,undefined,'','Orbit','../../other','<script>','matrix'])assert.equal(resolveVariant(value),'orbit');
});
