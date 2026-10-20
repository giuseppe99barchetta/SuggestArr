import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { createYearRecapDemo, DEMO_TITLES, storyDescription, YEAR_RECAP_STORIES, yearRecapCaption } from './yearRecapDemo.js';
import { recapShareTargets } from './recapCanvas.js';

test('personal yearly sample totals match their monthly series and genre distribution', () => {
  const data = createYearRecapDemo();
  assert.equal(data.year, 2026);
  assert.equal(data.isDemo, true);
  assert.equal(data.requested.movies + data.requested.series, data.requested.total);
  assert.equal(data.monthly.reduce((sum, m) => sum + m.requests, 0), 248);
  assert.equal(data.watchMinutes, 314 * 60 + 20);
  assert.equal(data.genres.reduce((sum, genre) => sum + genre.percent, 0), 100);
  assert.equal(data.peakMonth.month, 'Oct');
  assert.equal(data.peakMonth.minutes, 51 * 60);
});

test('server demo scales every count and monthly value fivefold without changing genres', () => {
  const personal = createYearRecapDemo();
  const server = createYearRecapDemo('server', 'plex');
  assert.equal(server.activeUsers, 12);
  assert.equal(server.providerLabel, 'Plex');
  for (const key of ['total', 'movies', 'series']) assert.equal(server.requested[key], personal.requested[key] * 5);
  for (const key of ['movies', 'episodes', 'series']) assert.equal(server.watched[key], personal.watched[key] * 5);
  assert.equal(server.watchMinutes, 1571 * 60 + 40);
  assert.deepEqual(server.genres, personal.genres);
  server.monthly.forEach((month, i) => assert.equal(month.minutes, personal.monthly[i].minutes * 5));
});

test('all nine share captions and accessible descriptions disclose fictional data and the year', () => {
  assert.equal(YEAR_RECAP_STORIES.length, 9);
  const data = createYearRecapDemo('server');
  for (const story of YEAR_RECAP_STORIES) {
    const caption = yearRecapCaption(data, story);
    assert.match(caption, /2026.*Preview.*Sample data/);
    assert.ok(caption.length <= 300, 'caption must fit a Bluesky post');
    assert.match(storyDescription(data, story), /Fictional sample data for 2026/);
    const targets = recapShareTargets(null, { title: '2026 Year Recap · Preview · Sample data', caption });
    assert.match(new URL(targets[0].url).searchParams.get('title'), /Preview.*Sample data/);
    assert.equal(new URL(targets[3].url).searchParams.get('text'), caption);
  }
});

test('demo artwork is bundled, portrait, self-contained SVG with no remote resources', () => {
  assert.equal(DEMO_TITLES.length, 4);
  for (const title of DEMO_TITLES) {
    const svg = readFileSync(new URL(title.artwork), 'utf8');
    assert.match(svg, /viewBox="0 0 400 600"/);
    assert.doesNotMatch(svg, /<image|<script|href=|@import/);
  }
  const one = createYearRecapDemo();
  one.titles[0].title = 'changed';
  assert.equal(createYearRecapDemo().titles[0].title, 'Orbit');
});
