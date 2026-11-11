import { test } from 'node:test';
import assert from 'node:assert/strict';
import { SEEN_STORAGE_KEY, markSeen, pendingEntry, readSeen, visibleSlides } from './whatsNew.js';
import { WHATS_NEW } from '../data/releaseNotes.js';

const slide = (extra = {}) => ({ icon: 'fa-tag', tone: 'brand', heading: 'h', text: 't', ...extra });
const entry = { id: 'new', title: 'New', slides: [slide(), slide({ adminOnly: true })] };

function memoryStorage(initial = {}) {
  const data = { ...initial };
  return { getItem: (key) => data[key] ?? null, setItem: (key, value) => { data[key] = value; }, data };
}

test('admin-only slides are hidden from other users', () => {
  assert.equal(pendingEntry(entry, []).id, 'new');
  assert.equal(pendingEntry(entry, [], false).slides.length, 1);
  assert.equal(pendingEntry(entry, [], true).slides.length, 2);
});

test('a seen note, or one with nothing for this viewer, is not pending', () => {
  assert.equal(pendingEntry(entry, ['new']), null);
  assert.equal(pendingEntry(entry, ['unrelated']).id, 'new');
  assert.equal(pendingEntry({ id: 'a', slides: [slide({ adminOnly: true })] }, [], false), null);
  const storage = memoryStorage();
  markSeen([entry.id], storage);
  assert.equal(pendingEntry(entry, readSeen(storage), true), null);
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

test('the release note is complete', () => {
  assert.ok(WHATS_NEW.id && WHATS_NEW.title, 'needs an id and a title');
  assert.ok(WHATS_NEW.slides.length > 0 && WHATS_NEW.slides.length <= 5, 'needs 1 to 5 slides');
  for (const s of WHATS_NEW.slides) {
    for (const field of ['icon', 'heading', 'text']) assert.ok(s[field], `slide without ${field}`);
    assert.match(s.icon, /^fa-[a-z0-9-]+$/);
    assert.ok(['brand', 'good', 'caution'].includes(s.tone), `unknown tone ${s.tone}`);
    assert.ok(s.text.length <= 220, `text too long for one slide: ${s.heading}`);
    const points = s.points || [];
    assert.ok(Array.isArray(points) && points.length <= 3, `at most 3 points: ${s.heading}`);
    for (const point of points) assert.ok(typeof point === 'string' && point.trim() && point.length <= 110, `short points only: ${s.heading}`);
  }
});
