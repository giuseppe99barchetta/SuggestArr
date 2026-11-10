/**
 * "What's new" popup logic: which release note to show, and what has been seen.
 *
 * Entries are keyed by a stable `id`, never by app version: the Docker workflow assigns the
 * version on `main` only, so a nightly build carries the previous release's version number.
 * An entry exists in the code only in builds that contain its feature, which is what makes it eligible.
 */
export const SEEN_STORAGE_KEY = 'suggestarr-whats-new-seen';

/** Slides this viewer should see (admin-only slides are hidden from other users). */
export function visibleSlides(entry, isAdmin) {
  return (entry?.slides || []).filter((slide) => isAdmin || !slide.adminOnly);
}

/**
 * The newest entry not yet seen that has something to show this viewer.
 * @param {Array} entries Release entries, newest first.
 * @param {Iterable<string>} seenIds Ids already seen.
 * @param {boolean} isAdmin Whether the viewer is an admin.
 * @returns {object|null} The entry with its slides filtered for the viewer, or null.
 */
export function pendingEntry(entries, seenIds, isAdmin = false) {
  const seen = new Set(seenIds || []);
  for (const entry of entries || []) {
    if (seen.has(entry.id)) continue;
    const slides = visibleSlides(entry, isAdmin);
    if (slides.length) return { ...entry, slides };
  }
  return null;
}

/** Ids of every entry not yet seen: closing the popup marks all of them, so older ones never resurface. */
export function unseenIds(entries, seenIds) {
  const seen = new Set(seenIds || []);
  return (entries || []).map((entry) => entry.id).filter((id) => !seen.has(id));
}

export function readSeen(storage = globalThis.localStorage) {
  try {
    const value = JSON.parse(storage.getItem(SEEN_STORAGE_KEY) || '[]');
    return Array.isArray(value) ? value.filter((id) => typeof id === 'string') : [];
  } catch {
    return []; // storage blocked or corrupt: the popup may show again, never break the page
  }
}

export function markSeen(ids, storage = globalThis.localStorage) {
  try {
    storage.setItem(SEEN_STORAGE_KEY, JSON.stringify([...new Set([...readSeen(storage), ...ids])]));
  } catch {
    // storage unavailable (private window): nothing to remember with
  }
}
