import test from 'node:test';
import assert from 'node:assert/strict';

import { previewLoaderMethods } from './simklPreview.js';

/** A stand-in for the component: preview state plus a controllable fetch. */
function makeHost() {
  const pending = [];
  const host = {
    previewGeneration: 0,
    previewTargetKey: 'plex:1',
    previewItems: [],
    previewLoading: false,
    previewError: null,
    previewFetched: false,
    clientIdError: false,
    get previewTargetUser() {
      return this.previewTargetKey ? { provider: 'plex', external_user_id: this.previewTargetKey.split(':')[1] } : null;
    },
    rowKey: user => `${user.provider}:${user.external_user_id}`,
    fetchPreview: () => new Promise((resolve, reject) => pending.push({ resolve, reject })),
    ...previewLoaderMethods,
  };
  return { host, pending };
}

test('a reset during an in-flight preview clears the spinner and drops the late response', async () => {
  const { host, pending } = makeHost();
  const load = host.loadPreviewItems();
  assert.equal(host.previewLoading, true);

  host.resetPreview();
  assert.equal(host.previewLoading, false);

  pending[0].resolve({ data: { items: [{ title: 'Stale' }] } });
  await load;
  assert.equal(host.previewLoading, false);
  assert.deepEqual(host.previewItems, []);
  assert.equal(host.previewFetched, false);
});

test('a response for a previous target is ignored once the target changes', async () => {
  const { host, pending } = makeHost();
  const first = host.loadPreviewItems();
  host.previewTargetKey = 'plex:2';
  const second = host.loadPreviewItems();

  pending[0].resolve({ data: { items: [{ title: 'From user 1' }] } });
  await first;
  assert.equal(host.previewLoading, true);

  pending[1].resolve({ data: { items: [{ title: 'From user 2' }] } });
  await second;
  assert.equal(host.previewLoading, false);
  assert.deepEqual(host.previewItems, [{ title: 'From user 2' }]);
});

test('a rejected client ID raises the install-level banner, not a preview error', async () => {
  const { host, pending } = makeHost();
  const load = host.loadPreviewItems();
  pending[0].reject({ response: { data: { code: 'client_id_failed' } } });
  await load;
  assert.equal(host.clientIdError, true);
  assert.equal(host.previewError, null);
  assert.equal(host.previewLoading, false);
});
