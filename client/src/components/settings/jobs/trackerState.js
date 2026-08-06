/**
 * Shared availability logic for watch trackers (Trakt, Simkl) on a
 * recommendation job.
 *
 * Kept out of the component so the rules can be tested directly: whether a
 * toggle is offered depends on which users a job reads from, which is easy to
 * get subtly wrong and hard to see in the UI.
 */

/** Whether any user this job actually reads from has the tracker linked. */
export function monitoredConnected({ users, key, userMode, selectedIds }) {
  if (!users.length) return false;
  if (userMode === 'all') {
    return users.some(u => u[key]?.connected);
  }
  if (!selectedIds.length) return false;
  return users.some(
    u => selectedIds.includes(u.external_user_id) && u[key]?.connected
  );
}

/**
 * How a watch tracker relates to this job.
 *
 * A tracker is only `usable` when a monitored user has it linked, since
 * enabling it otherwise would silently do nothing. `linked-not-monitored`
 * separates the case that would otherwise read as a broken integration: an
 * account *is* linked, just not for a user this job reads from.
 */
export function trackerState({
  configured, users, selfConnected, key, userMode, selectedIds,
}) {
  if (!configured) return 'unconfigured';
  if (monitoredConnected({ users, key, userMode, selectedIds })) return 'usable';
  if (selfConnected || users.some(u => u[key]?.connected)) {
    return 'linked-not-monitored';
  }
  return 'none-linked';
}

/** Why a tracker is unavailable, or null when it is usable. */
export function trackerWarning(state, label, credentials) {
  switch (state) {
    case 'unconfigured':
      return `${label} not configured — set the ${credentials} in Services`;
    case 'linked-not-monitored':
      return `A ${label} account is linked, but not for any user this job monitors`;
    case 'none-linked':
      return `No linked ${label} accounts — each user links their own from Profile > ${label} Account`;
    default:
      return null;
  }
}
