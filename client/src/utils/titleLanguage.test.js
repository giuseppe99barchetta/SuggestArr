import assert from 'node:assert/strict';
import { test } from 'node:test';

import { languageOptions, languagePayload } from './titleLanguage.js';

test('the default comes first, then the languages by name', () => {
  const options = languageOptions([
    { iso_639_1: 'de', english_name: 'German', name: 'Deutsch' },
    { iso_639_1: 'en', english_name: 'English', name: 'English' },
    { iso_639_1: 'fr', english_name: 'French', name: 'Français' },
  ]);
  assert.deepEqual(options, [
    { value: '', label: 'Server default' },
    { value: 'en', label: 'English' },
    { value: 'fr', label: 'French (Français)' },
    { value: 'de', label: 'German (Deutsch)' },
  ]);
});

test('entries TMDb returns without a usable code are left out', () => {
  const options = languageOptions([{ iso_639_1: 'xx-long', english_name: 'Broken' }, null, { english_name: 'No code' }]);
  assert.deepEqual(options, [{ value: '', label: 'Server default' }]);
  assert.deepEqual(languageOptions(undefined), [{ value: '', label: 'Server default' }]);
});

test('choosing the default sends null, a language sends its code', () => {
  assert.deepEqual(languagePayload(''), { language: null });
  assert.deepEqual(languagePayload(null), { language: null });
  assert.deepEqual(languagePayload('de'), { language: 'de' });
});
