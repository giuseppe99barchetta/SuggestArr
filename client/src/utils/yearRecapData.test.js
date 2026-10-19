import test from 'node:test';
import assert from 'node:assert/strict';
import { canvasBlob } from './recapCanvas.js';
import { prepareYearRecap, yearStories, yearCaption, yearDescription } from './yearRecapData.js';

const real = () => ({ year: 2025, isDemo: false, scope: 'personal', requested: { total: 2, movies: 1, series: 1 },
  watched: null, watchMinutes: null, watchNote: 'Not loaded.', genres: [], genreCoverage: 0, titles: [],
  peakMonth: { label: 'May', requests: 2 }, monthly: [] });

test('real stories and captions preserve the year and unavailable watch data', () => {
  const data = prepareYearRecap(real());
  const stories = yearStories(data);
  assert.equal(stories[0].title, 'Your 2025, on screen');
  assert.equal(stories[3].title, 'A year of discoveries');
  assert.match(yearCaption(data, stories[6]), /2025.*2 recorded titles/);
  assert.doesNotMatch(yearCaption(data, stories[6]), /Sample|undefined|null|NaN/);
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
