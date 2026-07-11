import test from 'node:test';
import assert from 'node:assert/strict';
import axios from 'axios';
import { fetchRandomMovieImages } from './tmdbApi.js';

test('shares the TMDb catalog for two hours and deduplicates refreshes', async () => {
  const originalGet = axios.get;
  const originalNow = Date.now;
  let now = 1;
  let calls = 0;

  Date.now = () => now;
  axios.get = async () => {
    calls += 1;
    return { data: { results: [{ backdrop_path: `/image-${calls}.jpg` }] } };
  };

  try {
    const [first, concurrent] = await Promise.all([
      fetchRandomMovieImages(),
      fetchRandomMovieImages(),
    ]);
    assert.deepEqual(first, concurrent);
    assert.equal(calls, 1);

    now += 2 * 60 * 60 * 1000 - 1;
    await fetchRandomMovieImages();
    assert.equal(calls, 1);

    now += 1;
    await fetchRandomMovieImages();
    assert.equal(calls, 2);

    now += 2 * 60 * 60 * 1000;
    axios.get = async () => { throw { response: { status: 400 } }; };
    assert.equal(await fetchRandomMovieImages(), null);
  } finally {
    axios.get = originalGet;
    Date.now = originalNow;
  }
});
