import { trailerTarget } from './trailer.js';

let webUrl = null;

/**
 * Seer's browser address, asked once per page load.
 *
 * @param {{ get: Function }} http - axios, or anything with the same `get`.
 * @returns {Promise<string|null>} The address, or null when Seer is not set up or cannot be asked.
 */
export function loadSeerWebUrl(http) {
  webUrl ??= http.get('/api/seer/web-url')
    .then(({ data }) => data?.url || null)
    .catch(() => {
      webUrl = null; // try again on the next modal
      return null;
    });
  return webUrl;
}

/**
 * @param {string|null} base - Seer's browser address.
 * @param {object} item - What the details modal shows.
 * @returns {string|null} The title's page in Seer, or null when there is no Seer or no single title.
 */
export function seerTitleUrl(base, item) {
  const target = trailerTarget(item);
  return base && target ? `${base}/${target.mediaType}/${target.tmdbId}` : null;
}
