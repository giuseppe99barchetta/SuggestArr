<template>
  <AppDialog :title="`${mode === 'demo' ? 2026 : year} Year recap`" :subtitle="mode === 'demo' ? 'Preview · Sample data' : 'Recorded progress · Real data'" immersive width="max-w-7xl" body-class="p-0" @close="$emit('close')">
    <div class="grid h-full min-h-0 grid-rows-[minmax(0,1fr)_minmax(0,28dvh)] bg-canvas md:grid-cols-[minmax(0,1fr)_360px] md:grid-rows-1">
      <div class="grid min-h-0 min-w-0 grid-rows-[8px_minmax(0,1fr)_36px] justify-items-center gap-3 p-3 sm:p-4">
        <div class="flex w-full max-w-sm gap-1" aria-label="Story progress">
          <button v-for="(item, i) in stories" :key="item.id" type="button" class="h-2 min-w-0 flex-1 cursor-pointer overflow-hidden rounded-full border-0 bg-raised p-0" :aria-label="`Go to story ${i + 1}: ${item.title}`" :aria-current="i === index ? 'step' : null" @click="go(i)">
            <span class="block h-full bg-brand-ink" :style="{ width: `${i < index ? 100 : i === index ? progress : 0}%` }"></span>
          </button>
        </div>
        <div ref="stage" class="grid h-full min-h-0 w-full min-w-0 place-items-center">
        <div class="relative overflow-hidden rounded-card bg-panel ring-1 ring-edge" :style="frameStyle" :aria-busy="rendering" @touchstart.passive="touchStart" @touchend.passive="touchEnd">
          <canvas ref="canvas" width="1080" height="1920" tabindex="0" role="img" :aria-label="description" class="block h-full w-full"></canvas>
          <div v-if="rendering || loading || !data" class="absolute inset-0 grid place-items-center bg-canvas/90 p-3 text-center text-sm text-ink-3" role="status">{{ loading ? 'Loading recorded progress…' : !data ? 'Choose sample data or try again.' : 'Creating your story…' }}</div>
        </div>
        </div>
        <div class="flex w-full max-w-sm items-center justify-between gap-2">
          <button type="button" class="ui-btn h-9 px-3" :disabled="index === 0" aria-label="Previous story" @click="go(index - 1)"><i aria-hidden="true" class="fas fa-chevron-left"></i></button>
          <button type="button" class="ui-btn h-9 px-3" :aria-label="paused ? 'Play stories' : 'Pause stories'" @click="togglePlayback"><i aria-hidden="true" :class="paused ? 'fas fa-play' : 'fas fa-pause'"></i>{{ paused ? 'Play' : 'Pause' }}</button>
          <span class="text-xs text-ink-3" aria-live="polite">{{ index + 1 }} / {{ stories.length }}</span>
          <button type="button" class="ui-btn h-9 px-3" :disabled="index === stories.length - 1" aria-label="Next story" @click="go(index + 1)"><i aria-hidden="true" class="fas fa-chevron-right"></i></button>
        </div>
      </div>
      <div class="flex min-h-0 min-w-0 flex-col gap-4 overflow-y-auto overscroll-contain border-t border-edge bg-panel p-4 sm:p-5 md:border-l md:border-t-0">
        <div class="grid grid-cols-2 gap-2">
          <label class="ui-label">Data source<select v-model="mode" class="ui-input"><option value="real">My activity</option><option value="demo">Preview · Sample data</option></select></label>
          <label v-if="mode === 'real'" class="ui-label">Year<select v-model.number="year" aria-label="Year" class="ui-input"><option v-for="value in availableYears" :key="value" :value="value">{{ value }}</option></select></label>
          <label v-else class="ui-label">Media server<select v-model="provider" class="ui-input"><option value="jellyfin">Jellyfin</option><option value="plex">Plex</option></select></label>
          <label v-if="isAdmin && (mode === 'demo' || realData?.allowedScopes.includes('server'))" class="ui-label">Recap scope<select v-model="scope" class="ui-input"><option value="personal">Personal recap</option><option value="server">Server recap</option></select></label>
          <p v-else class="m-0 self-end pb-2 text-xs text-ink-3">Personal recap</p>
        </div>
        <template v-if="mode === 'real' && data">
          <p v-if="!data.hasLinkedProfiles" class="m-0 text-sm text-ink-2"><router-link :to="{ name: 'DashboardTab', params: { tab: 'profile' } }">Link your media account</router-link> in My profile to build your personal recap.</p>
          <p v-else-if="!data.requested.total" class="m-0 text-sm text-ink-3">No title requests recorded for {{ year }} in this scope.</p>
          <button v-if="data.provider && data.hasLinkedProfiles" type="button" class="ui-btn justify-center" :disabled="loading" @click="loadWatchActivity">{{ includePlayback ? 'Refresh watch activity' : `Load ${data.providerLabel} watch activity` }}</button>
        </template>
        <div aria-live="polite">
          <p class="m-0 text-[11px] font-bold uppercase tracking-wider text-brand-ink">Story {{ index + 1 }} · {{ mode === 'demo' ? 2026 : year }}</p>
          <h3 class="m-0 mt-1 text-lg font-extrabold text-ink">{{ story.title }}</h3>
          <p class="m-0 mt-2 text-sm leading-relaxed text-ink-3">{{ description }}</p>
        </div>
        <p v-if="mode === 'demo'" class="m-0 rounded-ctl border border-brand-soft bg-brand-soft/25 p-3 text-xs leading-relaxed text-ink-2">Preview · Sample data. These numbers and titles are fictional. Your Plex, Jellyfin and SuggestArr activity is not being read.</p>
        <div v-else class="rounded-ctl border border-edge bg-panel-2 p-3 text-xs leading-relaxed text-ink-3">
          <p class="m-0">{{ data?.isYearToDate ? 'Year to date. ' : '' }}Counts reflect the first recorded request for each title. Previously deleted history cannot be recovered. Genres and covers describe requested titles.</p>
          <p v-if="data" class="m-0 mt-2">{{ data.watchNote }}</p>
        </div>
        <button type="button" class="ui-btn-primary justify-center" :disabled="!ready || rendering" @click="download"><i aria-hidden="true" class="fas fa-download"></i>Download this story</button>
        <button v-if="story.id === 'summary'" type="button" class="ui-btn justify-center" :disabled="!ready || rendering" @click="download">Download summary</button>
        <div class="flex flex-wrap gap-2">
          <button v-if="canCopyImage" type="button" class="ui-btn px-3 text-xs" :disabled="!ready || rendering" @click="copyImage">Copy image</button>
          <button type="button" class="ui-btn px-3 text-xs" @click="copyCaption">Copy caption</button>
          <button v-if="canShare" type="button" class="ui-btn px-3 text-xs" :disabled="!ready || rendering" @click="share">Share</button>
        </div>
        <template v-if="story.id === 'summary'">
          <h4 class="m-0 text-sm font-bold text-ink">Share your year</h4>
          <div class="grid grid-cols-2 gap-2">
            <a v-for="target in targets" :key="target.id" :href="target.url" target="_blank" rel="noopener noreferrer" class="ui-btn justify-center no-underline" :class="target.id === 'reddit' ? 'border-brand bg-brand-soft text-brand-ink' : ''" :aria-disabled="!ready || rendering ? 'true' : 'false'" @click="preparePlatform($event, target)"><i aria-hidden="true" :class="target.icon"></i>{{ target.label }}</a>
          </div>
          <p class="m-0 text-xs leading-relaxed text-ink-4">Attach the saved PNG to your post, or paste the copied image into Discord. Publishing is your choice.</p>
        </template>
        <p v-if="notice" role="status" class="m-0 text-xs text-brand-ink">{{ notice }}</p>
        <p v-if="error" role="alert" class="ui-alert-bad">{{ error }} <button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-brand-ink underline" @click="retry">Try again</button></p>
        <details class="text-xs text-ink-4"><summary class="cursor-pointer">Caption · 1080 × 1920 PNG</summary><p class="m-0 mt-2 break-words leading-relaxed">{{ caption }}</p></details>
      </div>
    </div>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import { getYearRecap } from '@/api/recapApi.js';
