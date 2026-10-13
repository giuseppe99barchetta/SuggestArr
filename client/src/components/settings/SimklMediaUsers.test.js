import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('./SimklMediaUsers.vue', import.meta.url), 'utf8');

test('preview results are guarded against stale targets', () => {
  assert.match(source, /previewGeneration: 0/);
  assert.match(source, /const generation = \+\+this\.previewGeneration/);
  assert.match(source, /targetKey !== this\.previewTargetKey/);
  assert.match(source, /if \(generation === this\.previewGeneration\) this\.previewLoading = false/);
});
