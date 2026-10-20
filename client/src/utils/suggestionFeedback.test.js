import assert from 'node:assert/strict';
import { test } from 'node:test';

import { SEEN_OPTIONS, loadSeenRatingMode, ratedSeenOption, saveSeenFeedback } from './suggestionFeedback.js';

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

test('star ratings map onto the existing verdicts', () => {
  assert.equal(ratedSeenOption(10).feedback, 'seen_liked');
  assert.equal(ratedSeenOption(7).feedback, 'seen_liked');
  assert.equal(ratedSeenOption(6).feedback, 'already_seen');
  assert.equal(ratedSeenOption(5).feedback, 'already_seen');
  assert.equal(ratedSeenOption(4).feedback, 'seen_disliked');
  assert.equal(ratedSeenOption(1).feedback, 'seen_disliked');
  assert.equal(ratedSeenOption(8).label, 'Seen it, rated 8/10');
});

test('no stars is the plain seen option', () => {
  assert.equal(ratedSeenOption(null), SEEN_OPTIONS.find(option => option.value === 'seen'));
});

test('trakt details are sent only when given', async () => {
  const calls = [];
  const http = { put: (url, body) => { calls.push(body); return Promise.resolve(); } };

  await saveSeenFeedback(http, 5, SEEN_OPTIONS[2], { title: 'Plain' });
  await saveSeenFeedback(http, 6, ratedSeenOption(9), { title: 'Rated' }, { rating: 9, markWatched: false });
  await saveSeenFeedback(http, 7, ratedSeenOption(null), { title: 'Unrated' }, { rating: null, markWatched: true });

  assert.equal('rating' in calls[0], false);
  assert.equal('mark_watched' in calls[0], false);
  assert.deepEqual([calls[1].feedback, calls[1].rating, calls[1].mark_watched], ['seen_liked', 9, false]);
  assert.deepEqual([calls[2].feedback, calls[2].rating, calls[2].mark_watched], ['already_seen', null, true]);
});

test('the star picker is used only when the server says the rating reaches Trakt', async () => {
  const reply = data => ({ get: () => Promise.resolve({ data }) });
  assert.equal(await loadSeenRatingMode(reply({ sync_seen_feedback: true })), true);
  assert.equal(await loadSeenRatingMode(reply({ sync_seen_feedback: false })), false);
  assert.equal(await loadSeenRatingMode(reply({})), false);
  assert.equal(await loadSeenRatingMode({ get: () => Promise.reject(new Error('404')) }), false);
});
