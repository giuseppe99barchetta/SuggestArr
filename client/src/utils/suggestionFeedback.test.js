import assert from 'node:assert/strict';
import { test } from 'node:test';

import { SEEN_OPTIONS, saveSeenFeedback } from './suggestionFeedback.js';

test('every rating offered on a card records a watched or seen verdict', () => {
  assert.deepEqual(
    SEEN_OPTIONS.map(option => option.feedback),
    ['seen_liked', 'seen_disliked', 'already_seen'],
  );
});

test('the neutral option stays neutral', () => {
  // Watching something is not a verdict on it, so the plain "Seen it" option must not
  // map to a value that teaches the recommender a preference.
  const seen = SEEN_OPTIONS.find(option => option.value === 'seen');
  assert.equal(seen.feedback, 'already_seen');
});

test('a rating carries the title and year the recommendation prompt needs', async () => {
  const calls = [];
  const http = { put: (url, body) => { calls.push({ url, body }); return Promise.resolve(); } };

  await saveSeenFeedback(http, 5, SEEN_OPTIONS[0], { title: 'Arrival', release_date: '2016-11-11' });

  assert.equal(calls[0].url, '/api/automation/requests/workflow/5/feedback');
  assert.equal(calls[0].body.feedback, 'seen_liked');
  assert.equal(calls[0].body.title, 'Arrival');
  assert.equal(calls[0].body.year, 2016);
});

test('a missing or unparsable release date sends a null year rather than NaN', async () => {
  const calls = [];
  const http = { put: (url, body) => { calls.push(body); return Promise.resolve(); } };

  await saveSeenFeedback(http, 5, SEEN_OPTIONS[0], { title: 'Untitled' });
  await saveSeenFeedback(http, 6, SEEN_OPTIONS[0], { title: 'Odd', release_date: 'soon' });

  assert.equal(calls[0].year, null);
  assert.equal(calls[1].year, null);
});
