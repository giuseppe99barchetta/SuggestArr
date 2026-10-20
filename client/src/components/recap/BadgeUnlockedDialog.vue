<template>
  <AppDialog ref="dialog" :labelledby="titleId" width="max-w-xl" @close="$emit('close')">
    <!-- Fixed inside the top-layer dialog, so the burst covers the whole viewport without blocking clicks. -->
    <canvas ref="confetti" aria-hidden="true" class="pointer-events-none fixed inset-0 z-20 h-dvh w-screen"></canvas>
    <!-- The shareable PNG is rendered off-screen; the badge itself is the visual. -->
    <canvas ref="card" width="1080" height="1350" class="hidden"></canvas>

    <div class="relative overflow-hidden bg-radial-[at_50%_30%] from-brand-soft/45 via-panel to-panel px-6 pb-6 pt-10 text-center max-sm:px-4">
      <button type="button" class="absolute right-3 top-3 z-10 grid h-10 w-10 cursor-pointer place-items-center rounded-ctl border-0 bg-transparent text-ink-4 transition-colors hover:bg-raised hover:text-ink" aria-label="Close" @click="$refs.dialog.close()"><i aria-hidden="true" class="fas fa-times"></i></button>
      <h2 :id="titleId" class="m-0 text-[11px] font-semibold uppercase tracking-[0.3em] text-brand-ink">Badge unlocked</h2>

      <div :key="badge.id" class="relative mx-auto mt-6 grid h-56 w-56 place-items-center motion-safe:animate-pop sm:h-64 sm:w-64" aria-hidden="true">
        <span class="absolute inset-0 rounded-full bg-[repeating-conic-gradient(var(--color-brand)_0deg_6deg,transparent_6deg_18deg)] opacity-40 [mask-image:radial-gradient(circle,transparent_55%,black_56%,black_70%,transparent_71%)] motion-safe:animate-[spin_24s_linear_infinite]"></span>
        <span class="absolute inset-8 rounded-full bg-brand/40 blur-2xl motion-safe:animate-pulse"></span>
        <span class="relative grid h-40 w-40 place-items-center rounded-full border-4 border-brand-ink bg-linear-to-br from-brand-soft to-panel shadow-2xl shadow-brand/40 ring-8 ring-brand-soft/30 sm:h-44 sm:w-44">
          <i v-if="medallion.icon" :class="medallion.icon" class="text-6xl text-brand-ink"></i>
          <span v-else class="leading-none text-brand-ink">
            <span class="block text-6xl font-extrabold tracking-tight">{{ medallion.text }}</span>
            <span class="mt-2 block text-xs font-bold uppercase tracking-widest opacity-80">{{ medallion.unit }}</span>
          </span>
        </span>
      </div>

      <p class="m-0 mt-6 text-sm font-semibold text-ink-3">Congratulations!</p>
      <h3 class="m-0 mt-1 text-3xl font-extrabold leading-tight tracking-tight text-ink sm:text-4xl">{{ badge.label }}</h3>
      <p class="m-0 mt-2 text-sm text-ink-2">{{ badge.description }}</p>
      <p v-if="badge.unlocked_at" class="m-0 mt-1 text-xs text-ink-4">{{ unlockedOn }}</p>

      <div v-if="badges.length > 1" class="mt-5">
        <p class="m-0 mb-2 text-xs font-semibold text-ink-3">{{ badges.length }} new badges since your last visit</p>
        <div class="flex flex-wrap justify-center gap-2" role="group" aria-label="New badges">
          <button v-for="(item, i) in badges" :key="item.id" type="button" class="cursor-pointer rounded-full border px-3 py-1 text-xs font-semibold transition-colors" :class="i === selected ? 'border-brand-ink/50 bg-brand-soft/50 text-brand-ink' : 'border-edge bg-panel-2 text-ink-3 hover:border-edge-strong hover:text-ink'" :aria-pressed="i === selected" @click="select(i)">{{ item.label }}</button>
        </div>
      </div>

      <div class="mx-auto mt-6 grid max-w-md gap-2 whitespace-nowrap sm:grid-cols-2">
        <button type="button" class="ui-btn justify-center border-brand bg-brand text-white hover:bg-brand/90" :aria-expanded="sharing" @click="sharing = !sharing"><i aria-hidden="true" class="fas fa-share-alt"></i>Share badge</button>
        <button type="button" class="ui-btn justify-center border-brand-ink/25 bg-brand-soft/40 text-brand-ink hover:border-brand-ink/60 hover:bg-brand-soft/60" @click="$emit('support')"><i aria-hidden="true" class="fas fa-heart"></i>Support SuggestArr</button>
      </div>
      <p class="m-0 mx-auto mt-3 max-w-sm text-xs leading-relaxed text-ink-4">SuggestArr is built in spare time. If this milestone made you smile, a small contribution or a GitHub star helps it keep growing.</p>
    </div>

    <div v-if="sharing" class="border-t border-edge p-6 text-left max-sm:p-4">
      <p v-if="error" role="alert" class="ui-alert-bad m-0 mb-4">{{ error }} <button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-brand-ink underline" @click="render">Try again</button></p>
      <div class="grid gap-5 sm:grid-cols-[140px_minmax(0,1fr)]">
        <img v-if="previewUrl" :src="previewUrl" :alt="`${badge.label} badge image`" class="mx-auto block w-36 rounded-card shadow-xl shadow-black/40 sm:w-full">
        <RecapShareActions :key="badge.id" :blob="blob" :filename="`suggestarr-badge-${badge.id}.png`" :caption="caption" :share-title="`Badge unlocked: ${badge.label}`" :disabled="rendering || !blob" />
      </div>
    </div>

    <div class="border-t border-edge px-6 py-3 text-center">
      <button type="button" class="inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-ctl border-0 bg-transparent px-3 text-xs font-medium text-ink-3 hover:bg-raised hover:text-brand-ink" @click="$emit('show-badges')"><i aria-hidden="true" class="fas fa-th-large"></i>See all your badges</button>
    </div>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import RecapShareActions from './RecapShareActions.vue';
