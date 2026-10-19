<template>
  <AppDialog title="Your SuggestArr recap" icon="fas fa-image" width="max-w-4xl" class="h-[calc(100dvh-2rem)] sm:h-[min(80dvh,52rem)] sm:w-[calc(100%-4rem)]" body-class="grid min-h-0 grid-rows-[minmax(0,1fr)_minmax(0,48%)] p-0 sm:grid-cols-[minmax(0,1fr)_340px] sm:grid-rows-1" @close="$emit('close')">
    <div class="relative flex min-h-0 min-w-0 items-center justify-center bg-radial-[at_50%_35%] from-brand-soft/35 via-canvas/60 to-canvas p-4 sm:p-8" :aria-busy="rendering">
      <canvas ref="canvas" width="1080" height="1350" role="img" :aria-label="caption" class="block h-auto max-h-full w-auto max-w-full rounded-card object-contain shadow-2xl shadow-black/40"></canvas>
      <span v-if="rendering" role="status" class="absolute inset-0 grid place-items-center bg-canvas/80 text-sm text-ink-3 backdrop-blur-sm"><span><i aria-hidden="true" class="fas fa-spinner fa-spin mr-2"></i>Creating your recap…</span></span>
    </div>

    <div class="flex min-h-0 min-w-0 flex-col gap-6 overflow-y-auto overscroll-contain border-t border-edge p-4 sm:border-l sm:border-t-0 sm:p-6">
      <div class="flex flex-col gap-3">
        <BaseCheckbox v-model="includePosters" :disabled="rendering" label="Show top-title covers" />
        <p v-if="warning" role="status" class="m-0 rounded-ctl border border-caution/30 bg-caution/10 px-3 py-2 text-xs leading-relaxed text-ink-2">{{ warning }}</p>
        <p v-if="error" role="alert" class="ui-alert-bad m-0">{{ error }} <button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-brand-ink underline" @click="render">Try again</button></p>
      </div>
      <RecapShareActions :blob="blob" filename="suggestarr-recap.png" :caption="caption" :share-title="shareTitle" :disabled="rendering || !ready" />
      <div class="mt-auto flex flex-col gap-3 border-t border-edge pt-4">
        <details class="group">
          <summary class="flex cursor-pointer list-none items-center justify-between gap-2 rounded-ctl text-[13px] font-semibold text-ink-2 hover:text-ink [&::-webkit-details-marker]:hidden">
            <span class="inline-flex items-center gap-2"><i aria-hidden="true" class="fas fa-award text-brand-ink"></i>Badges · {{ unlockedBadges }} / {{ recap.badges.length }} unlocked</span>
            <i aria-hidden="true" class="fas fa-chevron-down text-[10px] text-ink-4 transition-transform group-open:rotate-180"></i>
          </summary>
          <RecapBadges class="mt-4" :recap="recap" />
        </details>
        <p class="m-0 flex items-center gap-2 text-[11px] text-ink-4"><i aria-hidden="true" class="fas fa-lock text-[10px]"></i>Made on your device. Server details stay private.</p>
      </div>
    </div>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import RecapBadges from './RecapBadges.vue';
import RecapShareActions from './RecapShareActions.vue';
import logoUrl from '@/assets/logo.png';
import { getRecap } from '@/api/recapApi.js';
import { canvasBlob, recapCaption, renderRecap } from '@/utils/recapCanvas.js';

export default {
  name: 'RecapDialog',
  components: { AppDialog, BaseCheckbox, RecapBadges, RecapShareActions },
  props: { recap: { type: Object, required: true } },
  emits: ['close'],
  data: () => ({
    includePosters: true, rendering: true, ready: false, warning: '', error: '', blob: null, active: true,
    featuredPosters: [], postersLoaded: false,
  }),
  computed: {
    caption() { return recapCaption(this.recap); },
    shareTitle() { return `${this.recap.total.toLocaleString('en-US')} titles requested with SuggestArr`; },
    unlockedBadges() { return this.recap.badges.filter(badge => badge.unlocked).length; },
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
