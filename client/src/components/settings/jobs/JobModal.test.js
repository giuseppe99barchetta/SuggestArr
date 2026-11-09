import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./JobModal.vue', import.meta.url), 'utf8');

test('the modal keeps Tab inside, takes focus on open and gives it back on close', () => {
  assert.match(source, /ref="dialog" role="dialog" aria-modal="true"/);
  assert.match(source, /if \(event\.key === 'Tab'\) return this\.keepFocusInside\(event\)/);
  assert.match(source, /this\.\$refs\.dialog\?\.focus\(\)/);
  assert.match(source, /this\.opener\.focus\(\)/);
});

test('native dialogs and the jobs tour keep their own keys', () => {
  assert.match(source, /querySelector\('dialog\[open\], \[aria-labelledby="tour-title"\]'\)/);
});
