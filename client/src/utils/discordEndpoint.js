/**
 * The public address Discord should call for rating-prompt button taps.
 *
 * @param {string} origin Page origin, e.g. https://example.com
 * @param {string} baseURL The API base the app already uses (axios default): the sub-path, "/" at the root,
 *   or an absolute URL in development.
 * @returns {string} The full Interactions Endpoint URL, including any sub-path.
 */
export function discordEndpointUrl(origin, baseURL) {
  const base = new URL(baseURL || '/', origin);
  return `${base.origin}${base.pathname.replace(/\/+$/, '')}/api/discord/interactions`;
}
