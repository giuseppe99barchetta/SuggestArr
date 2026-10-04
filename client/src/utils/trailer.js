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
