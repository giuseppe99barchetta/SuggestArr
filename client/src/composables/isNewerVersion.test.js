import test from 'node:test';
import assert from 'node:assert/strict';
import { isNewerVersion } from './isNewerVersion.js';

test('compares numeric parts, not text', () => {
  assert.equal(isNewerVersion('3.10.0', '3.9.0'), true);
  assert.equal(isNewerVersion('3.9.0', '3.10.0'), false);
});

test('equal versions are not newer, the v prefix and suffix are ignored', () => {
  assert.equal(isNewerVersion('v3.4.0', '3.4.0'), false);
  assert.equal(isNewerVersion('v3.5.0', 'v3.4.0-nightly'), true);
  assert.equal(isNewerVersion('3.4', '3.4.0'), false);
});
