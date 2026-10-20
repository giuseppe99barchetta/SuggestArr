const SUBJECTS = ['film', 'tv', 'ticket', 'clapperboard', 'reel'];
const PALETTES = [
  'bg-brand-soft text-brand-ink',
  'bg-notice/15 text-notice',
  'bg-good/15 text-good',
  'bg-caution/15 text-caution',
];

// An apparently random assignment that stays the same across sessions and renames.
export function cinemaAvatar(user) {
  const seed = String(user?.id ?? user?.username ?? 'suggestarr');
  let hash = 2166136261;
  for (const character of seed) hash = Math.imul(hash ^ character.charCodeAt(0), 16777619) >>> 0;
  return { subject: SUBJECTS[hash % SUBJECTS.length], palette: PALETTES[Math.floor(hash / SUBJECTS.length) % PALETTES.length] };
}
