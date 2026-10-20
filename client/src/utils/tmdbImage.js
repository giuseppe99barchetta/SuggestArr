/**
 * A TMDb image at a given size. Stored paths are full URLs (…/t/p/original/x.jpg) or bare
 * TMDb paths (/x.jpg); both come back as a full URL using `size` (w300, w780, w1280, original).
 *
 * @param {string|null} path
 * @param {string} size
 * @returns {string} The URL, or '' when there is no image.
 */
export function tmdbImage(path, size) {
  if (!path) return '';
  if (path.startsWith('/')) return `https://image.tmdb.org/t/p/${size}${path}`;
  return path.replace(/\/t\/p\/(w\d+|original)\//, `/t/p/${size}/`);
}
