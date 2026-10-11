import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatDate, timeFromNow } from './dateUtils.js';

const now = new Date('2026-10-09T12:00:00Z');
const at = minutes => new Date(now.getTime() + minutes * 60000);

test('timeFromNow reads both directions', () => {
  assert.equal(timeFromNow(at(134), now), 'in 2h 14m');
  assert.equal(timeFromNow(at(-5), now), '5m ago');
  assert.equal(timeFromNow(at(-120), now), '2h ago');
  assert.equal(timeFromNow(at(-125), now), '2h ago');
  assert.equal(timeFromNow(at(3 * 24 * 60), now), 'in 3 days');
  assert.equal(timeFromNow(at(-24 * 60), now), '1 day ago');
  assert.equal(timeFromNow(at(0), now), 'just now');
  assert.equal(timeFromNow(null, now), '');
  assert.equal(timeFromNow('nope', now), '');
});

test('formatDate says "1 week ago", not "1 weeks ago"', () => {
  const eightDaysAgo = new Date(Date.now() - 8 * 24 * 3600 * 1000).toISOString();
  assert.equal(formatDate(eightDaysAgo), '1 week ago');
});
