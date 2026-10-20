<template>
  <div>
    <div class="mb-5 flex flex-wrap items-center justify-between gap-2">
      <h3 class="m-0 text-base font-bold text-ink">Your badges</h3>
      <span class="rounded-full border border-brand-ink/15 bg-brand-soft/30 px-3 py-1 text-[11px] font-semibold text-brand-ink">{{ unlockedCount }} / {{ recap.badges.length }} unlocked</span>
    </div>
    <p v-if="recap.hit_rate != null" class="m-0 mb-5 rounded-ctl border border-edge bg-canvas/30 px-3 py-2 text-xs leading-relaxed text-ink-3"><strong class="text-ink">{{ recap.hit_rate }}%</strong> of requested titles watched · {{ recap.watched.toLocaleString('en-US') }} of {{ recap.total.toLocaleString('en-US') }}<template v-if="recap.streak?.current"> · {{ recap.streak.current }}-month streak</template></p>
    <section v-for="group in groups" :key="group.kind" class="mt-5 first:mt-0" :aria-labelledby="`badge-group-${group.kind}`">
      <h4 :id="`badge-group-${group.kind}`" class="m-0 mb-2 text-[11px] font-semibold uppercase tracking-widest text-ink-4">{{ group.title }}</h4>
      <ul :aria-label="group.title" class="m-0 grid list-none grid-cols-2 gap-3 p-0 sm:grid-cols-3">
        <li v-for="badge in group.badges" :key="badge.id" class="relative flex flex-col items-center overflow-hidden rounded-card border px-2 py-3 text-center" :class="badge.unlocked ? 'border-brand-ink/20 bg-linear-to-b from-brand-soft/40 to-panel' : isNext(badge) ? 'border-brand-ink/45 bg-brand-soft/10' : 'border-edge bg-canvas/30'">
          <span class="mb-2 grid h-11 w-11 shrink-0 place-items-center rounded-full border text-center" :class="badge.unlocked ? 'border-brand-ink/30 bg-brand-soft text-brand-ink ring-4 ring-brand-soft/20' : 'border-edge-strong bg-panel text-ink-3'" aria-hidden="true">
            <i v-if="medallion(badge).icon" :class="medallion(badge).icon" class="text-base"></i>
            <span v-else class="leading-none"><span class="block text-base font-extrabold tracking-tight">{{ medallion(badge).text }}</span><span class="block text-[7px] font-semibold uppercase tracking-wider opacity-80">{{ medallion(badge).unit }}</span></span>
          </span>
          <p class="m-0 flex min-h-8 items-center text-xs font-semibold leading-snug" :class="badge.unlocked ? 'text-ink' : 'text-ink-3'">{{ badge.label }}</p>
          <p class="m-0 mt-1 text-[11px] leading-snug text-ink-4">{{ badge.description }}</p>
          <span class="mt-2 inline-flex items-center gap-1.5 text-[10px] font-semibold" :class="badge.unlocked ? 'text-brand-ink' : isNext(badge) ? 'text-ink-2' : 'text-ink-4'"><i aria-hidden="true" :class="badge.unlocked ? 'fas fa-check' : isNext(badge) ? 'fas fa-arrow-right' : 'fas fa-lock'"></i>{{ isNext(badge) ? `Next milestone · ${hint(badge)}` : hint(badge) }}</span>
          <progress v-if="!badge.unlocked && badge.kind !== 'days' && badge.progress" class="absolute inset-x-0 bottom-0 block h-1 w-full appearance-none overflow-hidden border-0 bg-raised [&::-webkit-progress-bar]:bg-raised [&::-webkit-progress-value]:bg-brand [&::-moz-progress-bar]:bg-brand" :value="badge.progress" :max="badge.threshold" :aria-label="`Progress toward ${badge.label}`"></progress>
        </li>
      </ul>
    </section>
    <p v-if="!recap.watch_tracking" class="m-0 mt-5 text-[11px] leading-relaxed text-ink-4">Connect Plex or Jellyfin to unlock badges for the suggestions you actually watch.</p>
  </div>
</template>

<script>
import { BADGE_GROUPS, badgeHint, badgeMedallion } from '@/utils/recapBadges.js';

export default {
  name: 'RecapBadges',
  props: { recap: { type: Object, required: true } },
  computed: {
    groups() {
      return BADGE_GROUPS.map(group => ({ ...group, badges: this.recap.badges.filter(badge => badge.kind === group.kind) }))
        .filter(group => group.badges.length);
    },
    unlockedCount() { return this.recap.badges.filter(badge => badge.unlocked).length; },
  },
  methods: {
    isNext(badge) { return !badge.unlocked && badge.id === this.recap.next_badge?.id; },
    medallion: badgeMedallion,
    hint: badgeHint,
  },
};
</script>
