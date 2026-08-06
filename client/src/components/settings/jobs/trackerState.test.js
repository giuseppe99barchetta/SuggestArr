import test from 'node:test';
import assert from 'node:assert/strict';
import { trackerState, trackerWarning } from './trackerState.js';

const linked = { external_user_id: '1', simkl: { connected: true } };
const unlinked = { external_user_id: '2', simkl: {} };

function state(overrides = {}) {
  return trackerState({
    configured: true,
    users: [],
    selfConnected: false,
    key: 'simkl',
    userMode: 'all',
    selectedIds: [],
    ...overrides,
  });
}

test('an unconfigured tracker reports the missing credentials, not a missing link', () => {
  assert.equal(state({ configured: false, users: [linked] }), 'unconfigured');
});

test('a monitored user with a link makes the tracker usable', () => {
  assert.equal(state({ users: [linked] }), 'usable');
});

test('monitoring everyone ignores users who have not linked', () => {
  assert.equal(state({ users: [unlinked, linked] }), 'usable');
  assert.equal(state({ users: [unlinked] }), 'none-linked');
});

test('nothing linked anywhere reads as none-linked', () => {
  assert.equal(state({ users: [unlinked], selfConnected: false }), 'none-linked');
});

test('an account linked outside the monitored set is reported as such', () => {
  // The regression this guards: an admin links their own account from
  // Profile, but that media account was never chosen in Services, so the
  // admin list cannot see it and the UI used to claim nothing was linked.
  assert.equal(state({ users: [unlinked], selfConnected: true }), 'linked-not-monitored');
});

test('an empty monitored list still surfaces the caller own link', () => {
  assert.equal(state({ users: [], selfConnected: true }), 'linked-not-monitored');
  assert.equal(state({ users: [], selfConnected: false }), 'none-linked');
});

test('selecting specific users only counts those users', () => {
  const users = [linked, { external_user_id: '2', simkl: { connected: true } }];
  assert.equal(
    state({ users, userMode: 'specific', selectedIds: ['2'] }), 'usable',
  );
  assert.equal(
    state({ users: [linked], userMode: 'specific', selectedIds: ['2'] }),
    'linked-not-monitored',
  );
});

test('specific mode with nothing selected cannot be usable', () => {
  assert.equal(
    state({ users: [linked], userMode: 'specific', selectedIds: [] }),
    'linked-not-monitored',
  );
});

test('each tracker key is read independently', () => {
  const traktOnly = [{ external_user_id: '1', trakt: { connected: true }, simkl: {} }];
  assert.equal(state({ users: traktOnly, key: 'trakt' }), 'usable');
  assert.equal(state({ users: traktOnly, key: 'simkl' }), 'none-linked');
});

test('a usable tracker shows no warning', () => {
  assert.equal(trackerWarning('usable', 'Simkl', 'Client ID'), null);
});

test('the none-linked warning points at Profile, where linking actually happens', () => {
  const warning = trackerWarning('none-linked', 'Simkl', 'Client ID');
  assert.match(warning, /Profile > Simkl Account/);
  assert.doesNotMatch(warning, /Services/);
});

test('the unconfigured warning names the credentials that tracker needs', () => {
  assert.match(
    trackerWarning('unconfigured', 'Simkl', 'Client ID'),
    /set the Client ID in Services/,
  );
  assert.match(
    trackerWarning('unconfigured', 'Trakt', 'Client ID / Secret'),
    /set the Client ID \/ Secret in Services/,
  );
});

test('the linked-not-monitored warning does not tell the user to link again', () => {
  const warning = trackerWarning('linked-not-monitored', 'Simkl', 'Client ID');
  assert.match(warning, /is linked/);
  assert.match(warning, /this job monitors/);
});
