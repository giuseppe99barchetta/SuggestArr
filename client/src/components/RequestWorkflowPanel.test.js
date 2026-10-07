import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./RequestWorkflowPanel.vue', import.meta.url), 'utf8');
const settings = readFileSync(
  new URL('./settings/SettingsRequests.vue', import.meta.url), 'utf8');

// `confirmAction(` also appears in the template, so anchor on the script-block form.
const markSeen = source.slice(source.indexOf('async markSeen('), source.indexOf('async decideOne('));

test('pending cards here offer the same already-seen action as the other UI', () => {
  assert.match(source, /aria-label="Already seen it"/);
  assert.match(source, /@click\.stop="seenMenuId = item\.id"/);
});

test('both pending UIs read their options from the shared module', () => {
  for (const file of [source, settings]) {
    assert.match(file, /from '@\/utils\/suggestionFeedback\.js'/);
    assert.match(file, /seenOptions: SEEN_OPTIONS/);
  }
});

test('rating a card does not also open the detail view', () => {
  // The <article> carries @click="openItem(item)", so every action must stop propagation.
  const actions = source.slice(source.indexOf('seenMenuId === item.id'), source.indexOf('request-card-body'));
  for (const handler of actions.match(/@click[.\w]*="(markSeen|seenMenuId)[^"]*"/g) || []) {
    assert.match(handler, /@click\.stop=/);
  }
});

test('marking a suggestion seen saves feedback before clearing the card', () => {
  const feedbackCall = markSeen.indexOf('saveSeenFeedback(');
  const rejectCall = markSeen.indexOf("this.decideOne('reject'");
  assert.ok(feedbackCall > -1, 'markSeen should save feedback');
  assert.ok(rejectCall > -1, 'markSeen should clear the pending card');
  assert.ok(feedbackCall < rejectCall, 'feedback must be saved before the request is rejected');
});

test('a failed feedback save leaves the suggestion in the queue', () => {
  assert.match(markSeen, /catch \(error\)[\s\S]*?return;/);
});

test('switching to bulk mode closes an open rating row', () => {
  assert.match(source, /bulkMode\(value\) \{[^}]*this\.seenMenuId = null;[^}]*\}/);
});
