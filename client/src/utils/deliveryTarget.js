/**
 * Where queued requests are delivered, from the `backend` field of each queue row
 * (`seer`, `arr`; rows from before the field existed have none and are Seer's).
 */
export function deliveryCounts(items) {
  const counts = { seer: 0, arr: 0 };
  for (const item of items || []) counts[item?.backend === 'arr' ? 'arr' : 'seer'] += 1;
  return counts;
}

/** "Seer", "Radarr/Sonarr", or "Seer (2) and Radarr/Sonarr (1)" for a mixed batch. */
export function deliveryLabel(items) {
  const { seer, arr } = deliveryCounts(items);
  if (seer && arr) return `Seer (${seer}) and Radarr/Sonarr (${arr})`;
  return arr ? 'Radarr/Sonarr' : 'Seer';
}

/** Short wording for the approval toast, including profile overrides that direct rows ignored. */
export function approvalNotice(items, ignoredOverrides = 0) {
  const base = `Queued for ${deliveryLabel(items)}`;
  return ignoredOverrides > 0
    ? `${base}. The chosen profile was ignored for ${ignoredOverrides} Radarr/Sonarr ${ignoredOverrides === 1 ? 'item' : 'items'}, which keep their own.`
    : base;
}
