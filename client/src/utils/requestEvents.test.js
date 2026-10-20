import assert from 'node:assert/strict';
import { test } from 'node:test';

import { REQUESTS_CHANGED, notifyRequestsChanged } from './requestEvents.js';

test('notifying fires the shared window event', () => {
  const fired = [];
  const target = new EventTarget();
  globalThis.window = target;
  target.addEventListener(REQUESTS_CHANGED, event => fired.push(event.type));

  notifyRequestsChanged();

  assert.deepEqual(fired, [REQUESTS_CHANGED]);
  delete globalThis.window;
});
