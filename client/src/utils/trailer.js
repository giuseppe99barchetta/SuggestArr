/** Which TMDb title a request, workflow suggestion or request source stands for. */

/**
 * @param {object|null} item - What the details modal shows.
 * @returns {{ mediaType: string, tmdbId: string }|null} null when the item is not a single movie or TV show.
 */
export function trailerTarget(item) {
  if (!item || !['movie', 'tv'].includes(item.media_type)) return null;
  // A workflow suggestion carries its own row id in `id`; a source with a visual is a job, not a title.
  const tmdbId = item.tmdb_id ?? item.request_id ?? (item.visual ? null : item.id);
  if (!/^\d+$/.test(String(tmdbId ?? ''))) return null;
  return { mediaType: item.media_type, tmdbId: String(tmdbId) };
}

/**
 * @param {{ mediaType: string, tmdbId: string }} target
 * @returns {string} API path that answers with the title's trailer URL.
 */
export function trailerEndpoint(target) {
  return `/api/tmdb/trailer/${target.mediaType}/${target.tmdbId}`;
}

/**
 * @param {{ get: Function }} http - axios, or anything with the same `get`.
 * @param {object|null} item - What the details modal shows.
 * @returns {Promise<string|null>} The YouTube trailer URL; null when there is none or it cannot be looked up.
 */
export async function loadTrailerUrl(http, item) {
  const target = trailerTarget(item);
  if (!target) return null;
  try {
    const { data } = await http.get(trailerEndpoint(target));
    return data?.url || null;
  } catch {
    // Without a trailer the link is simply not offered.
    return null;
  }
}

/**
 * Look a trailer up only once it is asked for, and open it in a new tab.
 * For lists too long to look every title up in advance.
 *
 * @param {{ get: Function }} http - axios, or anything with the same `get`.
 * @param {object|null} item - The listed title.
 * @param {Function} [openTab] - Opens a blank tab and returns its window.
 * @returns {Promise<'opened'|'blocked'|'none'>} 'none' when the title has no trailer,
 *   'blocked' when it has one but the browser refused to open a tab for it.
 */
export async function openTrailer(http, item, openTab = () => window.open('', '_blank')) {
  // Opened before the lookup: a tab opened after waiting is blocked as a popup.
  const tab = openTab();
  const url = await loadTrailerUrl(http, item);
  if (!url) {
    tab?.close();
    return 'none';
  }
  if (!tab) return 'blocked';
  tab.opener = null;
  tab.location.replace(url);
  return 'opened';
}
