import test from 'node:test';
import assert from 'node:assert/strict';
import { yearRecapSeason } from './yearRecapSeason.js';

test('Home invitation runs from December 15 through January 31 inclusive', () => {
  assert.deepEqual(yearRecapSeason(new Date(2026, 11, 14, 23, 59, 59)), { available: false, year: 2026 });
  assert.deepEqual(yearRecapSeason(new Date(2026, 11, 15)), { available: true, year: 2026 });
  assert.deepEqual(yearRecapSeason(new Date(2026, 11, 31, 23, 59, 59)), { available: true, year: 2026 });
  assert.deepEqual(yearRecapSeason(new Date(2027, 0, 1)), { available: true, year: 2026 });
  assert.deepEqual(yearRecapSeason(new Date(2027, 0, 31, 23, 59, 59)), { available: true, year: 2026 });
  assert.deepEqual(yearRecapSeason(new Date(2027, 1, 1)), { available: false, year: 2027 });
  for (let month = 1; month < 11; month += 1) {
    assert.equal(yearRecapSeason(new Date(2026, month, 15)).available, false);
  }
});
