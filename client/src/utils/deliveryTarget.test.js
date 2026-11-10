import { test } from 'node:test';
import assert from 'node:assert/strict';
import { approvalNotice, deliveryCounts, deliveryLabel } from './deliveryTarget.js';

test('rows without a backend (queued before the field existed) belong to Seer', () => {
  assert.deepEqual(deliveryCounts([{}, { backend: 'seer' }, { backend: 'arr' }, null]), { seer: 3, arr: 1 });
  assert.equal(deliveryLabel([{}]), 'Seer');
  assert.equal(deliveryLabel([]), 'Seer');
});

test('the label names direct delivery and breaks a mixed batch down by backend', () => {
  assert.equal(deliveryLabel([{ backend: 'arr' }, { backend: 'arr' }]), 'Radarr/Sonarr');
  assert.equal(deliveryLabel([{ backend: 'seer' }, { backend: 'arr' }, { backend: 'seer' }]), 'Seer (2) and Radarr/Sonarr (1)');
});

test('the approval notice reports ignored profile overrides', () => {
  assert.equal(approvalNotice([{ backend: 'seer' }]), 'Queued for Seer');
  assert.match(approvalNotice([{ backend: 'arr' }], 1), /ignored for 1 Radarr\/Sonarr item,/);
  assert.match(approvalNotice([{ backend: 'arr' }, { backend: 'arr' }], 2), /2 Radarr\/Sonarr items/);
});
