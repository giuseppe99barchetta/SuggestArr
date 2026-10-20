<template>
  <AppDialog ref="dialog" :labelledby="titleId" width="max-w-6xl" class="h-[calc(100dvh-2rem)] sm:h-[min(80dvh,52rem)] sm:w-[calc(100%-4rem)]" @close="$emit('close')">
    <div class="grid h-full min-h-0 grid-rows-[minmax(0,1fr)_minmax(0,38%)] sm:grid-cols-[minmax(0,1fr)_320px] sm:grid-rows-1">
      <!-- The recap image is the stage; everything else is secondary. -->
      <div class="relative grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)_auto] justify-items-center gap-3 bg-radial-[at_50%_40%] from-brand-soft/45 via-canvas/70 to-canvas px-4 pb-4 pt-3 sm:px-8 sm:pb-6 sm:pt-5" :aria-busy="rendering">
        <div class="flex w-full items-center justify-between gap-3">
          <h2 :id="titleId" class="m-0 inline-flex items-center gap-2 text-sm font-bold text-ink"><i aria-hidden="true" class="fas fa-image text-brand-ink"></i>Your SuggestArr recap</h2>
          <button type="button" class="-mr-2 grid h-10 w-10 shrink-0 cursor-pointer place-items-center rounded-ctl border-0 bg-transparent text-ink-3 hover:bg-raised hover:text-ink" aria-label="Close" @click="$refs.dialog.close()"><i aria-hidden="true" class="fas fa-times"></i></button>
        </div>
        <div class="relative flex min-h-0 w-full items-center justify-center">
          <canvas ref="canvas" width="1080" height="1350" role="img" :aria-label="caption" class="block h-auto max-h-full w-auto max-w-full rounded-card object-contain shadow-2xl shadow-black/50 ring-1 ring-white/5"></canvas>
          <span v-if="rendering" role="status" class="absolute inset-0 grid place-items-center text-sm text-ink-3"><span class="rounded-full bg-canvas/80 px-4 py-2 backdrop-blur-sm"><i aria-hidden="true" class="fas fa-spinner fa-spin mr-2"></i>Creating your recap…</span></span>
        </div>
        <div class="flex flex-col items-center gap-2">
          <BaseCheckbox v-model="includePosters" :disabled="rendering" label="Show top-title covers" />
          <p v-if="warning" role="status" class="m-0 rounded-ctl border border-caution/30 bg-caution/10 px-3 py-1.5 text-center text-xs leading-relaxed text-ink-2">{{ warning }}</p>
          <p v-if="error" role="alert" class="ui-alert-bad m-0">{{ error }} <button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-brand-ink underline" @click="render">Try again</button></p>
        </div>
      </div>

      <div class="flex min-h-0 min-w-0 flex-col gap-5 overflow-y-auto overscroll-contain border-t border-edge p-4 sm:border-l sm:border-t-0 sm:p-5">
        <RecapShareActions :blob="blob" filename="suggestarr-recap.png" :caption="caption" :share-title="shareTitle" :disabled="rendering || !ready" />
        <button type="button" class="mt-auto flex w-full cursor-pointer items-center gap-3 rounded-card border border-edge bg-panel-2 p-3 text-left transition-colors hover:border-brand-ink/40 hover:bg-raised" @click="$emit('show-badges')">
          <BadgeMedallion v-if="latest" :badge="latest" size="sm" />
          <span class="min-w-0 flex-1">
            <span class="block text-[13px] font-semibold text-ink">Badges · {{ unlockedBadges }} / {{ recap.badges.length }} unlocked</span>
            <span v-if="latest" class="block truncate text-[11px] text-ink-4">Latest: {{ latest.label }}</span>
          </span>
          <i aria-hidden="true" class="fas fa-chevron-right text-[10px] text-ink-4"></i>
        </button>
        <p class="m-0 flex items-center gap-2 text-[11px] text-ink-4"><i aria-hidden="true" class="fas fa-lock text-[10px]"></i>Made on your device. Server details stay private.</p>
      </div>
    </div>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import BadgeMedallion from './BadgeMedallion.vue';
import RecapShareActions from './RecapShareActions.vue';
import logoUrl from '@/assets/logo.png';
import { getRecap } from '@/api/recapApi.js';
import { canvasBlob, recapCaption, renderRecap } from '@/utils/recapCanvas.js';
import { latestBadge } from '@/utils/recapBadges.js';

let nextId = 0;

export default {
  name: 'RecapDialog',
  components: { AppDialog, BadgeMedallion, BaseCheckbox, RecapShareActions },
  props: { recap: { type: Object, required: true } },
  emits: ['close', 'show-badges'],
  data: () => ({
    includePosters: true, rendering: true, ready: false, warning: '', error: '', blob: null, active: true,
    featuredPosters: [], postersLoaded: false, titleId: `recap-dialog-${++nextId}`,
  }),
  computed: {
    caption() { return recapCaption(this.recap); },
    shareTitle() { return `${this.recap.total.toLocaleString('en-US')} titles requested with SuggestArr`; },
    unlockedBadges() { return this.recap.badges.filter(badge => badge.unlocked).length; },
    latest() { return latestBadge(this.recap.badges); },
  },
  watch: {
    includePosters() { this.render(); },
  },
  mounted() {
    this.render();
  },
  beforeUnmount() {
    this.active = false;
  },
  methods: {
    async render() {
      this.rendering = true;
      this.ready = false;
      this.error = '';
      this.warning = '';
      try {
        if (this.includePosters && !this.postersLoaded) {
          try {
            this.featuredPosters = (await getRecap(true)).posters.slice(0, 4);
            this.postersLoaded = true;
          }
          catch { this.warning = 'Posters could not be loaded. Your statistics are still available.'; }
        }
        const data = { ...this.recap, posters: this.featuredPosters };
        if (!this.active) return;
        const result = await renderRecap(this.$refs.canvas, data, { logoUrl, includePosters: this.includePosters });
        if (!this.active) return;
        if (result.missingPosters) this.warning = 'Some covers could not be loaded. Their places use illustrated cards.';
        else if (this.includePosters && !data.posters.length) this.warning ||= 'No cover artwork is available. Your recap uses an illustrated fan.';
        this.blob = await canvasBlob(this.$refs.canvas);
        if (!this.active) return;
        this.ready = true;
      } catch { this.error = 'Unable to create your recap. Try again or turn off posters.'; }
      finally { this.rendering = false; }
    },
  },
};
</script>
