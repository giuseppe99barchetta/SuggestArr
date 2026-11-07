import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./ToggleTrack.vue', import.meta.url), 'utf8');

test('the track is decorative and moves only with transform', () => {
  assert.match(source, /aria-hidden="true"/);
  assert.match(source, /transition-transform/);
  assert.doesNotMatch(source, /transition-all|left-\[21px\]/);
});

test('every settings switch uses ToggleTrack, none hand-draws the track', () => {
  for (const file of ['../configWizard/ContentFilterSettings.vue', '../settings/AiSearchPage.vue', '../settings/SettingsAdvanced.vue', '../settings/SettingsCleanup.vue', '../settings/UserManagement.vue']) {
    const vue = readFileSync(new URL(file, import.meta.url), 'utf8');
    assert.match(vue, /<ToggleTrack :on=/, file);
    assert.doesNotMatch(vue, /h-\[22px\] w-10/, file);
  }
});
