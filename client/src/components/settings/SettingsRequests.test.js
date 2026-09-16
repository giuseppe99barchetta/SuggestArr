import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./SettingsRequests.vue', import.meta.url), 'utf8');

test('pending cards offer an already-seen action beside approve and reject', () => {
  assert.match(source, /aria-label="Already seen it"/);
  assert.match(source, /@click="seenMenuId = request\.id"/);
});

test('the rating options come from the shared module, not a local copy', () => {
  // Both pending UIs must offer the same actions; duplicating the list is how they drift.
  assert.match(source, /import \{ SEEN_OPTIONS, saveSeenFeedback \} from '@\/utils\/suggestionFeedback\.js'/);
  assert.match(source, /seenOptions: SEEN_OPTIONS/);
});

test('marking a suggestion seen saves feedback before clearing the card', () => {
  const method = source.slice(source.indexOf('async markSeen('), source.indexOf('async decidePending('));
  const feedbackCall = method.indexOf('saveSeenFeedback(');
  const rejectCall = method.indexOf("this.decidePending('reject'");
  assert.ok(feedbackCall > -1, 'markSeen should save feedback');
  assert.ok(rejectCall > -1, 'markSeen should clear the pending card');
  assert.ok(feedbackCall < rejectCall, 'feedback must be saved before the request is rejected');
});

test('a failed feedback save leaves the suggestion in the queue', () => {
  const method = source.slice(source.indexOf('async markSeen('), source.indexOf('async decidePending('));
  assert.match(method, /catch \(error\)[\s\S]*?return;/);
});
