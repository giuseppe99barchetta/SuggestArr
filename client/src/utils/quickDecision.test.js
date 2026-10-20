import assert from 'node:assert/strict';
import { test } from 'node:test';
import { keyDecision, swipeDecision } from './quickDecision.js';

const key = (k, extra = {}) => ({ key: k, target: { closest: () => null }, ...extra });

test('A, R and S decide; other keys, modifiers and repeats do not', () => {
  assert.equal(keyDecision(key('a')), 'approve');
  assert.equal(keyDecision(key('R')), 'reject');
  assert.equal(keyDecision(key('s')), 'seen');
  assert.equal(keyDecision(key('x')), null);
  assert.equal(keyDecision(key('a', { ctrlKey: true })), null);
  assert.equal(keyDecision(key('a', { repeat: true })), null);
});

test('typing in a field is never a shortcut', () => {
  assert.equal(keyDecision(key('a', { target: { closest: () => ({}) } })), null);
});

test('a long horizontal swipe decides; short or vertical drags scroll', () => {
  assert.equal(swipeDecision({ x: 0, y: 0 }, { x: 120, y: 10 }), 'approve');
  assert.equal(swipeDecision({ x: 200, y: 0 }, { x: 60, y: 20 }), 'reject');
  assert.equal(swipeDecision({ x: 0, y: 0 }, { x: 40, y: 0 }), null);
  assert.equal(swipeDecision({ x: 0, y: 0 }, { x: 100, y: 90 }), null);
  assert.equal(swipeDecision(null, { x: 100, y: 0 }), null);
});
