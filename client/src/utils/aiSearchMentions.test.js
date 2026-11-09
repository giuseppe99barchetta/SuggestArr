import assert from 'node:assert/strict';
import { test } from 'node:test';

import { addSelected, applyMention, filterPeople, findMentionQuery, toggleSelected } from './aiSearchMentions.js';

test('a mention is the @word being typed at the caret, and only at the start of a word', () => {
  assert.deepEqual(findMentionQuery('a film for @An', 14), { start: 11, query: 'An' });
  assert.deepEqual(findMentionQuery('@', 1), { start: 0, query: '' });
  assert.equal(findMentionQuery('write to me@home', 16), null);
  // Spaces stay inside the query so a two-word name can be narrowed; unrelated text just matches nobody.
  assert.deepEqual(findMentionQuery('a film for @Ann Le', 18), { start: 11, query: 'Ann Le' });
  assert.deepEqual(filterPeople([{ id: 1, name: 'Ann Lee' }, { id: 2, name: 'Bob' }], 'Ann Le').map(person => person.id), [1]);
  assert.deepEqual(filterPeople([{ id: 1, name: 'Ann Lee' }], 'Ann and we want'), []);
  assert.equal(findMentionQuery('a film for @' + 'x'.repeat(41), 12 + 41), null);
  // Only text before the caret counts.
  assert.deepEqual(findMentionQuery('@Ann tonight', 2), { start: 0, query: 'A' });
});

test('people are filtered by any part of their name, ignoring case', () => {
  const people = [{ id: 1, name: 'Ann Lee' }, { id: 2, name: 'Bob' }];
  assert.deepEqual(filterPeople(people, 'LEE').map(person => person.id), [1]);
  assert.deepEqual(filterPeople(people, '').map(person => person.id), [1, 2]);
});

test('choosing a mention swaps the typed part for the full name and moves the caret after it', () => {
  const text = 'a film for @An tonight';
  const result = applyMention(text, { start: 11, query: 'An' }, 14, 'Ann Lee');
  assert.equal(result.text, 'a film for @Ann Lee  tonight');
  assert.equal(result.caret, 11 + '@Ann Lee '.length);
});

test('the last selected person cannot be removed and the limit cannot be exceeded', () => {
  assert.deepEqual(toggleSelected([1], 1), { ids: [1], reason: 'last' });
  assert.deepEqual(toggleSelected([1, 2], 1), { ids: [2], reason: null });
  assert.deepEqual(toggleSelected([1], 2), { ids: [1, 2], reason: null });
  assert.deepEqual(toggleSelected([1, 2, 3, 4], 5), { ids: [1, 2, 3, 4], reason: 'limit' });
  assert.deepEqual(toggleSelected([1, 2, 3, 4], 4), { ids: [1, 2, 3], reason: null });
});

test('a mention only adds: an already selected person stays, a fifth is refused', () => {
  assert.deepEqual(addSelected([1, 2], 2), { ids: [1, 2], reason: null });
  assert.deepEqual(addSelected([1, 2], 3), { ids: [1, 2, 3], reason: null });
  assert.deepEqual(addSelected([1, 2, 3, 4], 5), { ids: [1, 2, 3, 4], reason: 'limit' });
});
