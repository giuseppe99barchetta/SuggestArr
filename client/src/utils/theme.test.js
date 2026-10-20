import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readThemeChoice, resolveTheme } from './theme.js';

const storage = (value) => ({ getItem: () => value });

test('the saved choice is read, and anything else means system', () => {
  assert.equal(readThemeChoice(storage('light')), 'light');
  assert.equal(readThemeChoice(storage('dark')), 'dark');
  assert.equal(readThemeChoice(storage(null)), 'system');
  assert.equal(readThemeChoice(storage('purple')), 'system');
  assert.equal(readThemeChoice({ getItem: () => { throw new Error('blocked'); } }), 'system');
});

test('system follows the OS; an explicit choice wins', () => {
  assert.equal(resolveTheme('system', true), 'dark');
  assert.equal(resolveTheme('system', false), 'light');
  assert.equal(resolveTheme('light', true), 'light');
  assert.equal(resolveTheme('dark', false), 'dark');
});
