import test from 'node:test';
import assert from 'node:assert/strict';
import mixin from './simklPinPolling.js';

/**
 * Build a standalone `this` for the mixin.
 *
 * The mixin is a plain options object, so its methods can be exercised without
 * mounting a component as long as data and bound methods share one object.
 */
function makeContext() {
  const ctx = { ...mixin.data() };
  for (const [name, fn] of Object.entries(mixin.methods)) {
    ctx[name] = fn.bind(ctx);
  }
  return ctx;
}

const PIN_RESPONSE = {
  data: { user_code: 'ABC123', verification_uri: 'https://simkl.com/pin', interval: 5, expires_in: 900 },
};

/** Collect the arguments setError is called with. */
function errorSink() {
  const calls = [];
  const setError = (message, err) => calls.push({ message, err });
  return { calls, setError, get last() { return calls[calls.length - 1]; } };
}

function baseOptions(overrides = {}) {
  const sink = errorSink();
  return {
    sink,
    options: {
      requestCode: async () => PIN_RESPONSE,
      pollToken: async () => ({ data: { connected: false } }),
      onConnected: async () => {},
      setError: sink.setError,
      ...overrides,
    },
  };
}

test('starting a flow exposes the PIN and the verification destination', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval'] });
  const ctx = makeContext();
  const { options } = baseOptions();

  assert.equal(await ctx.startSimklPolling(options), true);
  assert.equal(ctx.simklUserCode, 'ABC123');
  assert.equal(ctx.simklVerificationUri, 'https://simkl.com/pin');
  assert.equal(ctx.isPollingSimkl, true);
  ctx.stopSimklPolling();
});

test('a response with no user code is rejected instead of polling forever', async () => {
  const ctx = makeContext();
  const { sink, options } = baseOptions({ requestCode: async () => ({ data: {} }) });

  assert.equal(await ctx.startSimklPolling(options), false);
  assert.equal(ctx.isPollingSimkl, false);
  assert.match(sink.last.message, /Invalid Simkl PIN response/);
});

test('a missing verification uri falls back to the documented destination', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval'] });
  const ctx = makeContext();
  const { options } = baseOptions({
    requestCode: async () => ({ data: { user_code: 'ABC123', interval: 5, expires_in: 900 } }),
  });

  await ctx.startSimklPolling(options);
  assert.equal(ctx.simklVerificationUri, 'https://simkl.com/pin');
  ctx.stopSimklPolling();
});

test('polling honours the interval Simkl asks for', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval'] });
  const ctx = makeContext();
  let polls = 0;
  const { options } = baseOptions({
    requestCode: async () => ({ data: { ...PIN_RESPONSE.data, interval: 10 } }),
    pollToken: async () => { polls += 1; return { data: { connected: false } }; },
  });

  await ctx.startSimklPolling(options);
  t.mock.timers.tick(9000);
  assert.equal(polls, 0, 'polled before the interval elapsed');
  t.mock.timers.tick(1000);
  assert.equal(polls, 1);
  ctx.stopSimklPolling();
});

test('a sub-five-second interval is floored', async (t) => {
  // Simkl suspends client IDs for sustained overage, so an aggressive value in
  // the response is not a reason to poll faster than the documented floor.
  t.mock.timers.enable({ apis: ['setInterval'] });
  const ctx = makeContext();
  let polls = 0;
  const { options } = baseOptions({
    requestCode: async () => ({ data: { ...PIN_RESPONSE.data, interval: 1 } }),
    pollToken: async () => { polls += 1; return { data: { connected: false } }; },
  });

  await ctx.startSimklPolling(options);
  t.mock.timers.tick(4000);
  assert.equal(polls, 0);
  t.mock.timers.tick(1000);
  assert.equal(polls, 1);
  ctx.stopSimklPolling();
});

test('a connected response stops polling and reports success once', async () => {
  const ctx = makeContext();
  let connectedCalls = 0;
  const { options } = baseOptions({
    pollToken: async () => ({ data: { connected: true, simkl_username: 'wire' } }),
    onConnected: async () => { connectedCalls += 1; },
  });

  await ctx.startSimklPolling(options);
  await ctx.pollSimklPinToken();

  assert.equal(connectedCalls, 1);
  assert.equal(ctx.isPollingSimkl, false);
  assert.equal(ctx.simklUserCode, '');
});

