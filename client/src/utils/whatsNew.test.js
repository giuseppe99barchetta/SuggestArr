import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { SEEN_STORAGE_KEY, artProblems, markSeen, pendingEntry, readSeen, unseenIds, visibleSlides } from './whatsNew.js';
import { RELEASE_NOTES } from '../data/releaseNotes.js';

const slide = (extra = {}) => ({ art: { type: 'features', items: [{ label: 'a' }] }, tone: 'brand', heading: 'h', changes: 'c', impact: 'i', ...extra });
const entries = [
  { id: 'new', title: 'New', slides: [slide(), slide({ adminOnly: true })] },
  { id: 'admin-only', title: 'Admin', slides: [slide({ adminOnly: true })] },
  { id: 'old', title: 'Old', slides: [slide()] },
];

function memoryStorage(initial = {}) {
  const data = { ...initial };
  return { getItem: (key) => data[key] ?? null, setItem: (key, value) => { data[key] = value; }, data };
}

test('the newest unseen entry is shown, with admin-only slides hidden from other users', () => {
  assert.equal(pendingEntry(entries, []).id, 'new');
  assert.equal(pendingEntry(entries, [], false).slides.length, 1);
  assert.equal(pendingEntry(entries, [], true).slides.length, 2);
});

test('seen entries are skipped, and an entry with nothing for this viewer is passed over', () => {
  assert.equal(pendingEntry(entries, ['new']).id, 'old');
  assert.equal(pendingEntry([entries[1]], [], false), null);
  assert.equal(pendingEntry(entries, ['new', 'old'], false), null);
  assert.equal(pendingEntry(entries, ['new', 'old'], true).id, 'admin-only');
});

test('after a multi-release upgrade only the newest is shown and closing marks every older one as seen', () => {
  assert.equal(pendingEntry(entries, ['unrelated']).id, 'new');
  assert.deepEqual(unseenIds(entries, ['old']), ['new', 'admin-only']);
  const storage = memoryStorage();
  markSeen(unseenIds(entries, []), storage);
  assert.equal(pendingEntry(entries, readSeen(storage), true), null);
});

test('the seen list is stored once per id and survives a corrupt or blocked storage', () => {
  const storage = memoryStorage();
  markSeen(['a'], storage);
  markSeen(['a', 'b'], storage);
  assert.deepEqual(readSeen(storage), ['a', 'b']);
  assert.deepEqual(readSeen(memoryStorage({ [SEEN_STORAGE_KEY]: '{not json' })), []);
  assert.deepEqual(readSeen(memoryStorage({ [SEEN_STORAGE_KEY]: '{"a":1}' })), []);
  const blocked = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  assert.deepEqual(readSeen(blocked), []);
  assert.doesNotThrow(() => markSeen(['a'], blocked));
});

test('visibleSlides tolerates a missing entry', () => {
  assert.deepEqual(visibleSlides(undefined, true), []);
});

test('every release note is complete and its art is valid', () => {
  const ids = new Set();
  for (const entry of RELEASE_NOTES) {
    assert.ok(entry.id && entry.title, 'entry needs an id and a title');
    assert.ok(!ids.has(entry.id), `duplicate id ${entry.id}`);
    ids.add(entry.id);
    assert.ok(entry.slides.length > 0, `${entry.id} has no slides`);
    for (const s of entry.slides) {
      for (const field of ['tone', 'heading', 'changes', 'impact']) assert.ok(s[field], `${entry.id}: slide without ${field}`);
      assert.ok(['brand', 'good', 'caution'].includes(s.tone), `${entry.id}: unknown tone ${s.tone}`);
      if (s.art) {
        assert.deepEqual(artProblems(s.art), [], `${entry.id}: ${s.heading}`);
      } else {
        const file = fileURLToPath(new URL(`../assets/whats-new/${entry.id}/${s.icon}`, import.meta.url));
        assert.ok(s.icon && existsSync(file), `${entry.id}: slide needs art or an existing icon file (${s.icon})`);
      }
    }
  }
});

test('artProblems accepts the three art types and explains what is wrong otherwise', () => {
  assert.deepEqual(artProblems({ type: 'flow', source: { poster: true }, targets: [{ label: 'A' }] }), []);
  assert.deepEqual(artProblems({ type: 'form', fields: [{ label: 'L', value: 'V' }], optional: { label: 'O', value: 'V' } }), []);
  assert.deepEqual(artProblems({ type: 'features', items: [{ label: 'x' }], locked: false }), []);
  assert.match(artProblems({ type: 'chart' })[0], /unknown art type/);
  assert.match(artProblems(null)[0], /must be an object/);
  assert.ok(artProblems({ type: 'flow', source: {}, targets: [] }).length >= 2);
  assert.ok(artProblems({ type: 'flow', source: { label: 'S' }, via: 'V', targets: [{ label: 'a' }, { label: 'b' }, { label: 'c' }] }).length > 0);
  const field = { label: 'a', value: 'b' };
  assert.ok(artProblems({ type: 'form', fields: [field, field, field], optional: { label: 'o', value: 'v' } }).length > 0);
  assert.ok(artProblems({ type: 'features', items: Array.from({ length: 7 }, () => ({ label: 'x' })) }).length > 0);
});