import logoUrl from '@/assets/logo.png';
import { canvasBlob } from '@/utils/recapCanvas.js';
import { badgeCaption, renderBadgeCard } from '@/utils/badgeCanvas.js';
import { badgeMedallion, formatBadgeDate } from '@/utils/recapBadges.js';
import { launchConfetti } from '@/utils/confetti.js';

let nextId = 0;

export default {
  name: 'BadgeUnlockedDialog',
  components: { AppDialog, RecapShareActions },
  props: { badges: { type: Array, required: true } },
  emits: ['close', 'support', 'show-badges'],
  data: () => ({ selected: 0, sharing: false, rendering: true, blob: null, previewUrl: '', error: '', active: true,
    stopConfetti: null, generation: 0, titleId: `badge-unlocked-${++nextId}` }),
  computed: {
    badge() { return this.badges[this.selected]; },
    medallion() { return badgeMedallion(this.badge); },
    caption() { return badgeCaption(this.badge); },
    unlockedOn() { return `Unlocked ${formatBadgeDate(this.badge.unlocked_at)}`; },
  },
  mounted() {
    this.render();
    // Wait for the dialog to be laid out so the overlay has its viewport size.
    requestAnimationFrame(() => this.celebrate());
  },
  beforeUnmount() {
    this.active = false;
    this.stopConfetti?.();
    if (this.previewUrl) URL.revokeObjectURL(this.previewUrl);
  },
  methods: {
    celebrate() {
      if (!this.active) return;
      this.stopConfetti?.();
      this.stopConfetti = launchConfetti(this.$refs.confetti);
    },
    select(index) {
      this.selected = index;
      this.render();
      this.celebrate();
    },
    async render() {
      const generation = ++this.generation;
      this.rendering = true;
      this.error = '';
      this.blob = null;
      try {
        await renderBadgeCard(this.$refs.card, this.badge, { logoUrl });
        const blob = await canvasBlob(this.$refs.card);
        if (!this.active || generation !== this.generation) return;
        if (this.previewUrl) URL.revokeObjectURL(this.previewUrl);
        this.blob = blob;
        this.previewUrl = URL.createObjectURL(blob);
      } catch { if (generation === this.generation) this.error = 'Unable to create the badge image.'; }
      finally { if (generation === this.generation) this.rendering = false; }
    },
  },
};
</script>
