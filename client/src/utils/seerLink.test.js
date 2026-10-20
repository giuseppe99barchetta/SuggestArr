import assert from 'node:assert/strict';
import { test } from 'node:test';
import { loadSeerWebUrl, seerTitleUrl } from './seerLink.js';

test('a title page in Seer is built from its base address and TMDb id', () => {
  assert.equal(seerTitleUrl('http://192.168.1.5:5055', { request_id: '155', media_type: 'movie' }), 'http://192.168.1.5:5055/movie/155');
  assert.equal(seerTitleUrl('https://seer.example', { tmdb_id: 1399, media_type: 'tv' }), 'https://seer.example/tv/1399');
  assert.equal(seerTitleUrl(null, { request_id: '155', media_type: 'movie' }), null);
  assert.equal(seerTitleUrl('https://seer.example', { media_type: 'movie' }), null);
});

test('the address is asked once, and asked again after a failure', async () => {
  let calls = 0;
  const failing = { get: async () => { calls += 1; throw new Error('offline'); } };
  assert.equal(await loadSeerWebUrl(failing), null);
  const working = { get: async () => { calls += 1; return { data: { url: 'https://seer.example' } }; } };
  assert.equal(await loadSeerWebUrl(working), 'https://seer.example');
  assert.equal(await loadSeerWebUrl(working), 'https://seer.example');
  assert.equal(calls, 2);
});
