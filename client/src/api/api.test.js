import test from 'node:test';
import assert from 'node:assert/strict';
import axios from 'axios';
import { listTraktJobUsers } from './api.js';

test('Trakt job users are scoped by role', async () => {
  const originalAdapter = axios.defaults.adapter;
  const requested = [];
  axios.defaults.adapter = async (config) => {
    requested.push(config.url);
    const mediaUser = { external_user_id: 'mine', trakt: { connected: true } };
    return {
      data: config.url === '/api/trakt/me' ? { media_user: mediaUser } : { media_users: [mediaUser] },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    };
  };

  try {
    assert.deepEqual(await listTraktJobUsers('user'), [
      { external_user_id: 'mine', trakt: { connected: true } },
    ]);
    assert.equal((await listTraktJobUsers('admin')).length, 1);
    assert.deepEqual(requested, ['/api/trakt/me', '/api/trakt/media-users']);
  } finally {
    axios.defaults.adapter = originalAdapter;
  }
});
