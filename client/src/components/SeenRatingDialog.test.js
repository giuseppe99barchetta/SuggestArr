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

test('a show with no stars and no episodes says it stays in SuggestArr', () => {
  // Nothing reaches Trakt in that case, so the dialog must not imply it does.
  assert.match(source, /localOnly\(\) \{\s*return this\.item\.media_type === 'tv' && !this\.markWatched;/);
  assert.match(source, /localOnly \? 'Seen it, SuggestArr only' : 'Seen it, no rating'/);
  assert.match(source, /v-if="localOnly && !rating"[^>]*>Without stars or the episodes box, this is saved in SuggestArr only/);
});

test('saving without stars is allowed, saving with stars needs a pick', () => {
  assert.match(source, /@click="save\(null\)">\{\{ localOnly/);
  assert.match(source, /:disabled="busy \|\| !rating" @click="save\(rating\)"/);
});
