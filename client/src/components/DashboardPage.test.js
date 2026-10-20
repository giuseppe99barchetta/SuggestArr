import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./DashboardPage.vue', import.meta.url), 'utf8');
const home = readFileSync(new URL('./HomePage.vue', import.meta.url), 'utf8');
const panel = readFileSync(new URL('./RequestWorkflowPanel.vue', import.meta.url), 'utf8');

test('the request badge recounts when a page reports a change', () => {
  assert.match(source, /window\.addEventListener\(REQUESTS_CHANGED, this\.loadRequestCount\)/);
  assert.match(source, /window\.removeEventListener\(REQUESTS_CHANGED, this\.loadRequestCount\)/);
});

test('the request badge recounts when switching pages', () => {
  assert.match(source, /activeTab\(\) \{\s*this\.loadRequestCount\(\);\s*\}/);
});

test('every approval decision announces the change', () => {
  for (const file of [home, panel]) {
    for (const post of file.match(/await axios\.post\(`\/api\/automation\/requests\/workflow\/\$\{action\}`[^\n]*\n[^\n]*/g)) {
      assert.match(post, /notifyRequestsChanged\(\);/);
    }
  }
});

test('saving a section never copies the redacted-secret sentinel into the live config', () => {
  const save = source.slice(source.indexOf('async saveSection('), source.indexOf('async saveSection(') + 900);
  assert.doesNotMatch(save, /Object\.assign\(this\.config, data\)/);
  assert.match(save, /if \(value !== '\*\*\*'\) this\.config\[key\] = value;/);
});

test('only the newest badge count may write the badge', () => {
  // An approval event and a tab switch can start overlapping counts; an older,
  // slower answer must not overwrite a newer one.
  const method = source.slice(source.indexOf('async loadRequestCount()'), source.indexOf('async showChangelog()'));
  assert.match(method, /const call = \+\+this\.requestCountCall;/);
  const writes = method.match(/this\.requestCount = [^;]+;/g);
  assert.ok(writes.length >= 2);
  for (const write of writes) {
    assert.match(method, new RegExp(`if \\(call === this\\.requestCountCall\\) ${write.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`));
  }
  assert.match(source, /requestCountCall: 0,/);
});
