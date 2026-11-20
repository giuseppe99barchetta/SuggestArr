/**
 * "What's new" popup logic: which release note to show, and what has been seen.
 *
 * The note is keyed by a stable `id`, never by app version: the Docker workflow assigns the
 * version on `main` only, so a nightly build carries the previous release's version number.
 * The note exists in the code only in builds that contain its feature, which is what makes it eligible.
 */
export const SEEN_STORAGE_KEY = 'suggestarr-whats-new-seen';

/** Slides this viewer should see (admin-only slides are hidden from other users). */
export function visibleSlides(entry, isAdmin) {
  return (entry?.slides || []).filter((slide) => isAdmin || !slide.adminOnly);
}

/**
 * The note if this viewer has not seen it and it has something for them.
 * @param {object} entry The release note.
 * @param {Iterable<string>} seenIds Ids already seen.
 * @param {boolean} isAdmin Whether the viewer is an admin.
 * @returns {object|null} The entry with its slides filtered for the viewer, or null.
 */
export function pendingEntry(entry, seenIds, isAdmin = false) {
  if (!entry || new Set(seenIds || []).has(entry.id)) return null;
  const slides = visibleSlides(entry, isAdmin);
  return slides.length ? { ...entry, slides } : null;
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
