import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseLogs } from './logs.js';

test('log lines split into fields, keeping " - " inside the message', () => {
  const [log] = parseLogs(['2026-10-11 12:00:01 - jobs.runner - ERROR - Seer said - no']);
  assert.deepEqual(log, { dateTime: '2026-10-11 12:00:01', time: '12:00:01', tag: 'jobs.runner', severity: 'ERROR', message: 'Seer said - no' });
});

test('malformed and empty-message lines are dropped', () => {
  assert.deepEqual(parseLogs(['garbage', 'a - b - INFO - ', '']), []);
});
