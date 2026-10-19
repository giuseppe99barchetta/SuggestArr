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
