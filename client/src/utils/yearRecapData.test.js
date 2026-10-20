import test from 'node:test';
import assert from 'node:assert/strict';
import { canvasBlob } from './recapCanvas.js';
import { prepareYearRecap, yearStories, yearCaption, yearDescription } from './yearRecapData.js';

const real = () => ({ year: 2025, isDemo: false, scope: 'personal', requested: { total: 3, movies: 2, series: 1 },
  watched: null, watchMinutes: null, watchNote: 'Not loaded.', genres: [], genreCoverage: 0, titles: [],
  peakMonth: { label: 'May', requests: 2 }, monthly: [] });

test('real stories and captions preserve the year and unavailable watch data', () => {
  const data = prepareYearRecap(real());
  const stories = yearStories(data);
  // No watch data, genres or titles: those stories are skipped instead of shown empty.
  assert.deepEqual(stories.map(story => story.id), ['intro', 'discovery', 'time', 'summary']);
  assert.equal(stories[0].title, 'Your 2025, on screen');
  assert.equal(stories[2].title, 'A year of discoveries');
  assert.match(yearCaption(data, stories.at(-1)), /2025.*3 recorded titles/);
  assert.doesNotMatch(yearCaption(data, stories.at(-1)), /Sample|undefined|null|NaN/);
  for (const story of stories) assert.doesNotMatch(yearDescription(data, story), /Sample|undefined|null|NaN/);
});

test('cover URLs reject installation paths and arbitrary hosts', () => {
  const data = real();
  data.titles = [{ poster_path: '/cover.jpg' }, { poster_path: 'https://internal.example/private.jpg' }];
  const result = prepareYearRecap(data);
  assert.equal(result.titles[0].artwork, 'https://image.tmdb.org/t/p/w342/cover.jpg');
  assert.equal(result.titles[1].artwork, null);
});

test('PNG export recovers when the browser encoder never calls back', async () => {
  const blob = await canvasBlob({ toBlob() {}, toDataURL: () => 'data:image/png;base64,AQID' }, 10);
  assert.equal(blob.type, 'image/png');
  assert.deepEqual(new Uint8Array(await blob.arrayBuffer()), new Uint8Array([1, 2, 3]));
});

test('hit rate, badges and streak stories appear only with real data behind them', () => {
  const data = prepareYearRecap({ ...real(), requested: { total: 0, movies: 0, series: 0 }, hitRate: { watched: 0, total: 0, percent: 0, movies: 0, series: 0 }, badgesUnlocked: [] });
  // Nothing requested: no empty chart, no 0% hit rate, no empty badge list.
  assert.deepEqual(yearStories(data).map(story => story.id), ['intro', 'discovery', 'summary']);
  const full = prepareYearRecap({ ...real(), hitRate: { watched: 3, total: 6, percent: 50, movies: 2, series: 1 },
    streak: { longest: 3, months: 3 }, badgesUnlocked: [{ id: 'titles_10', kind: 'titles', label: 'First discoveries', unlockedAt: '2025-03-01T00:00:00+00:00' }] });
  const stories = yearStories(full);
  assert.deepEqual(stories.map(story => story.id), ['intro', 'discovery', 'hitrate', 'time', 'badges', 'summary']);
  assert.match(yearDescription(full, stories[2]), /50% of the titles requested this year were watched/);
  assert.match(yearDescription(full, stories[3]), /Longest watch streak: 3 months/);
  assert.match(yearDescription(full, stories[4]), /First discoveries unlocked this year/);
  assert.match(yearCaption(full, stories.at(-1)), /50% of them watched/);
});

test('stories with too little behind them are left out', () => {
  const thin = prepareYearRecap({ ...real(), requested: { total: 2, movies: 1, series: 1 },
    watched: { movies: 1, episodes: 1, series: 1 }, genres: [{ label: 'Drama', percent: 100 }], genreCoverage: 2,
    hitRate: { watched: 5, total: 60, percent: 8, movies: 5, series: 0 } });
  assert.deepEqual(yearStories(thin).map(story => story.id), ['intro', 'discovery', 'summary']);
});