import { canvasBlob, recapShareTargets } from '@/utils/recapCanvas.js';
import { createYearRecapDemo } from '@/utils/yearRecapDemo.js';
import { prepareYearRecap, yearStories, yearCaption, yearDescription } from '@/utils/yearRecapData.js';
import { yearRecapSeason } from '@/utils/yearRecapSeason.js';
import { renderYearStory } from '@/utils/yearRecapCanvas.js';

export default {
  name: 'YearRecapStories',
  components: { AppDialog },
  props: { isAdmin: { type: Boolean, default: false }, initialMode: { type: String, default: 'real' }, initialYear: { type: Number, default: null } },
  emits: ['close'],
  data() { return { index: 0, scope: 'personal', provider: 'jellyfin', paused: false,
    elapsed: 0, rendering: true, ready: false, blob: null, error: '', notice: '', reducedMotion: false,
    generation: 0, active: true, timer: null, lastTick: 0, touch: null, animation: null, motionQuery: null,
    stageWidth: 0, stageHeight: 0, resizeObserver: null,
    mode: this.initialMode, year: this.initialYear ?? yearRecapSeason().year, realData: null, loading: false,
    includePlayback: false, requestVersion: 0, controller: null }; },
  computed: {
    frameStyle() {
      const width = Math.max(0, Math.min(this.stageWidth, this.stageHeight * 9 / 16) - 2);
      return { width: `${width}px`, height: `${width * 16 / 9}px` };
    },
    data() { return this.mode === 'demo' ? createYearRecapDemo(this.isAdmin ? this.scope : 'personal', this.provider) : this.realData; },
    stories() { return yearStories(this.data || { year: this.year, isDemo: false }); },
    availableYears() { return [...new Set([this.year, ...(this.realData?.availableYears || [this.year - 1])])].sort((a, b) => b - a); },
    story() { return this.stories[this.index]; },
    description() { return this.data ? yearDescription(this.data, this.story) : 'Recorded progress is not available yet.'; },
    caption() { return this.data ? yearCaption(this.data, this.story) : ''; },
    shareTitle() { return `${this.data?.year || this.year} Year Recap${this.mode === 'demo' ? ' · Preview · Sample data' : ' · Recorded progress'}`; },
    progress() { return this.index === this.stories.length - 1 ? 100 : this.elapsed / 80; },
    targets() { return recapShareTargets(null, { title: this.shareTitle, caption: this.caption }); },
    canCopyImage() { return typeof ClipboardItem !== 'undefined' && typeof navigator.clipboard?.write === 'function'; },
    canShare() { return typeof navigator.canShare === 'function' && navigator.canShare({ files: [new File([''], 'year-recap.png', { type: 'image/png' })] }); },
  },
  watch: {
    scope() { this.load(); },
    provider() { if (this.mode === 'demo') this.reset(); },
    year() { if (this.mode === 'real') this.load(); },
    mode() { this.load(); },
    isAdmin() { this.scope = 'personal'; this.load(); },
  },
  mounted() {
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
    this.resizeObserver?.disconnect();
    this.controller?.abort();
    this.animation?.cancel();
    this.motionQuery?.removeEventListener('change', this.motionChanged);
    document.removeEventListener('visibilitychange', this.pauseWhenHidden);
    document.removeEventListener('keydown', this.onKey);
    window.removeEventListener('blur', this.pause);
  },
  methods: {
    async load() {
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
        const data = await getYearRecap(this.year, this.isAdmin ? this.scope : 'personal', this.includePlayback, this.controller.signal);
        if (!this.active || version !== this.requestVersion) return;
        this.realData = prepareYearRecap(data);
        this.reset();
      } catch {
        if (this.active && version === this.requestVersion) this.error = 'Unable to load recorded progress. Try again or select sample data.';
      } finally { if (version === this.requestVersion) this.loading = false; }
    },
    loadWatchActivity() { this.includePlayback = true; this.load(); },
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
      if (this.paused || this.loading || this.rendering || !this.ready || document.hidden) return;
      if (this.index === this.stories.length - 1) { this.pause(); return; }
      this.elapsed = Math.min(8000, this.elapsed + delta);
      if (this.elapsed >= 8000) this.go(this.index + 1);
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
      if (event.target.closest('select,input,textarea,a') || (event.code === 'Space' && event.target.closest('button'))) return;
      if (event.key === 'ArrowRight') { event.preventDefault(); this.go(this.index + 1); }
      else if (event.key === 'ArrowLeft') { event.preventDefault(); this.go(this.index - 1); }
      else if (event.code === 'Space') { event.preventDefault(); this.togglePlayback(); }
    },
    touchStart(event) { this.touch = { x: event.changedTouches[0].clientX, y: event.changedTouches[0].clientY }; },
    touchEnd(event) {
      if (!this.touch) return;
      const dx = event.changedTouches[0].clientX - this.touch.x;
      const dy = event.changedTouches[0].clientY - this.touch.y;
      if (Math.abs(dx) >= 40 && Math.abs(dx) > Math.abs(dy)) this.go(this.index + (dx < 0 ? 1 : -1));
      this.touch = null;
    },
    async render() {
      if (!this.data) return;
      const generation = ++this.generation;
      this.rendering = true;
      this.ready = false;
      this.error = this.notice = '';
      try {
        const frame = document.createElement('canvas');
        const result = await renderYearStory(frame, this.data, this.story, this.index);
        if (!this.active || generation !== this.generation) return;
        const blob = await canvasBlob(frame);
        if (!this.active || generation !== this.generation) return;
        const canvas = this.$refs.canvas;
        canvas.width = frame.width;
        canvas.height = frame.height;
        canvas.getContext('2d').drawImage(frame, 0, 0);
        this.blob = blob;
        this.ready = true;
        if (result.missingPosters) this.notice = 'Some covers could not be loaded. Title cards are used in the preview and PNG.';
        this.lastTick = performance.now();
        this.animation?.cancel();
        if (!this.reducedMotion) this.animation = canvas.animate([{ opacity: 0, transform: 'translateY(10px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 260, easing: 'ease-out' });
      } catch { if (generation === this.generation) this.error = 'Unable to render this story.'; }
      finally { if (generation === this.generation) this.rendering = false; }
    },
    filename() { return `suggestarr-${this.data.year}-${this.story.id}-${this.data.isDemo ? 'preview' : 'recorded'}.png`; },
    download() {
      this.pause();
      const url = URL.createObjectURL(this.blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = this.filename();
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    async copyImage() {
      this.pause();
      try {
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': this.blob })]);
        this.notice = 'Story image copied. Paste it into your post or conversation.';
      } catch { this.error = 'Image copying is unavailable. Download the PNG instead.'; }
    },
    async copyCaption() {
      this.pause();
      try { await navigator.clipboard.writeText(this.caption); this.notice = 'Story caption copied.'; }
      catch { this.error = 'Clipboard unavailable. Open the caption below to copy it.'; }
    },
    async share() {
      this.pause();
      try { await navigator.share({ files: [new File([this.blob], this.filename(), { type: 'image/png' })], title: this.shareTitle, text: this.caption }); }
      catch (error) { if (error.name !== 'AbortError') this.error = 'Sharing unavailable. Download the PNG instead.'; }
    },
    preparePlatform(event, target) {
      if (!this.ready || this.rendering) { event.preventDefault(); return; }
      this.pause();
      if (target.id === 'discord' && this.canCopyImage) {
        navigator.clipboard.write([new ClipboardItem({ 'image/png': this.blob })]).then(() => {
          this.notice = 'Story image copied. Choose a Discord conversation and paste it there.';
        }).catch(() => { this.download(); this.notice = 'Story PNG saved. Attach it in Discord.'; });
      } else {
        this.download();
        this.notice = `Story PNG saved. Attach it to your ${target.label} post.`;
        navigator.clipboard?.writeText(this.caption).catch(() => { /* Caption remains visible below. */ });
      }
    },
  },
};
</script>
