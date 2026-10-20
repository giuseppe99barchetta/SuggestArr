<template>
  <!-- Full-viewport story viewer: the page stays visible behind a blurred backdrop.
       Native <dialog> keeps focus trapping, Escape and top-layer stacking. -->
  <dialog ref="dialog" :aria-labelledby="titleId" class="m-0 h-dvh max-h-none w-screen max-w-none overflow-hidden border-0 bg-transparent p-0 text-white outline-none backdrop:bg-black/75 backdrop:backdrop-blur-xl open:flex" @cancel="onCancel" @close="$emit('close')">
    <div class="relative flex min-h-0 min-w-0 flex-1 flex-col items-center gap-3 px-4 pb-4 pt-3" @click.self="dismiss">
      <header class="flex w-full items-center justify-between gap-3">
        <div class="min-w-0">
          <h2 :id="titleId" class="m-0 truncate text-sm font-bold">{{ displayYear }} Year recap</h2>
          <p class="m-0 text-xs text-white/60">{{ mode === 'demo' ? 'Sample data' : 'Recorded progress' }}</p>
        </div>
        <button type="button" :class="glassButton" aria-label="Close" @click="close"><i aria-hidden="true" class="fas fa-times"></i></button>
      </header>

      <div class="flex h-2 min-w-32 max-w-full shrink-0 gap-1" :style="{ width: frameStyle.width }" aria-label="Story progress">
        <button v-for="(item, i) in stories" :key="item.id" type="button" class="h-1 min-w-0 flex-1 cursor-pointer self-center overflow-hidden rounded-full border-0 bg-white/25 p-0" :aria-label="`Go to story ${i + 1}: ${item.title}`" :aria-current="i === index ? 'step' : null" @click="go(i)">
          <span class="block h-full bg-white" :style="{ width: `${i < index ? 100 : i === index ? progress : 0}%` }"></span>
        </button>
      </div>

      <div ref="stage" class="relative grid min-h-0 w-full min-w-0 flex-1 place-items-center" @click.self="dismiss">
        <!-- Tap the left third to go back and the rest to advance; press and hold to pause. -->
        <div class="group relative cursor-pointer touch-pan-y select-none overflow-hidden rounded-card bg-panel shadow-2xl shadow-black/50" :style="frameStyle" :aria-busy="rendering" @click="tap" @pointerdown="holdStart" @pointerup="holdEnd" @pointercancel="holdCancel" @pointerleave="holdCancel" @contextmenu.prevent @touchstart.passive="touchStart" @touchend.passive="touchEnd">
          <canvas ref="canvas" width="1080" height="1920" tabindex="0" role="img" :aria-label="description" class="block h-full w-full"></canvas>
          <div v-if="rendering || loading || !data" class="absolute inset-0 grid place-items-center bg-canvas/90 p-3 text-center text-sm text-ink-3" role="status">{{ loading ? 'Loading recorded progress…' : !data ? 'Choose sample data or try again.' : 'Creating your story…' }}</div>
        </div>
      </div>

      <h3 class="sr-only">{{ story.title }}</h3>
      <span class="sr-only" aria-live="polite">Story {{ index + 1 }} of {{ stories.length }}</span>
      <p v-if="notice" role="status" class="m-0 max-w-full text-center text-xs text-white/70" :style="{ width: frameStyle.width }">{{ notice }}</p>
      <p v-if="error" role="alert" class="m-0 max-w-full rounded-ctl bg-bad/20 px-3 py-2 text-center text-xs" :style="{ width: frameStyle.width }">{{ error }} <button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-white underline" @click="retry">Try again</button></p>

      <div class="flex min-w-72 max-w-full shrink-0 items-center justify-between gap-2" :style="{ width: frameStyle.width }">
        <button type="button" :class="[glassButton, panel === 'options' ? 'bg-white/25' : '']" aria-label="Recap options" :aria-expanded="panel === 'options'" @click="toggle('options')"><i aria-hidden="true" class="fas fa-sliders-h"></i></button>
        <div class="flex items-center gap-2">
          <button type="button" :class="glassButton" :disabled="index === 0" aria-label="Previous story" @click="go(index - 1)"><i aria-hidden="true" class="fas fa-chevron-left"></i></button>
          <button type="button" :class="glassButton" :aria-label="paused ? 'Play stories' : 'Pause stories'" @click="togglePlayback"><i aria-hidden="true" :class="paused ? 'fas fa-play' : 'fas fa-pause'"></i></button>
          <button type="button" :class="glassButton" :disabled="index === stories.length - 1" aria-label="Next story" @click="go(index + 1)"><i aria-hidden="true" class="fas fa-chevron-right"></i></button>
        </div>
        <div class="flex items-center gap-2">
          <button type="button" :class="glassButton" :disabled="!ready || rendering || !blob" aria-label="Download this story" @click="download"><i aria-hidden="true" class="fas fa-download"></i></button>
          <button type="button" :class="[glassButton, panel === 'share' ? 'bg-white/25' : '']" aria-label="Share this story" :aria-expanded="panel === 'share'" @click="toggle('share')"><i aria-hidden="true" class="fas fa-share-alt"></i></button>
        </div>
      </div>
    </div>

    <Transition enter-from-class="max-md:translate-y-full md:translate-x-full" leave-to-class="max-md:translate-y-full md:translate-x-full" enter-active-class="transition-transform duration-200 ease-out motion-reduce:transition-none" leave-active-class="transition-transform duration-150 ease-in motion-reduce:transition-none">
      <aside v-if="panel" :aria-label="panel === 'share' ? 'Share' : 'Recap options'" class="flex min-h-0 flex-col overflow-hidden bg-panel text-ink shadow-2xl max-md:absolute max-md:inset-x-0 max-md:bottom-0 max-md:max-h-[75dvh] max-md:rounded-t-card md:w-[360px] md:shrink-0 md:border-l md:border-edge">
        <header class="flex shrink-0 items-center justify-between gap-3 px-5 pb-2 pt-4">
          <h3 class="m-0 text-base font-bold">{{ panel === 'share' ? 'Share' : 'Options' }}</h3>
          <button type="button" class="-mr-2 grid h-9 w-9 cursor-pointer place-items-center rounded-[8px] border-0 bg-transparent text-ink-3 hover:bg-raised hover:text-ink" :aria-label="`Close ${panel === 'share' ? 'share' : 'options'}`" @click="panel = null"><i aria-hidden="true" class="fas fa-times"></i></button>
        </header>
        <div class="flex min-h-0 flex-col gap-5 overflow-y-auto overscroll-contain px-5 pb-5 pt-2">
          <RecapShareActions v-if="panel === 'share'" :blob="blob" :filename="filename" :caption="caption" :share-title="shareTitle" :disabled="!ready || rendering" download-label="Download PNG" @before-action="pause" />
          <template v-else>
        <section aria-label="Recap settings" class="flex flex-col gap-3">
          <div class="grid grid-cols-2 gap-2">
            <label v-if="sampleDataAvailable" class="ui-label">Data source<select v-model="mode" class="ui-input"><option value="real">My activity</option><option value="demo">Sample data</option></select></label>
            <label v-if="mode === 'real'" class="ui-label">Year<select v-model.number="year" aria-label="Year" class="ui-input"><option v-for="value in availableYears" :key="value" :value="value">{{ value }}</option></select></label>
            <label v-else class="ui-label">Media server<select v-model="provider" class="ui-input"><option value="jellyfin">Jellyfin</option><option value="plex">Plex</option></select></label>
            <label v-if="isAdmin && (mode === 'demo' || realData?.allowedScopes.includes('server'))" class="ui-label col-span-2">Recap scope<select v-model="scope" class="ui-input"><option value="personal">Personal recap</option><option value="server">Server recap</option></select></label>
          </div>
          <p v-if="mode === 'demo'" class="m-0 rounded-ctl border border-brand-soft bg-brand-soft/25 px-3 py-2 text-xs leading-relaxed text-ink-2">Fictional numbers and titles. Your Plex, Jellyfin and SuggestArr activity is not read.</p>
          <template v-else-if="data">
            <p v-if="!data.hasLinkedProfiles" class="m-0 text-sm text-ink-2"><router-link :to="{ name: 'DashboardTab', params: { tab: 'profile' } }">Link your media account</router-link> in My profile to build your personal recap.</p>
            <p v-else-if="!data.requested.total" class="m-0 text-sm text-ink-3">No title requests recorded for {{ year }} in this scope.</p>
            <button v-if="data.watchStatus === 'unavailable'" type="button" class="ui-btn justify-center" :disabled="loading" @click="load(true)"><i aria-hidden="true" class="fas fa-redo"></i>Retry {{ data.providerLabel }} watch activity</button>
          </template>
        </section>

        <details class="group text-xs">
          <summary class="flex cursor-pointer list-none items-center justify-between gap-2 font-semibold text-ink-3 hover:text-ink [&::-webkit-details-marker]:hidden">
            <span><i aria-hidden="true" class="fas fa-info-circle mr-2"></i>About these numbers</span>
            <i aria-hidden="true" class="fas fa-chevron-down text-[10px] transition-transform group-open:rotate-180"></i>
          </summary>
          <div class="mt-2 leading-relaxed text-ink-3">
            <p v-if="mode === 'demo'" class="m-0">Every number, title and cover in this preview is sample data, so you can see the stories before your own year is recorded. Shared images and captions are labelled as sample data.</p>
            <template v-else>
              <p class="m-0">{{ data?.isYearToDate ? 'Year to date. ' : '' }}Counts reflect the first recorded request for each title, and recorded history may not cover the entire year. Previously deleted history cannot be recovered. Genres and covers describe requested titles.</p>
              <p v-if="data" class="m-0 mt-2">{{ data.watchNote }}</p>
            </template>
            <p class="m-0 mt-2 text-ink-4">Images are created on your device as 1080 × 1920 PNGs.</p>
          </div>
        </details>
          </template>
        </div>
      </aside>
    </Transition>
  </dialog>