test('a pending response keeps the flow alive', async () => {
  const ctx = makeContext();
  const { sink, options } = baseOptions();

  await ctx.startSimklPolling(options);
  await ctx.pollSimklPinToken();

  assert.equal(ctx.isPollingSimkl, true);
  // setError(null) at start is the only call; a pending poll must not surface
  // an error to the user.
  assert.deepEqual(sink.calls.map(c => c.message), [null]);
  ctx.stopSimklPolling();
});

test('a thrown poll error stops the flow and surfaces the server message', async () => {
  const ctx = makeContext();
  const { sink, options } = baseOptions({
    pollToken: async () => {
      throw { response: { data: { message: 'The Simkl PIN expired. Request a new one.' } } };
    },
  });

  await ctx.startSimklPolling(options);
  await ctx.pollSimklPinToken();

  assert.equal(ctx.isPollingSimkl, false);
  assert.equal(sink.last.message, 'The Simkl PIN expired. Request a new one.');
});

test('the original error is handed to setError so callers can branch on a code', async () => {
  const ctx = makeContext();
  const failure = { response: { data: { message: 'rejected', code: 'client_id_failed' } } };
  const { sink, options } = baseOptions({
    requestCode: async () => { throw failure; },
  });

  await ctx.startSimklPolling(options);
  assert.equal(sink.last.err, failure);
  assert.equal(sink.last.err.response.data.code, 'client_id_failed');
});

test('an error with no message still produces readable copy', async () => {
  const ctx = makeContext();
  const { sink, options } = baseOptions({
    pollToken: async () => { throw new Error(''); },
  });

  await ctx.startSimklPolling(options);
  await ctx.pollSimklPinToken();

  assert.equal(sink.last.message, 'Simkl authorization failed. Please try again.');
});

test('the deadline ends a flow the user walked away from', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval', 'Date'] });
  const ctx = makeContext();
  let polls = 0;
  const { sink, options } = baseOptions({
    pollToken: async () => { polls += 1; return { data: { connected: false } }; },
  });

  await ctx.startSimklPolling(options);
  t.mock.timers.tick(901_000);
  await ctx.pollSimklPinToken();

  assert.equal(polls, 0, 'kept polling past the expiry');
  assert.equal(ctx.isPollingSimkl, false);
  assert.match(sink.last.message, /expired/i);
});

test('cancelling clears the pending code server-side', async () => {
  const ctx = makeContext();
  let cancelled = 0;
  const { options } = baseOptions({ cancelCode: async () => { cancelled += 1; } });

  await ctx.startSimklPolling(options);
  await ctx.cancelSimklPolling();

  assert.equal(cancelled, 1);
  assert.equal(ctx.isPollingSimkl, false);
  assert.equal(ctx.simklUserCode, '');
});

test('a failed cancel still resets the card', async () => {
  // Leaving the UI stuck in a waiting state because cleanup failed is worse
  // than the orphaned code that cleanup was trying to prevent.
  const ctx = makeContext();
  const { options } = baseOptions({
    cancelCode: async () => { throw new Error('network down'); },
  });

  await ctx.startSimklPolling(options);
  await ctx.cancelSimklPolling();

  assert.equal(ctx.isPollingSimkl, false);
  assert.equal(ctx.simklUserCode, '');
});

test('cancelling without a cancel handler is not an error', async () => {
  const ctx = makeContext();
  const { options } = baseOptions();

  await ctx.startSimklPolling(options);
  await ctx.cancelSimklPolling();

  assert.equal(ctx.isPollingSimkl, false);
});

test('starting a second flow does not leave the first one polling', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval'] });
  const ctx = makeContext();
  let polls = 0;
  const { options } = baseOptions({
    pollToken: async () => { polls += 1; return { data: { connected: false } }; },
  });

  await ctx.startSimklPolling(options);
  await ctx.startSimklPolling(options);
  t.mock.timers.tick(5000);

  assert.equal(polls, 1, 'both timers fired');
  ctx.stopSimklPolling();
});

test('a poll after the flow was stopped is a no-op', async () => {
  const ctx = makeContext();
  let polls = 0;
  const { options } = baseOptions({
    pollToken: async () => { polls += 1; return { data: { connected: false } }; },
  });

  await ctx.startSimklPolling(options);
  ctx.stopSimklPolling();
  await ctx.pollSimklPinToken();

  assert.equal(polls, 0);
});
