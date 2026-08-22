import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./SettingsJobs.vue', import.meta.url), 'utf8');

test('job card renders rating tags for their configured source', () => {
  assert.match(source, /rating_source !== 'imdb' && job\.filters\.vote_average_gte/);
  assert.match(source, /IMDB Rating &ge; \{\{ job\.filters\.imdb_rating_gte \}\}/);
});

test('job card summarizes excluded TMDb keywords', () => {
  assert.match(source, /job\.filters\.without_keywords && job\.filters\.without_keywords\.length/);
});
