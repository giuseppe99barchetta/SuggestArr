import test from 'node:test';
import assert from 'node:assert/strict';
import axios from 'axios';
import { useAuth } from './useAuth.js';

// The composable keeps the session in module-level state and reads localStorage.
const storage = new Map();
globalThis.localStorage = {
  getItem: (key) => (storage.has(key) ? storage.get(key) : null),
  setItem: (key, value) => storage.set(key, String(value)),
  removeItem: (key) => storage.delete(key),
};

function jwt(name, expiresInSeconds = 600) {
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString('base64url');
  return `${encode({ alg: 'none' })}.${encode({ sub: '1', username: name, role: 'admin', exp: Math.floor(Date.now() / 1000) + expiresInSeconds })}.sig`;
}

const auth = useAuth();
auth.setupInterceptors();
const originalAdapter = axios.defaults.adapter;

function respond(config, status, data = {}) {
  const response = { data, status, statusText: String(status), headers: {}, config };
  if (status >= 200 && status < 300) return Promise.resolve(response);
  return Promise.reject(Object.assign(new Error(`HTTP ${status}`), { config, response, isAxiosError: true }));
}

function authorization(config) {
  return config.headers.Authorization || config.headers.get?.('Authorization');
}

async function signIn(token) {
  axios.defaults.adapter = (config) => respond(config, 200, { access_token: token });
  await auth.login('admin', 'secret'); // also clears the "refresh failed" latch
}

test('two requests sent with the same expired token refresh the session once and both succeed', async () => {
  await signIn(jwt('old'));
  const stale = `Bearer ${auth.accessToken.value}`;
  const fresh = jwt('fresh');
  let refreshes = 0;
  axios.defaults.adapter = async (config) => {
    if (config.url === '/api/auth/refresh') {
      refreshes += 1;
      return respond(config, 200, { access_token: fresh });
    }
    if (authorization(config) === stale) {
      // The second request's rejection arrives only after the first one's refresh has finished.
      if (config.url === '/api/b') await new Promise((resolve) => setTimeout(resolve, 80));
      return respond(config, 401);
    }
    return respond(config, 200, { ok: config.url });
  };
  const [a, b] = await Promise.all([axios.get('/api/a'), axios.get('/api/b')]);
  assert.equal(a.data.ok, '/api/a');
  assert.equal(b.data.ok, '/api/b');
  assert.equal(refreshes, 1);
  axios.defaults.adapter = originalAdapter;
});

test('a 401 on a token that has not expired still ends the session cleanly when refreshing is refused', async () => {
  await signIn(jwt('alice', 3600)); // far from expiry: the account was deactivated server-side
  let refreshCalls = 0;
  axios.defaults.adapter = async (config) => {
    if (config.url === '/api/auth/refresh') {
      refreshCalls += 1;
      return respond(config, 401);
    }
    if (config.url === '/api/auth/logout') return respond(config, 200);
    return respond(config, 401);
  };
  await assert.rejects(axios.get('/api/data'));
  assert.equal(refreshCalls, 1);
  assert.equal(auth.accessToken.value, null);
  axios.defaults.adapter = originalAdapter;
});

test('a refresh that fails because the backend is restarting keeps the session and recovers on the next request', async () => {
  await signIn(jwt('bob', -60)); // expired token, so the first call gets a 401
  const expired = `Bearer ${auth.accessToken.value}`;
  const fresh = jwt('bob-again');
  let backendUp = false;
  axios.defaults.adapter = async (config) => {
    if (config.url === '/api/auth/refresh') return backendUp ? respond(config, 200, { access_token: fresh }) : respond(config, 502);
    return authorization(config) === expired ? respond(config, 401) : respond(config, 200, { ok: true });
  };
  await assert.rejects(axios.get('/api/data'));          // backend down: this request fails...
  assert.notEqual(auth.accessToken.value, null);         // ...but the user stays signed in
  backendUp = true;
  const retried = await axios.get('/api/data');          // next request refreshes and succeeds
  assert.equal(retried.data.ok, true);
  axios.defaults.adapter = originalAdapter;
});

test('a refresh the server refuses stops further attempts until the next login', async () => {
  await signIn(jwt('carol'));
  axios.defaults.adapter = (config) => respond(config, 401);
  assert.equal(await auth.tryRefresh(), false);
  let calls = 0;
  axios.defaults.adapter = (config) => { calls += 1; return respond(config, 200, { access_token: jwt('x') }); };
  assert.equal(await auth.tryRefresh(), false);
  assert.equal(calls, 0);
  axios.defaults.adapter = originalAdapter;
});

test('logging out removes the legacy cached configuration', async () => {
  storage.set('suggestarr_config', JSON.stringify({ TMDB_API_KEY: 'secret' }));
  axios.defaults.adapter = (config) => respond(config, 200);
  await auth.logout();
  assert.equal(storage.has('suggestarr_config'), false);
  axios.defaults.adapter = originalAdapter;
});
