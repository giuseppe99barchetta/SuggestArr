import test from 'node:test';
import assert from 'node:assert/strict';

import { formatWatchedDate } from './simklPreview.js';

test('a real watch date is rendered', () => {
  assert.equal(
    formatWatchedDate(1778793765),
    new Date(1778793765 * 1000).toLocaleDateString(),
  );
});

test('a missing watch date renders as nothing, not as 1970', () => {
  // The sync caches an unparseable or absent timestamp as 0, which Date
  // happily turns into a valid-looking 1 January 1970.
  assert.equal(formatWatchedDate(0), '');
});

test('null and undefined timestamps render as nothing', () => {
  assert.equal(formatWatchedDate(null), '');
  assert.equal(formatWatchedDate(undefined), '');
});

test('a non-numeric timestamp renders as nothing', () => {
  assert.equal(formatWatchedDate('not-a-date'), '');
});

test('a numeric string timestamp is accepted', () => {
  assert.equal(
    formatWatchedDate('1778793765'),
    new Date(1778793765 * 1000).toLocaleDateString(),
  );
});
