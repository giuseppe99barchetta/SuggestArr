<template>
  <AppDialog title="Your SuggestArr recap" subtitle="Celebrate your discoveries and share the journey." icon="fas fa-wand-magic-sparkles" width="max-w-4xl" @close="$emit('close')">
    <div class="grid items-start gap-6 md:grid-cols-2">
      <div class="relative aspect-[4/5] overflow-hidden rounded-card border border-edge bg-canvas" :aria-busy="rendering">
        <canvas ref="canvas" width="1080" height="1350" role="img" :aria-label="caption" class="block aspect-[4/5] h-auto w-full"></canvas>
        <span v-if="rendering" role="status" class="absolute inset-0 grid place-items-center bg-canvas/90 text-sm text-ink-3">Creating your recap…</span>
      </div>
      <div class="flex min-w-0 flex-col gap-4">
        <div>
          <h3 class="m-0 text-sm font-bold text-ink">Your top picks, in the spotlight</h3>
          <p class="m-0 mt-1 text-xs leading-relaxed text-ink-3">Up to four of your highest-rated requested titles, arranged as a cinematic fan.</p>
        </div>
        <BaseCheckbox v-model="includePosters" :disabled="rendering" label="Show top-title covers" description="Turn off to keep your movie and TV picks private." />
        <div v-if="includePosters && featuredPosters.length" aria-label="Featured covers" class="grid grid-cols-4 gap-2">
          <div v-for="poster in featuredPosters" :key="poster.poster_path" class="min-w-0">
            <div class="aspect-[2/3] overflow-hidden rounded-ctl border border-edge bg-panel-2">
              <img v-if="artworkUrl(poster.poster_path) && !failedPosters.includes(poster.poster_path)" :src="artworkUrl(poster.poster_path)" alt="" crossorigin="anonymous" class="h-full w-full object-cover" @error="failedPosters.push(poster.poster_path)" />
              <span v-else class="grid h-full place-items-center text-ink-4"><i aria-hidden="true" class="fas fa-film"></i><span class="sr-only">Artwork unavailable</span></span>
            </div>
            <p class="m-0 mt-1 truncate text-[11px] font-semibold text-ink-2" :title="poster.title">{{ poster.title || 'Requested title' }}</p>
            <span v-if="poster.rating" class="text-[10px] text-caution">★ {{ Number(poster.rating).toFixed(1) }}</span>
          </div>
        </div>
        <p class="m-0 text-xs leading-relaxed text-ink-3">Review your covers before sharing. Account names, server names and installation addresses stay private.</p>
        <p v-if="warning" role="status" class="rounded-ctl border border-caution/30 bg-caution/10 p-3 text-sm text-ink-2">{{ warning }}</p>
        <p v-if="error" role="alert" class="ui-alert-bad">{{ error }}</p>
        <div class="flex flex-wrap gap-2">
          <button type="button" class="ui-btn-primary" :disabled="rendering || !ready || exporting" @click="download"><i aria-hidden="true" class="fas fa-download"></i>Download PNG</button>
          <button v-if="canCopyImage" type="button" class="ui-btn" :disabled="rendering || !ready || exporting" @click="copyImage"><i aria-hidden="true" class="fas fa-image"></i>Copy image</button>
          <button type="button" class="ui-btn" @click="copyCaption"><i aria-hidden="true" class="fas fa-copy"></i>Copy caption</button>
          <button v-if="canShare" type="button" class="ui-btn" :disabled="rendering || !ready || exporting" @click="share"><i aria-hidden="true" class="fas fa-share-alt"></i>Share</button>
        </div>
        <div class="border-t border-edge pt-4">
          <h3 class="m-0 mb-2 text-sm font-bold text-ink">Share your discoveries</h3>
          <div class="grid grid-cols-2 gap-2">
            <a v-for="target in shareTargets" :key="target.id" :href="target.url" target="_blank" rel="noopener noreferrer" class="ui-btn justify-center no-underline" :class="target.id === 'reddit' ? 'border-brand bg-brand-soft text-brand-ink' : ''" :aria-disabled="rendering || !ready || exporting ? 'true' : 'false'" @click="preparePlatform($event, target)"><i aria-hidden="true" :class="target.icon"></i>{{ target.label }}</a>
          </div>
          <p class="m-0 mt-2 text-xs leading-relaxed text-ink-3">Reddit and social buttons save the PNG for you to attach. Discord copies the image when supported, or saves it to attach.</p>
          <p v-if="shareNotice" role="status" class="mt-2 text-xs text-brand-ink">{{ shareNotice }}</p>
        </div>
        <p class="m-0 text-xs text-ink-4">1080 × 1350 PNG · Created on your device</p>
        <p class="m-0 break-words text-xs leading-relaxed text-ink-3">{{ caption }}</p>
        <div class="mt-2 border-t border-edge pt-4">
          <h3 class="m-0 mb-3 text-sm font-bold text-ink">Your badges</h3>
          <div class="grid grid-cols-2 gap-2">
            <div v-for="badge in recap.badges" :key="badge.id" class="flex flex-col gap-1 rounded-ctl border p-3" :class="badge.unlocked ? 'border-brand-soft bg-brand-soft/30' : 'border-edge bg-panel-2'">
              <i aria-hidden="true" :class="badge.unlocked ? 'fas fa-award text-brand-ink' : 'fas fa-lock text-ink-4'"></i>
              <span class="text-xs font-bold text-ink">{{ badge.label }}</span>
              <span class="text-[11px] text-ink-3">{{ badge.unlocked ? 'Unlocked · ' : '' }}{{ badge.kind === 'days' ? '365 days since your first recorded request' : `${badge.threshold.toLocaleString('en-US')} titles requested` }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import logoUrl from '@/assets/logo.png';
import { getRecap } from '@/api/recapApi.js';
import { canvasBlob, posterUrl, recapCaption, recapShareTargets, renderRecap } from '@/utils/recapCanvas.js';

export default {
  name: 'RecapDialog',
  components: { AppDialog, BaseCheckbox },
  props: { recap: { type: Object, required: true } },
  emits: ['close'],
  data: () => ({ includePosters: true, rendering: true, ready: false, exporting: false, warning: '', error: '', blob: null, active: true, featuredPosters: [], postersLoaded: false, failedPosters: [], shareNotice: '' }),
  computed: {
    caption() { return recapCaption(this.recap); },
    shareTargets() { return recapShareTargets(this.recap); },
    canCopyImage() { return typeof ClipboardItem !== 'undefined' && typeof navigator.clipboard?.write === 'function'; },
    canShare() {
      return typeof navigator.canShare === 'function' && navigator.canShare({ files: [new File([''], 'suggestarr-recap.png', { type: 'image/png' })] });
    },
  },
  watch: { includePosters() { this.render(); } },
  mounted() { this.render(); },
  beforeUnmount() { this.active = false; },
  methods: {
    artworkUrl: posterUrl,
    async render() {
      this.rendering = true;
      this.ready = false;
      this.error = '';
      this.warning = '';
      this.shareNotice = '';
      try {
        let data = this.recap;
        if (this.includePosters && !this.postersLoaded) {
          try {
            this.featuredPosters = (await getRecap(true)).posters.slice(0, 4);
            this.postersLoaded = true;
          }
          catch { this.warning = 'Posters could not be loaded. Your statistics are still available.'; }
        }
        data = { ...this.recap, posters: this.featuredPosters };
        if (!this.active) return;
        const result = await renderRecap(this.$refs.canvas, data, { logoUrl, includePosters: this.includePosters });
        if (!this.active) return;
        if (result.missingPosters) this.warning = 'Some covers could not be loaded. Their places use illustrated cards.';
        else if (this.includePosters && !data.posters.length) this.warning ||= 'No cover artwork is available. Your recap uses an illustrated fan.';
        this.blob = await canvasBlob(this.$refs.canvas);
        this.ready = true;
      } catch { this.error = 'Unable to create your recap. Try again or turn off posters.'; }
      finally { this.rendering = false; }
    },
    async download() {
      const url = URL.createObjectURL(this.blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'suggestarr-recap.png';
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    async copyImage() {
      try {
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': this.blob })]);
        this.shareNotice = 'Image copied. Paste it into your post or Discord conversation.';
      } catch { this.error = 'Image copying is unavailable here. Download the PNG to attach it instead.'; }
    },
    preparePlatform(event, target) {
      if (this.rendering || !this.ready || this.exporting) { event.preventDefault(); return; }
      // Keep the real anchor navigation synchronous, preserving browser activation
      // and a usable link even when clipboard permissions are refused.
      if (target.id === 'discord' && this.canCopyImage) {
        navigator.clipboard.write([new ClipboardItem({ 'image/png': this.blob })]).then(() => {
          this.shareNotice = 'Image copied. Choose a Discord conversation and paste it there.';
        }).catch(() => {
          this.download();
          this.shareNotice = 'PNG saved. Attach it in your Discord conversation.';
        });
      } else {
        this.download();
        this.shareNotice = `PNG saved. Attach it to your ${target.label} post.`;
        navigator.clipboard?.writeText(this.caption).then(() => {
          this.shareNotice += ' Caption copied.';
        }).catch(() => { /* The visible caption remains available for manual copy. */ });
      }
    },
    async copyCaption() {
      try {
        await navigator.clipboard.writeText(this.caption);
        this.$toast.success('Caption copied.');
      } catch { this.error = 'Clipboard unavailable. You can copy the caption below.'; }
    },
    async share() {
      this.exporting = true;
      try {
        await navigator.share({ files: [new File([this.blob], 'suggestarr-recap.png', { type: 'image/png' })], title: 'My SuggestArr recap', text: this.caption });
      } catch (error) {
        if (error.name !== 'AbortError') this.error = 'Sharing is unavailable here. Download the PNG instead.';
      } finally { this.exporting = false; }
    },
  },
};
</script>
