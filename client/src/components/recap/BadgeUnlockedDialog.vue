<template>
  <AppDialog title="Badge unlocked" icon="fas fa-award" width="max-w-4xl" class="sm:w-[calc(100%-4rem)]" body-class="grid min-h-0 p-0 sm:grid-cols-[minmax(0,1fr)_360px]" @close="$emit('close')">
    <!-- Fixed inside the top-layer dialog, so the burst covers the whole viewport without blocking clicks. -->
    <canvas ref="confetti" aria-hidden="true" class="pointer-events-none fixed inset-0 z-10 h-dvh w-screen"></canvas>
    <div class="relative flex min-h-0 min-w-0 items-center justify-center bg-radial-[at_50%_35%] from-brand-soft/35 via-canvas/60 to-canvas p-4 sm:p-8" :aria-busy="rendering">
      <canvas ref="card" width="1080" height="1350" role="img" :aria-label="`${badge.label}. ${badge.description}.`" class="block h-auto max-h-[min(60dvh,36rem)] w-auto max-w-full rounded-card object-contain shadow-2xl shadow-black/40"></canvas>
      <span v-if="rendering" role="status" class="absolute inset-0 grid place-items-center bg-canvas/80 text-sm text-ink-3 backdrop-blur-sm"><span><i aria-hidden="true" class="fas fa-spinner fa-spin mr-2"></i>Creating your badge…</span></span>
    </div>

    <div class="flex min-h-0 min-w-0 flex-col gap-5 overflow-y-auto overscroll-contain border-t border-edge p-4 sm:border-l sm:border-t-0 sm:p-6">
      <div>
        <p class="m-0 text-[11px] font-semibold uppercase tracking-widest text-brand-ink">Congratulations!</p>
        <h3 class="m-0 mt-1 text-xl font-bold leading-snug text-ink">{{ badge.label }}</h3>
        <p class="m-0 mt-1 text-sm text-ink-3">{{ badge.description }}<template v-if="badge.unlocked_at"> · {{ unlockedOn }}</template></p>
      </div>
      <div v-if="badges.length > 1">
        <p class="m-0 mb-2 text-xs font-semibold text-ink-3">{{ badges.length }} new badges since your last visit</p>
        <div class="flex flex-wrap gap-2" role="group" aria-label="New badges">
          <button v-for="(item, i) in badges" :key="item.id" type="button" class="cursor-pointer rounded-full border px-3 py-1 text-xs font-semibold transition-colors" :class="i === selected ? 'border-brand-ink/50 bg-brand-soft/50 text-brand-ink' : 'border-edge bg-panel-2 text-ink-3 hover:border-edge-strong hover:text-ink'" :aria-pressed="i === selected" @click="select(i)">{{ item.label }}</button>
        </div>
      </div>
      <p v-if="error" role="alert" class="ui-alert-bad m-0">{{ error }} <button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-brand-ink underline" @click="render">Try again</button></p>
      <RecapShareActions :key="badge.id" :blob="blob" :filename="`suggestarr-badge-${badge.id}.png`" :caption="caption" :share-title="`Badge unlocked: ${badge.label}`" :disabled="rendering || !blob" />
      <div class="rounded-card border border-brand-ink/20 bg-brand-soft/20 p-4">
        <p class="m-0 text-sm font-semibold text-ink"><i aria-hidden="true" class="far fa-heart mr-2 text-brand-ink"></i>Celebrate with SuggestArr</p>
        <p class="m-0 mt-1 text-xs leading-relaxed text-ink-3">SuggestArr is built in spare time. If this milestone made you smile, a small contribution or a GitHub star helps it keep growing.</p>
        <button type="button" class="ui-btn mt-3 w-full border-brand-ink/25 bg-brand-soft/40 text-brand-ink hover:border-brand-ink/60 hover:bg-brand-soft/60" @click="$emit('support')"><i aria-hidden="true" class="fas fa-heart"></i>Support SuggestArr</button>
      </div>
      <button type="button" class="mt-auto inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-ctl border-0 bg-transparent px-3 text-xs font-medium text-ink-3 hover:bg-raised hover:text-brand-ink" @click="$emit('show-badges')"><i aria-hidden="true" class="fas fa-th-large"></i>See all your badges</button>
    </div>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import RecapShareActions from './RecapShareActions.vue';
import logoUrl from '@/assets/logo.png';
import { canvasBlob } from '@/utils/recapCanvas.js';
import { badgeCaption, renderBadgeCard } from '@/utils/badgeCanvas.js';
import { formatBadgeDate } from '@/utils/recapBadges.js';
import { launchConfetti } from '@/utils/confetti.js';

export default {
  name: 'BadgeUnlockedDialog',
  components: { AppDialog, RecapShareActions },
  props: { badges: { type: Array, required: true } },
  emits: ['close', 'support', 'show-badges'],
  data: () => ({ selected: 0, rendering: true, blob: null, error: '', active: true, stopConfetti: null, generation: 0 }),
  computed: {
    badge() { return this.badges[this.selected]; },
    caption() { return badgeCaption(this.badge); },
    unlockedOn() { return `Unlocked ${formatBadgeDate(this.badge.unlocked_at)}`; },
  },
  mounted() {
    this.render();
    // Wait for the dialog to be laid out so the overlay has its viewport size.
    requestAnimationFrame(() => { if (this.active) this.stopConfetti = launchConfetti(this.$refs.confetti); });
  },
  beforeUnmount() {
    this.active = false;
    this.stopConfetti?.();
  },
  methods: {
    select(index) {
      this.selected = index;
      this.render();
    },
    async render() {
      const generation = ++this.generation;
      this.rendering = true;
      this.error = '';
      this.blob = null;
      try {
        await renderBadgeCard(this.$refs.card, this.badge, { logoUrl });
        const blob = await canvasBlob(this.$refs.card);
        if (this.active && generation === this.generation) this.blob = blob;
      } catch { if (generation === this.generation) this.error = 'Unable to create the badge image.'; }
      finally { if (generation === this.generation) this.rendering = false; }
    },
  },
};
</script>
