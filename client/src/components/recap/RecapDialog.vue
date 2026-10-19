<template>
  <AppDialog title="Your SuggestArr recap" icon="fas fa-image" width="max-w-3xl" class="h-[calc(100dvh-2rem)] sm:h-[min(80dvh,52rem)] sm:w-[calc(100%-4rem)]" body-class="flex min-h-0 flex-col p-0" @close="$emit('close')">
    <div role="tablist" aria-label="Recap views" class="grid shrink-0 grid-cols-3 gap-1 border-b border-edge px-4 pt-2 sm:px-6">
      <button
        v-for="(tab, index) in tabs"
        :id="`${tabId}-${tab.id}-tab`"
        :key="tab.id"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab.id"
        :aria-controls="`${tabId}-${tab.id}-panel`"
        :tabindex="activeTab === tab.id ? 0 : -1"
        class="flex h-11 min-w-0 cursor-pointer items-center justify-center gap-2 border-0 border-b-2 bg-transparent px-2 text-[13px] font-semibold transition-colors"
        :class="activeTab === tab.id ? 'border-brand-ink text-brand-ink' : 'border-transparent text-ink-3 hover:text-ink'"
        @click="activeTab = tab.id"
        @keydown.right.prevent="selectTab((index + 1) % tabs.length)"
        @keydown.left.prevent="selectTab((index + tabs.length - 1) % tabs.length)"
        @keydown.home.prevent="selectTab(0)"
        @keydown.end.prevent="selectTab(tabs.length - 1)"
      ><i aria-hidden="true" :class="tab.icon" class="hidden sm:inline"></i>{{ tab.label }}</button>
    </div>

    <div class="flex min-h-0 flex-1 flex-col">
      <p v-if="warning" role="status" class="mx-4 mb-0 mt-3 shrink-0 rounded-ctl border border-caution/30 bg-caution/10 px-3 py-2 text-xs leading-relaxed text-ink-2 sm:mx-6">{{ warning }}</p>
      <p v-if="error" role="alert" class="ui-alert-bad mx-4 mt-3 shrink-0 sm:mx-6">{{ error }}</p>
      <p v-if="shareNotice" role="status" class="mx-4 mb-0 mt-3 shrink-0 text-xs leading-relaxed text-brand-ink sm:mx-6">{{ shareNotice }}</p>

      <div v-show="activeTab === 'preview'" :id="`${tabId}-preview-panel`" role="tabpanel" :aria-labelledby="`${tabId}-preview-tab`" tabindex="0" class="flex min-h-0 flex-1 flex-col">
        <div class="relative flex min-h-0 flex-1 items-center justify-center bg-canvas/60 p-3 sm:p-4" :aria-busy="rendering">
          <canvas ref="canvas" width="1080" height="1350" role="img" :aria-label="caption" class="block h-auto max-h-full w-auto max-w-full rounded-ctl object-contain shadow-lg ring-1 ring-edge"></canvas>
          <span v-if="rendering" role="status" class="absolute inset-0 grid place-items-center bg-canvas/90 text-sm text-ink-3">Creating your recap…</span>
        </div>
        <div class="shrink-0 border-t border-edge px-4 py-3 sm:px-6">
          <BaseCheckbox v-model="includePosters" :disabled="rendering" label="Show top-title covers" />
        </div>
      </div>

      <div v-show="activeTab === 'share'" :id="`${tabId}-share-panel`" role="tabpanel" :aria-labelledby="`${tabId}-share-tab`" tabindex="0" class="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
        <h3 class="m-0 text-base font-bold text-ink">Share your discoveries</h3>
        <p class="m-0 mt-2 text-xs leading-relaxed text-ink-3">Choose a platform, then attach the saved image. Discord copies it when supported.</p>
        <div class="mt-4 grid grid-cols-2 gap-2">
          <a v-for="target in shareTargets" :key="target.id" :href="target.url" target="_blank" rel="noopener noreferrer" class="ui-btn no-underline" :class="target.id === 'reddit' ? 'border-brand bg-brand-soft text-brand-ink' : ''" :aria-disabled="rendering || !ready || exporting ? 'true' : 'false'" @click="preparePlatform($event, target)"><i aria-hidden="true" :class="target.icon"></i>{{ target.label }}</a>
        </div>
        <button v-if="canShare" type="button" class="ui-btn mt-3 w-full" :disabled="rendering || !ready || exporting" @click="share"><i aria-hidden="true" class="fas fa-share-alt"></i>Share</button>
        <div class="mt-5 border-t border-edge pt-4">
          <div class="flex items-center justify-between gap-3">
            <h4 class="m-0 text-xs font-semibold text-ink-3">Caption</h4>
            <button type="button" class="inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-ctl border-0 bg-transparent px-2 text-xs font-semibold text-brand-ink hover:bg-raised" @click="copyCaption"><i aria-hidden="true" class="fas fa-copy"></i>Copy caption</button>
          </div>
          <p class="m-0 mt-2 select-text break-words rounded-ctl border border-edge bg-canvas/50 p-3 text-xs leading-relaxed text-ink-2">{{ caption }}</p>
        </div>
        <p class="m-0 mt-4 text-[11px] leading-relaxed text-ink-4">Created on your device. Account and server details stay private.</p>
      </div>

      <div v-show="activeTab === 'badges'" :id="`${tabId}-badges-panel`" role="tabpanel" :aria-labelledby="`${tabId}-badges-tab`" tabindex="0" class="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
        <div class="mb-4 flex items-baseline justify-between gap-3">
          <h3 class="m-0 text-base font-bold text-ink">Your badges</h3>
          <span class="text-xs text-ink-3">{{ recap.badges.filter(badge => badge.unlocked).length }} / {{ recap.badges.length }} unlocked</span>
        </div>
        <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div v-for="badge in recap.badges" :key="badge.id" class="flex items-start gap-3 rounded-ctl border p-3" :class="badge.unlocked ? 'border-brand-soft bg-brand-soft/25' : 'border-edge bg-canvas/30'">
            <i aria-hidden="true" class="mt-0.5 w-4 shrink-0 text-center" :class="badge.unlocked ? 'fas fa-award text-brand-ink' : 'fas fa-lock text-ink-4'"></i>
            <div class="min-w-0">
              <p class="m-0 text-xs font-semibold" :class="badge.unlocked ? 'text-ink' : 'text-ink-3'">{{ badge.label }}</p>
              <p class="m-0 mt-1 text-[11px] leading-relaxed text-ink-4">{{ badge.kind === 'days' ? 'One year of discoveries' : `${badge.threshold.toLocaleString('en-US')} titles requested` }}</p>
              <span class="sr-only">{{ badge.unlocked ? 'Unlocked' : 'Locked' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="grid w-full gap-2" :class="canCopyImage ? 'grid-cols-2' : 'grid-cols-1'">
        <button v-if="canCopyImage" type="button" class="ui-btn min-w-0 px-2 text-xs sm:px-4 sm:text-sm" :disabled="rendering || !ready || exporting" @click="copyImage"><i aria-hidden="true" class="fas fa-image"></i>Copy image</button>
        <button type="button" class="ui-btn-primary min-w-0 px-2 text-xs sm:px-4 sm:text-sm" :disabled="rendering || !ready || exporting" @click="download"><i aria-hidden="true" class="fas fa-download"></i>Download PNG</button>
      </div>
    </template>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import logoUrl from '@/assets/logo.png';
import { getRecap } from '@/api/recapApi.js';
import { canvasBlob, recapCaption, recapShareTargets, renderRecap } from '@/utils/recapCanvas.js';

let nextTabId = 0;

export default {
  name: 'RecapDialog',
  components: { AppDialog, BaseCheckbox },
  props: { recap: { type: Object, required: true } },
  emits: ['close'],
  data: () => ({
    tabId: `recap-${++nextTabId}`, activeTab: 'preview',
    tabs: [
      { id: 'preview', label: 'Preview', icon: 'fas fa-image' },
      { id: 'share', label: 'Share', icon: 'fas fa-share-alt' },
      { id: 'badges', label: 'Badges', icon: 'fas fa-award' },
    ],
    includePosters: true, rendering: true, ready: false, exporting: false, warning: '', error: '', blob: null, active: true, featuredPosters: [], postersLoaded: false, shareNotice: '',
  }),
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
    selectTab(index) {
      this.activeTab = this.tabs[index].id;
      this.$nextTick(() => document.getElementById(`${this.tabId}-${this.tabs[index].id}-tab`)?.focus());
    },
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
