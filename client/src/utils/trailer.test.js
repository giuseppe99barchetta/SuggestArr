import assert from 'node:assert/strict';
import { test } from 'node:test';
import { loadTrailerUrl, trailerEndpoint, trailerTarget } from './trailer.js';

test('a sent request is looked up by its TMDb id', () => {
  const target = trailerTarget({ request_id: '10950', media_type: 'movie' });
  assert.deepEqual(target, { mediaType: 'movie', tmdbId: '10950' });
  assert.equal(trailerEndpoint(target), '/api/tmdb/trailer/movie/10950');
});

test('a workflow suggestion uses its TMDb id, not its row id', () => {
  assert.deepEqual(trailerTarget({ id: 7, tmdb_id: 1399, media_type: 'tv' }), { mediaType: 'tv', tmdbId: '1399' });
});

test('a title that requests came from is looked up by its source id', () => {
  assert.deepEqual(trailerTarget({ id: '603', media_type: 'movie' }), { mediaType: 'movie', tmdbId: '603' });
});

test('jobs and items without a usable id or media type have no trailer', () => {
  assert.equal(trailerTarget({ id: '12', media_type: 'movie', visual: { key: 'discover' } }), null);
  assert.equal(trailerTarget({ id: 'job:12', media_type: 'movie' }), null);
  assert.equal(trailerTarget({ request_id: '10950', media_type: 'person' }), null);
  assert.equal(trailerTarget({ request_id: '10950' }), null);
  assert.equal(trailerTarget(null), null);
});

test('the trailer URL comes from the API, and is null when missing, failing or not applicable', async () => {
  const asked = [];
  const http = (answer) => ({ get: async (path) => { asked.push(path); return answer(); } });
  const movie = { request_id: '10950', media_type: 'movie' };

  assert.equal(await loadTrailerUrl(http(() => ({ data: { url: 'https://www.youtube.com/watch?v=abc' } })), movie), 'https://www.youtube.com/watch?v=abc');
  assert.equal(await loadTrailerUrl(http(() => ({ data: { url: null } })), movie), null);
  assert.equal(await loadTrailerUrl(http(() => { throw new Error('offline'); }), movie), null);
  assert.equal(await loadTrailerUrl(http(() => ({ data: { url: 'x' } })), { media_type: 'movie' }), null);
  assert.deepEqual(asked, Array(3).fill('/api/tmdb/trailer/movie/10950'));
});
