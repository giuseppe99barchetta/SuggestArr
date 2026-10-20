import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mediaStatus } from './mediaStatus.js';

test('watched wins over any Seer status', () => {
  assert.equal(mediaStatus('2030-01-02', 'processing').key, 'watched');
});

test('downloading, partly and fully available each get a badge', () => {
  assert.equal(mediaStatus(null, 'processing').label, 'Downloading');
  assert.equal(mediaStatus(null, 'partial').label, 'Partly available');
  assert.equal(mediaStatus(null, 'available').label, 'Available to watch');
});

test('requested, pending, not yet synced or unknown titles read as requested', () => {
  for (const status of ['requested', 'pending', null, undefined, 'something-new']) {
    assert.equal(mediaStatus(null, status).key, 'requested');
  }
});
