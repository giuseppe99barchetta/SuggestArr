<template>
  <div>
    <div class="mb-5 flex flex-wrap items-center justify-between gap-2">
      <h3 class="m-0 text-base font-bold text-ink">Your badges</h3>
      <span class="rounded-full border border-brand-ink/15 bg-brand-soft/30 px-3 py-1 text-[11px] font-semibold text-brand-ink">{{ unlockedCount }} / {{ recap.badges.length }} unlocked</span>
    </div>
    <ul aria-label="Title milestones" class="m-0 grid list-none grid-cols-2 gap-3 p-0 sm:grid-cols-3">
      <li v-for="badge in titleBadges" :key="badge.id" class="relative flex flex-col items-center overflow-hidden rounded-card border px-2 py-3 text-center" :class="badge.unlocked ? 'border-brand-ink/20 bg-linear-to-b from-brand-soft/40 to-panel' : isNext(badge) ? 'border-brand-ink/45 bg-brand-soft/10' : 'border-edge bg-canvas/30'">
        <span class="mb-2 grid h-11 w-11 shrink-0 place-items-center rounded-full border text-lg font-extrabold tracking-tight" :class="badge.unlocked ? 'border-brand-ink/30 bg-brand-soft text-brand-ink ring-4 ring-brand-soft/20' : 'border-edge-strong bg-panel text-ink-3'" aria-hidden="true">{{ badge.threshold.toLocaleString('en-US', { notation: 'compact', maximumFractionDigits: 0 }) }}</span>
        <p class="m-0 flex min-h-8 items-center text-xs font-semibold leading-snug" :class="badge.unlocked ? 'text-ink' : 'text-ink-3'">{{ badge.label }}</p>
        <p class="m-0 mt-1 text-[11px] text-ink-4">{{ badge.threshold.toLocaleString('en-US') }} titles requested</p>
        <span class="mt-2 inline-flex items-center gap-1.5 text-[10px] font-semibold" :class="badge.unlocked ? 'text-brand-ink' : isNext(badge) ? 'text-ink-2' : 'text-ink-4'"><i aria-hidden="true" :class="badge.unlocked ? 'fas fa-check' : isNext(badge) ? 'fas fa-arrow-right' : 'fas fa-lock'"></i>{{ badge.unlocked ? 'Unlocked' : isNext(badge) ? 'Next milestone' : 'Locked' }}</span>
        <progress v-if="isNext(badge)" class="absolute inset-x-0 bottom-0 block h-1 w-full appearance-none overflow-hidden border-0 bg-raised [&::-webkit-progress-bar]:bg-raised [&::-webkit-progress-value]:bg-brand [&::-moz-progress-bar]:bg-brand" :value="recap.total" :max="badge.threshold" :aria-label="`Progress toward ${badge.label}`"></progress>
      </li>
    </ul>
    <div v-for="badge in anniversaryBadges" :key="badge.id" class="mt-4 flex items-center gap-3 rounded-card border p-4" :class="badge.unlocked ? 'border-brand-ink/20 bg-brand-soft/20' : 'border-edge bg-canvas/30'">
      <span aria-hidden="true" class="grid h-12 w-12 shrink-0 place-items-center rounded-full border text-sm font-bold" :class="badge.unlocked ? 'border-brand-ink/25 bg-brand-soft text-brand-ink' : 'border-edge-strong bg-panel text-ink-3'">1 yr</span>
      <div class="min-w-0 flex-1">
        <p class="m-0 text-xs font-semibold text-ink">{{ badge.label }}</p>
        <p class="m-0 mt-1 text-[11px] leading-relaxed text-ink-4">{{ badge.threshold }} days since your first recorded request</p>
      </div>
      <span class="text-[10px] font-semibold" :class="badge.unlocked ? 'text-brand-ink' : 'text-ink-4'">{{ badge.unlocked ? 'Unlocked' : 'Locked' }}</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'RecapBadges',
  props: { recap: { type: Object, required: true } },
  computed: {
    titleBadges() { return this.recap.badges.filter(badge => badge.kind === 'titles'); },
    anniversaryBadges() { return this.recap.badges.filter(badge => badge.kind === 'days'); },
    unlockedCount() { return this.recap.badges.filter(badge => badge.unlocked).length; },
  },
  methods: { isNext(badge) { return !badge.unlocked && badge.threshold === this.recap.next_badge?.threshold; } },
};
</script>
