import test from 'node:test';
import assert from 'node:assert/strict';
import { badgeHint, badgeMedallion, latestBadge, markBadgesSeen, newlyUnlocked, showHitRate, upNext } from './recapBadges.js';

const store = new Map();
globalThis.window = { localStorage: {
  getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, value),
} };

const badge = (id, kind, threshold, extra = {}) => ({ id, kind, threshold, progress: 0, unlocked: false, unlocked_at: null, ...extra });

test('medallions and hints describe each badge kind', () => {
  assert.deepEqual(badgeMedallion(badge('titles_1000', 'titles', 1000)), { text: '1K', unit: 'titles' });
  assert.deepEqual(badgeMedallion(badge('years_2', 'days', 730)), { text: '2', unit: 'years' });
  assert.deepEqual(badgeMedallion(badge('countries_5', 'variety', 5)), { icon: 'fas fa-globe' });
  assert.equal(badgeHint(badge('titles_25', 'titles', 25, { progress: 24 })), '1 more title to go');
  assert.equal(badgeHint(badge('watched_10', 'watched', 10, { progress: 3 })), 'Watch 7 more picks');
  assert.equal(badgeHint(badge('streak_6', 'streak', 6, { progress: 2 })), 'Best so far: 2 of 6 months');
  assert.equal(badgeHint(badge('one_year', 'days', 365, { unlocks_at: '2027-03-04T00:00:00+00:00' })), 'Unlocks Mar 4, 2027');
  assert.equal(badgeHint(badge('genres_5', 'variety', 5, { progress: 3 })), '3 of 5 so far');
  assert.equal(badgeHint(badge('titles_10', 'titles', 10, { unlocked: true, unlocked_at: '2026-01-15T12:00:00+00:00' })), 'Unlocked Jan 15, 2026');
});

test('latest badge follows unlock dates rather than list order', () => {
  const badges = [badge('titles_10', 'titles', 10, { unlocked: true, unlocked_at: '2026-05-01' }),
    badge('titles_25', 'titles', 25), badge('watched_1', 'watched', 1, { unlocked: true, unlocked_at: '2026-06-01' }),
    badge('one_year', 'days', 365, { unlocked: true, unlocked_at: '2026-02-01' })];
  assert.equal(latestBadge(badges).id, 'watched_1');
  assert.equal(latestBadge([]), null);
});

test('celebrations start silently and then report only new unlocks', () => {
  const recap = { scope: 'personal', badges: [badge('titles_10', 'titles', 10, { unlocked: true, unlocked_at: '2026-01-01' }), badge('titles_25', 'titles', 25)] };
  assert.deepEqual(newlyUnlocked(recap, 7), []);
  recap.badges[1] = { ...recap.badges[1], unlocked: true, unlocked_at: '2026-02-01' };
  assert.deepEqual(newlyUnlocked(recap, 7).map(item => item.id), ['titles_25']);
  assert.deepEqual(newlyUnlocked(recap, 8), [], 'another user on the same browser has their own history');
  markBadgesSeen(recap, 7);
  assert.deepEqual(newlyUnlocked(recap, 7), []);
});

test('up next ranks locked badges by share of progress; hit rate needs a meaningful share', () => {
  const badges = [badge('titles_1000', 'titles', 1000, { progress: 597 }), badge('watched_10', 'watched', 10, { progress: 9 }),
    badge('genres_5', 'variety', 5), badge('titles_10', 'titles', 10, { progress: 10, unlocked: true }), badge('streak_3', 'streak', 3, { progress: 1 })];
  assert.deepEqual(upNext(badges).map(item => item.id), ['watched_10', 'titles_1000', 'streak_3']);
  assert.equal(showHitRate({ hit_rate: 0, watched: 2 }), false);
  assert.equal(showHitRate({ hit_rate: 40, watched: 2 }), false);
  assert.equal(showHitRate({ hit_rate: 12, watched: 30 }), true);
});
