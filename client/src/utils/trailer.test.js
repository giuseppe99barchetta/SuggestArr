import assert from 'node:assert/strict';
import { test } from 'node:test';
import { loadTitleDetails, loadTrailerUrl, trailerEmbedUrl, trailerEndpoint, trailerTarget } from './trailer.js';

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

test('a YouTube trailer plays in place through the privacy-enhanced embed', () => {
  assert.equal(trailerEmbedUrl('https://www.youtube.com/watch?v=abc123XYZ_-'), 'https://www.youtube-nocookie.com/embed/abc123XYZ_-?autoplay=1&rel=0');
  assert.equal(trailerEmbedUrl('https://youtu.be/abc123'), 'https://www.youtube-nocookie.com/embed/abc123?autoplay=1&rel=0');
  assert.equal(trailerEmbedUrl('https://www.youtube.com/watch?v=a"b<c>d'), null);
  assert.equal(trailerEmbedUrl('https://www.youtube.com/'), null);
  assert.equal(trailerEmbedUrl('not a url'), null);
});

test('title details come from the details API, and are null when failing or not applicable', async () => {
  const asked = [];
  const http = (answer) => ({ get: async (path) => { asked.push(path); return answer(); } });
  const show = { tmdb_id: 1399, media_type: 'tv' };

  assert.deepEqual(await loadTitleDetails(http(() => ({ data: { genres: ['Drama'] } })), show), { genres: ['Drama'] });
  assert.equal(await loadTitleDetails(http(() => { throw new Error('offline'); }), show), null);
  assert.equal(await loadTitleDetails(http(() => ({ data: {} })), { media_type: 'tv' }), null);
  assert.deepEqual(asked, Array(2).fill('/api/tmdb/details/tv/1399'));
});
