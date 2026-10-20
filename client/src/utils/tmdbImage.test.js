import assert from 'node:assert/strict';
import { test } from 'node:test';
import { tmdbImage } from './tmdbImage.js';

test('full TMDb URLs change size and bare paths become full URLs', () => {
  assert.equal(tmdbImage('https://image.tmdb.org/t/p/original/a.jpg', 'w780'), 'https://image.tmdb.org/t/p/w780/a.jpg');
  assert.equal(tmdbImage('https://image.tmdb.org/t/p/w500/a.jpg', 'w300'), 'https://image.tmdb.org/t/p/w300/a.jpg');
  assert.equal(tmdbImage('/a.png', 'w300'), 'https://image.tmdb.org/t/p/w300/a.png');
  assert.equal(tmdbImage('', 'w300'), '');
  assert.equal(tmdbImage('https://cdn.example/x.jpg', 'w300'), 'https://cdn.example/x.jpg');
});
