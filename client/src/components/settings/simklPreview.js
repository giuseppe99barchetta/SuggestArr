/**
 * Formatting helpers for the Simkl recent-items preview.
 *
 * Kept out of the component for the same reason as trackerState: the rules
 * turn on values the UI cannot show you (a missing watch date arrives as a
 * number, not as null), so they are easier to get right against tests.
 */

/**
 * Render a cached Simkl watch timestamp, or nothing when there isn't one.
 *
 * Simkl entries with no watch date are cached as epoch 0, which formats as a
 * perfectly valid 1 January 1970 rather than as the missing value it is.
 *
 * @param {number|string|null|undefined} ts Epoch seconds.
 * @returns {string} A locale date, or '' when there is no usable timestamp.
 */
export function formatWatchedDate(ts) {
  const seconds = Number(ts);
  if (!seconds || Number.isNaN(seconds)) return '';
  const date = new Date(seconds * 1000);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString();
}
