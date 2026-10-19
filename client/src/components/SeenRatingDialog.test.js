import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./SeenRatingDialog.vue', import.meta.url), 'utf8');

test('offers ten stars on the Trakt scale', () => {
  assert.match(source, /v-for="star in 10"/);
  assert.match(source, /role="radiogroup"/);
});

test('a show is not marked fully watched unless the user ticks it', () => {
  // Adding a show to Trakt history marks every aired episode, so TV defaults to rating only.
  assert.match(source, /markWatched: this\.item\.media_type !== 'tv'/);
  assert.match(source, /<BaseCheckbox\s+v-if="item\.media_type === 'tv'"/);
});

test('saving without stars is allowed, saving with stars needs a pick', () => {
  assert.match(source, /@click="save\(null\)">Seen it, no rating</);
  assert.match(source, /:disabled="busy \|\| !rating" @click="save\(rating\)"/);
});
