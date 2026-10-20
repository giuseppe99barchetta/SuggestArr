/** Presentation rules for recap badges; the server decides what is unlocked and when. */

export const BADGE_GROUPS = [
  { kind: 'titles', title: 'Titles requested' },
  { kind: 'watched', title: 'Suggestions watched' },
  { kind: 'variety', title: 'Variety' },
  { kind: 'streak', title: 'Monthly streaks' },
  { kind: 'days', title: 'Anniversaries' },
];

const VARIETY_ICONS = { genres_5: 'fas fa-layer-group', genres_10: 'fas fa-layer-group', decades_5: 'fas fa-history',
  countries_5: 'fas fa-globe', balanced: 'fas fa-balance-scale' };

const compact = value => value.toLocaleString('en-US', { notation: 'compact', maximumFractionDigits: 0 });

/** Short medallion content: either `{ text, unit }` or `{ icon }`. */
export function badgeMedallion(badge) {
  if (badge.kind === 'titles') return { text: compact(badge.threshold), unit: 'titles' };
  if (badge.kind === 'watched') return { text: compact(badge.threshold), unit: 'watched' };
  if (badge.kind === 'streak') return { text: String(badge.threshold), unit: 'months' };
  if (badge.kind === 'days') return { text: String(Math.round(badge.threshold / 365)), unit: badge.threshold > 365 ? 'years' : 'year' };
  return { icon: VARIETY_ICONS[badge.id] || 'fas fa-award' };
}

export function formatBadgeDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/** What is still missing for a locked badge, or when an unlocked one was earned. */
export function badgeHint(badge) {
  if (badge.unlocked) return badge.unlocked_at ? `Unlocked ${formatBadgeDate(badge.unlocked_at)}` : 'Unlocked';
  const remaining = Math.max(0, badge.threshold - (badge.progress || 0));
  if (badge.kind === 'titles') return `${remaining.toLocaleString('en-US')} more ${remaining === 1 ? 'title' : 'titles'} to go`;
  if (badge.kind === 'watched') return `Watch ${remaining.toLocaleString('en-US')} more ${remaining === 1 ? 'pick' : 'picks'}`;
  if (badge.kind === 'streak') return `Best so far: ${badge.progress || 0} of ${badge.threshold} months`;
  if (badge.kind === 'days') return badge.unlocks_at ? `Unlocks ${formatBadgeDate(badge.unlocks_at)}` : 'Starts with your first request';
  return `${badge.progress || 0} of ${badge.threshold} so far`;
}

/** The most recently earned badge; ties keep the server's order, favouring the later entry. */
export function latestBadge(badges = []) {
  return badges.filter(badge => badge.unlocked)
    .reduce((latest, badge) => (!latest || (badge.unlocked_at || '') >= (latest.unlocked_at || '') ? badge : latest), null);
}

const storage = () => { try { return window.localStorage; } catch { return null; } };

/**
 * Badges unlocked since this browser last saw the recap. The first visit records the current
 * state silently, so upgrading never celebrates a backlog of old badges.
 * @param {Object} recap - Recap summary with `badges` and `scope`.
 * @param {string|number} userId - Current user, so shared browsers keep separate histories.
 * @returns {Array} Newly unlocked badges, most recent first.
 */
export function newlyUnlocked(recap, userId) {
  const key = `suggestarr-recap-seen-badges:${userId ?? 'anonymous'}:${recap.scope}`;
  const unlocked = recap.badges.filter(badge => badge.unlocked);
  let seen = null;
  try { seen = JSON.parse(storage()?.getItem(key) ?? 'null'); } catch { seen = null; }
  if (!Array.isArray(seen)) {
    markBadgesSeen(recap, userId);
    return [];
  }
  return unlocked.filter(badge => !seen.includes(badge.id))
    .sort((a, b) => (b.unlocked_at || '').localeCompare(a.unlocked_at || ''));
}

export function markBadgesSeen(recap, userId) {
  const key = `suggestarr-recap-seen-badges:${userId ?? 'anonymous'}:${recap.scope}`;
  try { storage()?.setItem(key, JSON.stringify(recap.badges.filter(badge => badge.unlocked).map(badge => badge.id))); } catch { /* Celebrations are a convenience. */ }
}
