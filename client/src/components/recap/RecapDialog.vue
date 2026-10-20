<template>
  <!-- Same player as the year recap: the image over a blurred backdrop, controls below, sharing in a side panel. -->
  <dialog ref="dialog" :aria-labelledby="titleId" class="m-0 h-dvh max-h-none w-screen max-w-none overflow-hidden border-0 bg-transparent p-0 text-white outline-none backdrop:bg-black/75 backdrop:backdrop-blur-xl open:flex" @cancel="onCancel" @close="$emit('close')">
    <div class="relative flex min-h-0 min-w-0 flex-1 flex-col items-center gap-3 px-4 pb-4 pt-3" @click.self="dismiss">
      <header class="flex w-full items-center justify-between gap-3">
        <h2 :id="titleId" class="m-0 truncate text-sm font-bold">Your SuggestArr recap</h2>
        <button type="button" :class="glassButton" aria-label="Close" @click="close"><i aria-hidden="true" class="fas fa-times"></i></button>
      </header>

      <div class="relative flex min-h-0 w-full flex-1 items-center justify-center" :aria-busy="rendering" @click.self="dismiss">
        <canvas ref="canvas" width="1080" height="1350" role="img" :aria-label="caption" class="block h-auto max-h-full w-auto max-w-full rounded-card object-contain shadow-2xl shadow-black/60"></canvas>
        <span v-if="rendering" role="status" class="absolute inset-0 grid place-items-center text-sm"><span class="rounded-full bg-black/60 px-4 py-2 backdrop-blur-sm"><i aria-hidden="true" class="fas fa-spinner fa-spin mr-2"></i>Creating your recap…</span></span>
      </div>

      <p v-if="warning" role="status" class="m-0 max-w-xl text-center text-xs text-white/70">{{ warning }}</p>
      <p v-if="error" role="alert" class="m-0 max-w-xl rounded-ctl bg-bad/20 px-3 py-2 text-center text-xs">{{ error }} <button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-white underline" @click="render">Try again</button></p>

      <div class="flex w-full max-w-2xl flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <label class="inline-flex h-10 cursor-pointer items-center gap-2 rounded-full bg-white/10 px-4 text-xs font-semibold transition-colors hover:bg-white/20 has-disabled:cursor-default has-disabled:opacity-50">
            <input v-model="includePosters" type="checkbox" class="h-4 w-4 cursor-pointer accent-brand" :disabled="rendering"><i aria-hidden="true" class="fas fa-images sm:hidden"></i><span class="max-sm:sr-only">Show top-title covers</span>
          </label>
          <button type="button" class="inline-flex h-10 cursor-pointer items-center gap-2 rounded-full border-0 bg-white/10 py-0 pl-1 pr-4 text-xs font-semibold text-white transition-colors hover:bg-white/20" :aria-label="`Badges · ${unlockedBadges} / ${recap.badges.length} unlocked`" @click="$emit('show-badges')">
            <BadgeMedallion v-if="latest" :badge="latest" size="xs" />
            <i v-else aria-hidden="true" class="fas fa-award ml-3"></i>
            <span aria-hidden="true">{{ unlockedBadges }} / {{ recap.badges.length }}</span>
          </button>
        </div>
        <div class="flex items-center gap-2">
          <button type="button" class="inline-flex h-10 cursor-pointer items-center gap-2 rounded-full border-0 bg-brand px-5 text-sm font-semibold text-white transition-colors hover:bg-brand/90 disabled:cursor-default disabled:opacity-50" :disabled="!ready" @click="download"><i aria-hidden="true" class="fas fa-download"></i>Download PNG</button>
          <button type="button" :class="[glassButton, panel ? 'bg-white/25' : '']" aria-label="Share recap" :aria-expanded="panel" @click="panel = !panel"><i aria-hidden="true" class="fas fa-share-alt"></i></button>
        </div>
      </div>
      <p class="m-0 flex items-center gap-2 text-[11px] text-white/50"><i aria-hidden="true" class="fas fa-lock text-[10px]"></i>Made on your device. Server details stay private.</p>
    </div>

    <Transition enter-from-class="max-md:translate-y-full md:translate-x-full" leave-to-class="max-md:translate-y-full md:translate-x-full" enter-active-class="transition-transform duration-200 ease-out motion-reduce:transition-none" leave-active-class="transition-transform duration-150 ease-in motion-reduce:transition-none">
      <aside v-if="panel" aria-label="Share" class="flex min-h-0 flex-col overflow-hidden bg-panel text-ink shadow-2xl max-md:absolute max-md:inset-x-0 max-md:bottom-0 max-md:max-h-[75dvh] max-md:rounded-t-card md:w-[360px] md:shrink-0 md:border-l md:border-edge">
        <header class="flex shrink-0 items-center justify-between gap-3 px-5 pb-2 pt-4">
          <h3 class="m-0 text-base font-bold">Share</h3>
          <button type="button" class="-mr-2 grid h-9 w-9 cursor-pointer place-items-center rounded-[8px] border-0 bg-transparent text-ink-3 hover:bg-raised hover:text-ink" aria-label="Close share" @click="panel = false"><i aria-hidden="true" class="fas fa-times"></i></button>
        </header>
        <div class="min-h-0 overflow-y-auto overscroll-contain px-5 pb-5 pt-2">
          <RecapShareActions :blob="blob" filename="suggestarr-recap.png" :caption="caption" :share-title="shareTitle" :disabled="rendering || !ready" hide-download />
        </div>
      </aside>
    </Transition>
  </dialog>
</template>

<script>
import BadgeMedallion from './BadgeMedallion.vue';
import RecapShareActions from './RecapShareActions.vue';
import logoUrl from '@/assets/logo.png';
import { getRecap } from '@/api/recapApi.js';
import { canvasBlob, recapCaption, renderRecap } from '@/utils/recapCanvas.js';
import { latestBadge } from '@/utils/recapBadges.js';

const GLASS_BUTTON = 'grid h-10 w-10 shrink-0 cursor-pointer place-items-center rounded-full border-0 bg-white/10 text-white transition-colors hover:bg-white/20';

let nextId = 0;

export default {
  name: 'RecapDialog',
  components: { BadgeMedallion, RecapShareActions },
  props: { recap: { type: Object, required: true } },
  emits: ['close', 'show-badges'],
  data: () => ({
    includePosters: true, rendering: true, ready: false, warning: '', error: '', blob: null, active: true,
    featuredPosters: [], postersLoaded: false, panel: false, titleId: `recap-dialog-${++nextId}`, glassButton: GLASS_BUTTON,
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
    this.$refs.dialog.showModal();
    this.render();
  },
  beforeUnmount() {
    this.active = false;
  },
  methods: {
    close() { this.$refs.dialog.close(); },
    /** Clicking the backdrop closes an open panel first, then the player. */
    dismiss() { if (this.panel) this.panel = false; else this.close(); },
    onCancel(event) {
      // Escape closes an open panel before closing the player.
      if (!this.panel) return;
      event.preventDefault();
      this.panel = false;
    },
    download() {
      if (!this.blob) return;
      const url = URL.createObjectURL(this.blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'suggestarr-recap.png';
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
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
