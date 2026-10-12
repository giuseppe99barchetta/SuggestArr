/**
 * Utility functions for date formatting and manipulation
 */

/**
 * Formats a date string into a human-readable relative format
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted date string
 */
export function formatDate(dateString) {
  if (!dateString) return 'N/A';

  const date = new Date(dateString);
  const now = new Date();

  // Reset time to midnight for accurate day comparison
  const dateOnly = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const nowOnly = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  const diffTime = nowOnly - dateOnly;
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'today';
  if (diffDays === 1) return 'yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) {
    const weeks = Math.floor(diffDays / 7);
    return weeks === 1 ? '1 week ago' : `${weeks} weeks ago`;
  }
  if (diffDays < 365) {
    const months = Math.floor(diffDays / 30);
    return months === 1 ? '1 month ago' : `${months} months ago`;
  }
  const years = Math.floor(diffDays / 365);
  return years === 1 ? '1 year ago' : `${years} years ago`;
}

/**
 * Default export for convenience
 */
export default {
  formatDate
};
/**
 * Short distance between now and a date, in either direction:
 * "in 2h 14m", "in 3 days", "5m ago", "2 days ago".
 * @param {string|Date} value - Date or ISO string
 * @param {Date} [now] - Reference time (for tests)
 * @returns {string} Relative label, or '' for a missing/invalid date
 */
export function timeFromNow(value, now = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  if (!value || Number.isNaN(date.getTime())) return '';
  const minutes = Math.round((date - now) / 60000);
  const abs = Math.abs(minutes);
  let label;
  if (abs < 1) return 'just now';
  if (abs < 60) label = `${abs}m`;
  // Minutes only matter for what is coming up; "18h ago" reads better than "18h 36m ago".
  else if (abs < 24 * 60) label = `${Math.floor(abs / 60)}h${minutes > 0 && abs % 60 ? ` ${abs % 60}m` : ''}`;
  else {
    const days = Math.round(abs / (24 * 60));
    label = days === 1 ? '1 day' : `${days} days`;
  }
  return minutes > 0 ? `in ${label}` : `${label} ago`;
}
