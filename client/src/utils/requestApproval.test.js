import assert from 'node:assert/strict';
import { test } from 'node:test';

import { approvalEnabled, jobRequiresApproval } from './requestApproval.js';

test('a manual job always waits for approval, an automatic one never does', () => {
  assert.equal(jobRequiresApproval({ delivery_mode: 'manual' }, false), true);
  assert.equal(jobRequiresApproval({ delivery_mode: 'automatic' }, true), false);
});

test('an inheriting job follows the global setting, including string values', () => {
  assert.equal(jobRequiresApproval({ delivery_mode: 'inherit' }, true), true);
  assert.equal(jobRequiresApproval({}, false), false);
  assert.equal(jobRequiresApproval({}, 'true'), true);
  assert.equal(jobRequiresApproval({}, 'false'), false);
  assert.equal(jobRequiresApproval({}, undefined), false);
});

test('approval is enabled when any job needs it', () => {
  assert.equal(approvalEnabled({ jobs: [{ delivery_mode: 'inherit' }], request_approval_default: true }), true);
  assert.equal(approvalEnabled({ jobs: [{ delivery_mode: 'automatic' }], request_approval_default: true }), false);
  assert.equal(approvalEnabled({ jobs: [], request_approval_default: true }), false);
  assert.equal(approvalEnabled(null), false);
});
