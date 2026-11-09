// Picking the people an AI Search is for, and the @name autocomplete that goes with it.
// Kept free of Vue so the rules (4 people at most, never none) are easy to test.

export const MAX_PEOPLE = 4;
export const LIMIT_MESSAGE = `You can pick up to ${MAX_PEOPLE} people.`;

// The "@name" being typed just before the caret, or null. It must start a word, so an
// e-mail address such as "a@b" is not a mention. Spaces are allowed (up to 40 characters)
// so "@Ann Le" can still find "Ann Lee"; text that matches nobody simply shows no list.
export function findMentionQuery(text, caret) {
  const before = String(text || '').slice(0, caret);
  const match = /(^|\s)@([^@\n]{0,40})$/.exec(before);
  return match ? { start: before.length - match[2].length - 1, query: match[2] } : null;
}

export function filterPeople(people, query) {
  const needle = String(query || '').toLowerCase();
  return people.filter(person => person.name.toLowerCase().includes(needle));
}

// Replace the "@partial" with "@Full Name " and say where the caret goes.
export function applyMention(text, mention, caret, name) {
  const insert = `@${name} `;
  return { text: text.slice(0, mention.start) + insert + text.slice(caret), caret: mention.start + insert.length };
}

// Turn a chip on or off. At least one person always stays selected, and no more than
// `limit`; `reason` says why nothing changed ('last' or 'limit').
export function toggleSelected(selected, id, limit = MAX_PEOPLE) {
  if (selected.includes(id)) {
    return selected.length > 1 ? { ids: selected.filter(item => item !== id), reason: null } : { ids: selected, reason: 'last' };
  }
  return selected.length >= limit ? { ids: selected, reason: 'limit' } : { ids: [...selected, id], reason: null };
}

// Selecting through a mention only ever adds.
export function addSelected(selected, id, limit = MAX_PEOPLE) {
  return selected.includes(id) ? { ids: selected, reason: null } : toggleSelected(selected, id, limit);
}
