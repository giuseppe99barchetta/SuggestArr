<template>
  <AppDialog title="Your badges" :subtitle="`${unlockedCount} of ${recap.badges.length} unlocked`" icon="fas fa-award" width="max-w-4xl" @close="$emit('close')">
    <div class="flex flex-col gap-7">
      <div class="flex flex-wrap items-center gap-x-5 gap-y-4 rounded-card border border-brand-ink/15 bg-linear-to-r from-brand-soft/35 via-panel to-panel p-4 sm:p-5">
        <BadgeMedallion v-if="latest" :badge="latest" size="lg" />
        <div class="min-w-0 flex-1">
          <p class="m-0 text-[11px] font-semibold uppercase tracking-widest text-brand-ink">{{ latest ? 'Latest badge' : 'Your collection' }}</p>
          <p class="m-0 mt-1 text-lg font-bold leading-snug text-ink">{{ latest ? latest.label : 'Your first badge is on its way' }}</p>
          <p v-if="latest?.unlocked_at" class="m-0 mt-0.5 text-xs text-ink-4">{{ hint(latest) }}</p>
          <progress class="mt-3 block h-1.5 w-full max-w-xs appearance-none overflow-hidden rounded-full border-0 bg-raised [&::-webkit-progress-bar]:bg-raised [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:bg-brand [&::-moz-progress-bar]:bg-brand" :value="unlockedCount" :max="recap.badges.length" aria-label="Badges unlocked"></progress>
        </div>
        <div v-if="hitRate || recap.streak?.current" class="flex gap-5 text-center">
          <div v-if="hitRate"><p class="m-0 text-2xl font-extrabold text-ink">{{ recap.hit_rate }}%</p><p class="m-0 text-[11px] text-ink-4">picks watched</p></div>
          <div v-if="recap.streak?.current"><p class="m-0 text-2xl font-extrabold text-ink">{{ recap.streak.current }}</p><p class="m-0 text-[11px] text-ink-4">month streak</p></div>
        </div>
      </div>

      <section v-if="next.length" aria-labelledby="badges-up-next">
        <h3 id="badges-up-next" class="m-0 mb-3 text-sm font-bold text-ink">Up next</h3>
        <ul class="m-0 grid list-none gap-3 p-0 sm:grid-cols-3">
          <li v-for="badge in next" :key="badge.id" class="flex items-center gap-3 rounded-card border border-edge bg-panel-2 p-3">
            <BadgeMedallion :badge="badge" size="sm" />
            <div class="min-w-0 flex-1">
              <p class="m-0 truncate text-[13px] font-semibold text-ink">{{ badge.label }}</p>
              <p class="m-0 mt-0.5 truncate text-[11px] text-ink-3">{{ hint(badge) }}</p>
              <progress class="mt-2 block h-1 w-full appearance-none overflow-hidden rounded-full border-0 bg-raised [&::-webkit-progress-bar]:bg-raised [&::-webkit-progress-value]:bg-brand [&::-moz-progress-bar]:bg-brand" :value="badge.progress" :max="badge.threshold" :aria-label="`Progress toward ${badge.label}`"></progress>
            </div>
          </li>
        </ul>
      </section>

      <section v-for="group in groups" :key="group.kind" :aria-labelledby="`badge-group-${group.kind}`">
        <div class="mb-3 flex items-baseline justify-between gap-2">
          <h3 :id="`badge-group-${group.kind}`" class="m-0 text-sm font-bold text-ink">{{ group.title }}</h3>
          <span class="text-[11px] tabular-nums text-ink-4">{{ group.badges.filter(badge => badge.unlocked).length }} / {{ group.badges.length }}</span>
        </div>
        <ul :aria-label="group.title" class="m-0 grid list-none grid-cols-3 gap-x-2 gap-y-4 p-0 sm:grid-cols-5 md:grid-cols-6">
          <li v-for="badge in group.badges" :key="badge.id">
            <button type="button" class="flex w-full cursor-pointer flex-col items-center gap-2 rounded-card border-0 bg-transparent p-2 text-center transition-colors hover:bg-raised" :class="selected?.id === badge.id ? 'bg-raised' : ''" :aria-expanded="badge.unlocked ? null : selected?.id === badge.id" :aria-label="`${badge.label}, ${badge.unlocked ? 'unlocked' : 'locked'}`" @click="open(badge)">
              <span class="relative" :class="badge.unlocked ? '' : 'opacity-60'">
                <BadgeMedallion :badge="badge" size="md" />
                <span v-if="!badge.unlocked" aria-hidden="true" class="absolute -bottom-0.5 -right-0.5 grid h-5 w-5 place-items-center rounded-full border border-edge bg-panel text-[9px] text-ink-4"><i class="fas fa-lock"></i></span>
              </span>
              <span class="text-[11px] font-semibold leading-tight" :class="badge.unlocked ? 'text-ink' : 'text-ink-4'">{{ badge.label }}</span>
            </button>
          </li>
        </ul>
        <div v-if="selected && selected.kind === group.kind" role="region" :aria-label="`${selected.label} details`" class="mt-3 flex items-center gap-4 rounded-card border border-edge bg-panel-2 p-4">
          <BadgeMedallion :badge="selected" size="sm" />
          <div class="min-w-0 flex-1">
            <p class="m-0 text-[13px] font-semibold text-ink">{{ selected.label }}</p>
            <p class="m-0 mt-0.5 text-xs text-ink-3">{{ selected.description }} · {{ hint(selected) }}</p>
            <progress v-if="selected.kind !== 'days'" class="mt-2 block h-1 w-full max-w-sm appearance-none overflow-hidden rounded-full border-0 bg-raised [&::-webkit-progress-bar]:bg-raised [&::-webkit-progress-value]:bg-brand [&::-moz-progress-bar]:bg-brand" :value="selected.progress" :max="selected.threshold" :aria-label="`Progress toward ${selected.label}`"></progress>
          </div>
        </div>
      </section>

      <p v-if="!recap.watch_tracking" class="m-0 text-xs leading-relaxed text-ink-4">Connect Plex or Jellyfin to unlock badges for the suggestions you actually watch.</p>
    </div>
    <BadgeUnlockedDialog v-if="viewing" :badges="[viewing]" :celebrate="false" @close="viewing = null" @support="viewing = null; $emit('support')" />
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import BadgeMedallion from './BadgeMedallion.vue';
import BadgeUnlockedDialog from './BadgeUnlockedDialog.vue';
import { BADGE_GROUPS, badgeHint, latestBadge, showHitRate, upNext } from '@/utils/recapBadges.js';

export default {
  name: 'BadgesDialog',
  components: { AppDialog, BadgeMedallion, BadgeUnlockedDialog },
  props: { recap: { type: Object, required: true } },
  emits: ['close', 'support'],
  data: () => ({ selected: null, viewing: null }),
  computed: {
    groups() {
      return BADGE_GROUPS.map(group => ({ ...group, badges: this.recap.badges.filter(badge => badge.kind === group.kind) }))
        .filter(group => group.badges.length);
    },
    unlockedCount() { return this.recap.badges.filter(badge => badge.unlocked).length; },
    latest() { return latestBadge(this.recap.badges); },
    next() { return upNext(this.recap.badges); },
    hitRate() { return showHitRate(this.recap); },
  },
  methods: {
    hint: badgeHint,
    /** Unlocked badges open their shareable view; locked ones toggle what is still missing. */
    open(badge) {
      if (badge.unlocked) this.viewing = badge;
      else this.selected = this.selected?.id === badge.id ? null : badge;
    },
  },
};
</script>
