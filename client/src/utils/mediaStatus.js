/** How far a requested title has come, from the watch sync and the Seer availability sync. */

const STATES = {
  requested: { label: 'Requested in Seer', icon: 'fas fa-paper-plane', tone: 'bg-canvas/85 text-ink-3 ring-1 ring-white/15' },
  watched: { label: 'Watched', icon: 'fas fa-check', tone: 'bg-good text-on-good' },
  available: { label: 'Available to watch', icon: 'fas fa-play', tone: 'bg-brand text-white' },
  partial: { label: 'Partly available', icon: 'fas fa-play', tone: 'bg-brand/70 text-white' },
  processing: { label: 'Downloading', icon: 'fas fa-arrow-down', tone: 'bg-canvas/85 text-ink-2 ring-1 ring-white/15' },
};

/**
 * @param {string|null} watchedAt - When the recipient first played it, if they did.
 * @param {string|null} availability - Seer status: requested, pending, processing, partial or available;
 *   empty before the first availability sync.
 * @returns {{ key: string, label: string, icon: string, tone: string }} The furthest state reached.
 *   Pending in Seer and not yet synced both read as requested: every card here was sent to Seer.
 */
export function mediaStatus(watchedAt, availability) {
  const key = watchedAt ? 'watched' : (STATES[availability] ? availability : 'requested');
  return { key, ...STATES[key] };
}

/** Progress filter choices; values match the `progress` parameter of /api/automation/requests. */
export const PROGRESS_OPTIONS = [
  { value: 'all', label: 'Any progress' },
  { value: 'requested', label: 'Requested' },
  { value: 'processing', label: 'Downloading' },
  { value: 'available', label: 'Available' },
  { value: 'watched', label: 'Watched' },
];