</template>

<script>
import RecapShareActions from './RecapShareActions.vue';
import { getYearRecap } from '@/api/recapApi.js';
import { canvasBlob } from '@/utils/recapCanvas.js';
import { createYearRecapDemo } from '@/utils/yearRecapDemo.js';
import { prepareYearRecap, yearStories, yearCaption, yearDescription } from '@/utils/yearRecapData.js';
import { yearRecapSeason } from '@/utils/yearRecapSeason.js';
import { renderYearStory } from '@/utils/yearRecapCanvas.js';

const STORY_DURATION = 8000;
const HOLD_DELAY = 250;
const GLASS_BUTTON = 'grid h-10 w-10 shrink-0 cursor-pointer place-items-center rounded-full border-0 bg-white/10 text-white transition-colors hover:bg-white/20 disabled:cursor-default disabled:opacity-35 disabled:hover:bg-white/10';

const SAMPLE_DATA_AVAILABLE = import.meta.env.DEV === true;

let nextId = 0;

export default {
  name: 'YearRecapStories',
  components: { RecapShareActions },
  props: { isAdmin: { type: Boolean, default: false }, initialMode: { type: String, default: 'real' }, initialYear: { type: Number, default: null } },
  emits: ['close'],
  data() { return { index: 0, scope: 'personal', provider: 'jellyfin', paused: false, holding: false, holdTimer: null, suppressTap: false,
    elapsed: 0, rendering: true, ready: false, blob: null, error: '', notice: '', reducedMotion: false,
    generation: 0, active: true, timer: null, lastTick: 0, touch: null, animation: null, motionQuery: null,
    stageWidth: 0, stageHeight: 0, resizeObserver: null,
    // Sample data is a development aid only; installed builds always show real activity.
    sampleDataAvailable: SAMPLE_DATA_AVAILABLE,
    mode: SAMPLE_DATA_AVAILABLE ? this.initialMode : 'real', year: this.initialYear ?? yearRecapSeason().year, realData: null, loading: false,
    requestVersion: 0, controller: null,
    panel: null, titleId: `year-recap-title-${++nextId}`, glassButton: GLASS_BUTTON }; },
  computed: {
    frameStyle() {
      const width = Math.max(0, Math.min(this.stageWidth, this.stageHeight * 9 / 16) - 2);
      return { width: `${width}px`, height: `${width * 16 / 9}px` };
    },
    data() { return this.mode === 'demo' ? createYearRecapDemo(this.isAdmin ? this.scope : 'personal', this.provider) : this.realData; },
    displayYear() { return this.data?.year ?? this.year; },
    stories() { return yearStories(this.data || { year: this.year, isDemo: false }); },
    availableYears() { return [...new Set([this.year, ...(this.realData?.availableYears || [this.year - 1])])].sort((a, b) => b - a); },
    // A new year or scope can have fewer stories; stay in range until the player resets.
    story() { return this.stories[Math.min(this.index, this.stories.length - 1)]; },
    description() { return this.data ? yearDescription(this.data, this.story) : 'Recorded progress is not available yet.'; },
    caption() { return this.data ? yearCaption(this.data, this.story) : ''; },
    shareTitle() { return `${this.displayYear} Year Recap${this.mode === 'demo' ? ' · Preview · Sample data' : ' · Recorded progress'}`; },
    filename() { return this.data ? `suggestarr-${this.data.year}-${this.story.id}-${this.data.isDemo ? 'preview' : 'recorded'}.png` : 'suggestarr-year-recap.png'; },
    progress() { return this.index === this.stories.length - 1 ? 100 : this.elapsed / (STORY_DURATION / 100); },
  },
  watch: {
    scope() { this.load(); },
    provider() { if (this.mode === 'demo') this.reset(); },
    year() { if (this.mode === 'real') this.load(); },
    mode() { this.load(); },
    isAdmin() { this.scope = 'personal'; this.load(); },
  },
  created() {
    // Rendered PNGs per data snapshot and story index; not reactive on purpose.
    this.storyCache = new WeakMap();
  },
  mounted() {
    this.$refs.dialog.showModal();
    this.motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    this.reducedMotion = this.motionQuery.matches;
    this.paused = this.reducedMotion;
    this.motionQuery.addEventListener('change', this.motionChanged);
    document.addEventListener('visibilitychange', this.pauseWhenHidden);
    document.addEventListener('keydown', this.onKey);
    window.addEventListener('blur', this.pause);
    this.lastTick = performance.now();
    this.timer = setInterval(this.tick, 100);
    this.resizeObserver = new ResizeObserver(([entry]) => {
      this.stageWidth = entry.contentRect.width;
      this.stageHeight = entry.contentRect.height;
    });
    this.resizeObserver.observe(this.$refs.stage);
    this.load();
  },
  beforeUnmount() {
    this.active = false;
    this.generation += 1;
    clearInterval(this.timer);
    clearTimeout(this.holdTimer);
    this.resizeObserver?.disconnect();
    this.controller?.abort();
    this.animation?.cancel();
    this.motionQuery?.removeEventListener('change', this.motionChanged);
    document.removeEventListener('visibilitychange', this.pauseWhenHidden);
    document.removeEventListener('keydown', this.onKey);
    window.removeEventListener('blur', this.pause);
  },
  methods: {
    /**
     * Fetch recorded progress (or switch to sample data) and show a story.
     * @param {boolean} keepStory - Stay on the current story instead of restarting from the intro.
     */
    async load(keepStory = false) {
      const version = ++this.requestVersion;
      this.controller?.abort();
      this.generation += 1;
      this.ready = false;
      this.error = '';
      this.loading = false;
      if (this.mode === 'demo') { this.reset(); return; }
      this.loading = true;
      this.realData = null;
      this.controller = new AbortController();
      try {
        // Watch activity is always fetched with the recap; the server skips it when no media server is linked.
        const data = await getYearRecap(this.year, this.isAdmin ? this.scope : 'personal', true, this.controller.signal);
        if (!this.active || version !== this.requestVersion) return;
        this.realData = prepareYearRecap(data);
        if (keepStory) this.go(Math.min(this.index, this.stories.length - 1));
        else this.reset();
      } catch {
        if (this.active && version === this.requestVersion) this.error = 'Unable to load recorded progress. Try again or select sample data.';
      } finally { if (version === this.requestVersion) this.loading = false; }
    },
    close() { this.$refs.dialog.close(); },
    /** Toggle the options or share panel; opening one pauses the stories so they stay put. */
    toggle(panel) {
      this.panel = this.panel === panel ? null : panel;
      if (this.panel) this.pause();
    },
    /** Clicking the backdrop closes an open panel first, then the viewer. */
    dismiss() { if (this.panel) this.panel = null; else this.close(); },
    onCancel(event) {
      // Escape closes an open panel before closing the viewer.
      if (!this.panel) return;
      event.preventDefault();
      this.panel = null;
    },
    download() {
      if (!this.blob) return;
      this.pause();
      const url = URL.createObjectURL(this.blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = this.filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    retry() { if (!this.data) this.load(); else this.render(); },
    pause() { this.paused = true; },
    pauseWhenHidden() { if (document.hidden) this.pause(); },
    motionChanged(event) { this.reducedMotion = event.matches; if (event.matches) { this.pause(); this.animation?.cancel(); } },
    togglePlayback() {
      if (this.index === this.stories.length - 1 && this.paused) this.go(0);
      this.paused = !this.paused;
      this.lastTick = performance.now();
    },
    tick() {
      const now = performance.now();
      const delta = now - this.lastTick;
      this.lastTick = now;
      if (this.paused || this.holding || this.loading || this.rendering || !this.ready || document.hidden) return;
      if (this.index === this.stories.length - 1) { this.pause(); return; }
      this.elapsed = Math.min(STORY_DURATION, this.elapsed + delta);
      if (this.elapsed >= STORY_DURATION) this.go(this.index + 1);
    },
    go(index) {
      if (index < 0 || index >= this.stories.length) return;
      this.index = index;
      this.elapsed = 0;
      this.lastTick = performance.now();
      if (index === this.stories.length - 1) this.pause();
      this.render();
    },
    reset() { this.go(0); },
    onKey(event) {
      if (event.target.closest('select,input,textarea,a,summary') || (event.code === 'Space' && event.target.closest('button'))) return;
      if (event.key === 'ArrowRight') { event.preventDefault(); this.go(this.index + 1); }
      else if (event.key === 'ArrowLeft') { event.preventDefault(); this.go(this.index - 1); }
      else if (event.code === 'Space') { event.preventDefault(); this.togglePlayback(); }
    },
    tap(event) {
      if (this.suppressTap) { this.suppressTap = false; return; }
      if (this.loading || !this.data) return;
      const bounds = event.currentTarget.getBoundingClientRect();
      this.go(this.index + (event.clientX - bounds.left < bounds.width / 3 ? -1 : 1));
    },
    holdStart(event) {
      if (event.button !== 0) return;
      this.suppressTap = false;
      clearTimeout(this.holdTimer);
      this.holdTimer = setTimeout(() => { this.holding = true; }, HOLD_DELAY);
    },
    holdEnd() {
      clearTimeout(this.holdTimer);
      if (!this.holding) return;
      // Releasing a hold resumes the story instead of counting as a tap.
      this.holding = false;
      this.suppressTap = true;
      this.lastTick = performance.now();
    },
    holdCancel() {
      clearTimeout(this.holdTimer);
      this.holding = false;
    },
    touchStart(event) { this.touch = { x: event.changedTouches[0].clientX, y: event.changedTouches[0].clientY }; },
    touchEnd(event) {
      if (!this.touch) return;
      const dx = event.changedTouches[0].clientX - this.touch.x;
      const dy = event.changedTouches[0].clientY - this.touch.y;
      if (Math.abs(dx) >= 40 && Math.abs(dx) > Math.abs(dy)) this.go(this.index + (dx < 0 ? 1 : -1));
      this.touch = null;
    },
    /** Render a story PNG once per data snapshot; later visits and preloads reuse it. */
    storyImage(data, index) {
      let images = this.storyCache.get(data);
      if (!images) { images = new Map(); this.storyCache.set(data, images); }
      if (!images.has(index)) {
        const image = (async () => {
          const frame = document.createElement('canvas');
          const result = await renderYearStory(frame, data, yearStories(data)[index], index);
          return { blob: await canvasBlob(frame), missingPosters: result.missingPosters };
        })();
        images.set(index, image);
        image.catch(() => images.delete(index));
      }
      return images.get(index);
    },
    preload(data, index) {
      if (index >= this.stories.length) return;
      setTimeout(() => { if (this.active && this.data === data) this.storyImage(data, index).catch(() => {}); }, 0);
    },
    async render() {
      if (!this.data) return;
      const generation = ++this.generation;
      const { data, index } = this;
      this.rendering = true;
      this.ready = false;
      this.error = this.notice = '';
      try {
        const image = await this.storyImage(data, index);
        if (!this.active || generation !== this.generation) return;
        const bitmap = await createImageBitmap(image.blob);
        if (!this.active || generation !== this.generation) { bitmap.close(); return; }
        const canvas = this.$refs.canvas;
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
        canvas.getContext('2d').drawImage(bitmap, 0, 0);
        bitmap.close();
        this.blob = image.blob;
        this.ready = true;
        if (image.missingPosters) this.notice = 'Some covers could not be loaded. Title cards are used in the preview and PNG.';
        this.lastTick = performance.now();
        this.animation?.cancel();
        if (!this.reducedMotion) this.animation = canvas.animate([{ opacity: 0, transform: 'translateY(10px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 260, easing: 'ease-out' });
        this.preload(data, index + 1);
      } catch { if (generation === this.generation) this.error = 'Unable to render this story.'; }
      finally { if (generation === this.generation) this.rendering = false; }
    },
  },
};
</script>
