import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./OnboardingTour.vue', import.meta.url), 'utf8');

test('the tour card is a named dialog that takes focus', () => {
  assert.match(source, /role="dialog" aria-modal="true" aria-labelledby="tour-title"/);
  assert.match(source, /@after-enter="focusNext"/);
});

test('Escape skips the tour and Tab stays inside the card', () => {
  assert.match(source, /event\.key === 'Escape'[\s\S]*this\.skip\(\)/);
  assert.match(source, /document\.addEventListener\('keydown', this\.onKeydown\)/);
  assert.match(source, /document\.removeEventListener\('keydown', this\.onKeydown\)/);
});

test('step counter and skip link stay readable on the dark card', () => {
  assert.doesNotMatch(source, /text-white\/35/);
});
