import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./SettingsRequests.vue', import.meta.url), 'utf8');

test('pending cards offer an already-seen action beside approve and reject', () => {
  assert.match(source, /aria-label="Already seen it"/);
  assert.match(source, /@click="seenMenuId = request\.id"/);
});

test('the seen menu offers liked, disliked and plain seen', () => {
  assert.match(source, /label: 'Seen it, liked it', icon: 'fas fa-thumbs-up', feedback: 'interested'/);
  assert.match(source, /label: 'Seen it, did not like it', icon: 'fas fa-thumbs-down', feedback: 'not_interested'/);
  assert.match(source, /label: 'Seen it', icon: 'fas fa-eye', feedback: 'already_seen'/);
});

test('marking a suggestion seen saves feedback before clearing the card', () => {
  const method = source.slice(source.indexOf('async markSeen('), source.indexOf('async decidePending('));
  const feedbackCall = method.indexOf('/feedback');
  const rejectCall = method.indexOf("this.decidePending('reject'");
  assert.ok(feedbackCall > -1, 'markSeen should save feedback');
  assert.ok(rejectCall > -1, 'markSeen should clear the pending card');
  assert.ok(feedbackCall < rejectCall, 'feedback must be saved before the request is rejected');
});

test('a failed feedback save leaves the suggestion in the queue', () => {
  const method = source.slice(source.indexOf('async markSeen('), source.indexOf('async decidePending('));
  assert.match(method, /catch \(error\)[\s\S]*?return;/);
});

test('a liked rating is stored as a positive signal, not a neutral one', () => {
  // 'already_seen' only suppresses; 'interested' is what the recommender can learn from.
  assert.match(source, /label: 'Seen it, liked it',[^}]*feedback: 'interested'/);
});

test('the rating carries the title and year the recommender needs', () => {
  const method = source.slice(source.indexOf('async markSeen('), source.indexOf('async decidePending('));
  assert.match(method, /title: request\.title \|\| null/);
  assert.match(method, /request\.release_date \|\| request\.first_air_date/);
  assert.match(method, /year: Number\.isFinite\(year\) \? year : null/);
});
