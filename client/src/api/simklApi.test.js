import test from 'node:test';
import assert from 'node:assert/strict';
import axios from 'axios';
import {
  listSimklJobUsers,
  startMediaUserSimklPinCode,
  pollMediaUserSimklPinToken,
  cancelMediaUserSimklPin,
  unlinkMediaUserSimkl,
  previewMediaUserSimklRecent,
  pollMySimklPinToken,
  updateSimklSource,
} from './api.js';

/** Capture what the wrappers put on the wire without making a request. */
function withRecordedRequests(run, response = {}) {
  const originalAdapter = axios.defaults.adapter;
  const requests = [];
  axios.defaults.adapter = async (config) => {
    requests.push(config);
    return {
      data: typeof response === 'function' ? response(config) : response,
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    };
  };
  return run(requests).finally(() => {
    axios.defaults.adapter = originalAdapter;
  });
}

test('Simkl job users are scoped by role', async () => {
  await withRecordedRequests(
    async (requests) => {
      const mediaUser = { external_user_id: 'mine', simkl: { connected: true } };
      assert.deepEqual(await listSimklJobUsers('user'), [mediaUser]);
      assert.equal((await listSimklJobUsers('admin')).length, 1);
      assert.deepEqual(
        requests.map(r => r.url),
        ['/api/simkl/me', '/api/simkl/media-users'],
      );
    },
    (config) => {
      const mediaUser = { external_user_id: 'mine', simkl: { connected: true } };
      return config.url === '/api/simkl/me' ? { media_user: mediaUser } : { media_users: [mediaUser] };
    },
  );
});

test('an unlinked user yields an empty job-user list rather than a null entry', async () => {
  await withRecordedRequests(async () => {
    assert.deepEqual(await listSimklJobUsers('user'), []);
  }, {});
});

test('the PIN request sends no credentials', async () => {
  // The server reads the client ID from config; a body carrying Simkl
  // credentials would let a caller overwrite the install's integration config.
  await withRecordedRequests(async (requests) => {
    await startMediaUserSimklPinCode('jellyfin', 'jf-1');
    assert.equal(requests[0].url, '/api/simkl/media-users/jellyfin/jf-1/pin/code');
    assert.equal(requests[0].method, 'post');
    assert.equal(requests[0].data, undefined);
  });
});

test('the poll sends no PIN, since the server holds the one it issued', async () => {
  await withRecordedRequests(async (requests) => {
    await pollMediaUserSimklPinToken('plex', 'px-9');
    assert.equal(requests[0].url, '/api/simkl/media-users/plex/px-9/pin/token');
    assert.equal(requests[0].data, undefined);
  });
});

test('the self-service poll targets the me route', async () => {
  await withRecordedRequests(async (requests) => {
    await pollMySimklPinToken();
    assert.equal(requests[0].url, '/api/simkl/me/pin/token');
    assert.equal(requests[0].data, undefined);
  });
});

test('cancelling a PIN deletes it rather than unlinking the account', async () => {
  await withRecordedRequests(async (requests) => {
    await cancelMediaUserSimklPin('jellyfin', 'jf-1');
    await unlinkMediaUserSimkl('jellyfin', 'jf-1');
    assert.deepEqual(
      requests.map(r => `${r.method} ${r.url}`),
      [
        'delete /api/simkl/media-users/jellyfin/jf-1/pin',
        'delete /api/simkl/media-users/jellyfin/jf-1',
      ],
    );
  });
});

test('external user ids are encoded into the path', async () => {
  // Plex ids and Jellyfin usernames can contain characters that would
  // otherwise change which route is hit.
  await withRecordedRequests(async (requests) => {
    await previewMediaUserSimklRecent('plex', 'user/with?slash');
    assert.equal(
      requests[0].url,
      '/api/simkl/media-users/plex/user%2Fwith%3Fslash/recent',
    );
  });
});

test('the recent preview passes the limit as a query param', async () => {
  await withRecordedRequests(async (requests) => {
    await previewMediaUserSimklRecent('jellyfin', 'jf-1', 25);
    assert.deepEqual(requests[0].params, { limit: 25 });
  });
});

test('source flags are sent as the request body', async () => {
  await withRecordedRequests(async (requests) => {
    await updateSimklSource('jellyfin', 'jf-1', { use_as_seed: false });
    assert.equal(requests[0].method, 'put');
    assert.deepEqual(JSON.parse(requests[0].data), { use_as_seed: false });
  });
});
