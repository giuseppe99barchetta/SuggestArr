import assert from 'node:assert/strict';
import { test } from 'node:test';
import { containRect, fanLayout, posterUrl, recapCaption, recapShareTargets } from './recapCanvas.js';

test('poster paths are restricted to HTTPS TMDb image URLs', () => {
  assert.equal(posterUrl('/poster.jpg'), 'https://image.tmdb.org/t/p/w342/poster.jpg');
  assert.equal(posterUrl('https://image.tmdb.org/t/p/w500/poster.jpg'), 'https://image.tmdb.org/t/p/w500/poster.jpg');
  for (const path of ['http://image.tmdb.org/t/p/a.jpg', 'https://example.com/a.jpg', 'data:image/png;base64,a', 'javascript:alert(1)', '', null]) {
    assert.equal(posterUrl(path), null);
  }
});

test('captions contain aggregate progress and project attribution without private fields', () => {
  const caption = recapCaption({ total: 1234, movies: 1000, tv: 234, username: 'private-user', server: 'private-server' });
  assert.match(caption, /1,234 titles/);
  assert.match(caption, /1,000 movies and 234 TV series/);
  assert.match(caption, /https:\/\/github.com\/giuseppe99barchetta\/SuggestArr/);
  assert.doesNotMatch(caption, /private-/);
});

test('wide logo keeps its source aspect ratio inside the header', () => {
  const rect = containRect(512, 281, 72, 70, 106, 60);
  assert.equal(rect.width / rect.height, 512 / 281);
  assert.ok(rect.width <= 106 && rect.height <= 60);
});

test('one to four fan cards have distinct positions without changing portrait dimensions', () => {
  for (const count of [1, 2, 3, 4]) {
    const cards = fanLayout(count);
    assert.equal(cards.length, count);
    assert.equal(new Set(cards.map(card => card.index)).size, count);
    assert.equal(cards.at(-1).index, 0, 'the top-rated pick is drawn in front');
    assert.ok(cards.every(card => Math.abs(card.angle) <= 17));
  }
});

test('social shortcuts put Reddit first and encode only public aggregate text', () => {
  const targets = recapShareTargets({ total: 1234, movies: 1000, tv: 234, username: 'private-user' });
  assert.deepEqual(targets.map(target => target.id), ['reddit', 'discord', 'x', 'bluesky']);
  assert.equal(new URL(targets[0].url).searchParams.get('type'), 'IMAGE');
  assert.match(new URL(targets[0].url).searchParams.get('title'), /1,234/);
  assert.ok(targets.every(target => target.url.startsWith('https:') && !target.url.includes('private-user')));
  assert.match(new URL(targets[3].url).searchParams.get('text'), /github.com/);
});
