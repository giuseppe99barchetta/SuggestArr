<template>
  <div class="flex flex-col gap-6">
    <div class="flex flex-col gap-2">
      <button v-if="canShare" type="button" class="ui-btn-primary h-11 w-full whitespace-nowrap" :disabled="unavailable" @click="share"><i aria-hidden="true" class="fas fa-share-alt"></i>Share</button>
      <button v-else-if="!hideDownload" type="button" class="ui-btn-primary h-11 w-full whitespace-nowrap" :disabled="unavailable" @click="download"><i aria-hidden="true" class="fas fa-download"></i>{{ downloadLabel }}</button>
      <div v-if="canShare || canCopyImage" class="grid grid-cols-2 gap-2">
        <button v-if="canShare && !hideDownload" type="button" class="ui-btn whitespace-nowrap px-3" :class="canCopyImage ? '' : 'col-span-2'" :disabled="unavailable" @click="download"><i aria-hidden="true" class="fas fa-download"></i>{{ downloadLabel }}</button>
        <button v-if="canCopyImage" type="button" class="ui-btn whitespace-nowrap px-3" :class="[imageCopied ? 'border-good/40 text-good' : '', canShare && !hideDownload ? '' : 'col-span-2']" :disabled="unavailable" @click="copyImage"><i aria-hidden="true" :class="imageCopied ? 'fas fa-check' : 'far fa-copy'"></i><span aria-live="polite">{{ imageCopied ? 'Copied!' : 'Copy image' }}</span></button>
      </div>
      <p v-if="error" role="alert" class="ui-alert-bad m-0">{{ error }}</p>
    </div>

    <section :aria-labelledby="`${uid}-platforms`">
      <h4 :id="`${uid}-platforms`" class="m-0 text-[11px] font-semibold uppercase tracking-wider text-ink-4">Share to</h4>
      <div class="mt-2.5 grid grid-cols-4 gap-2">
        <a v-for="target in targets" :key="target.id" :href="target.url" target="_blank" rel="noopener noreferrer" class="flex h-16 min-w-0 flex-col items-center justify-center gap-1.5 rounded-ctl border border-edge bg-panel-2 text-[11px] font-medium text-ink-2 no-underline transition-colors hover:border-edge-strong hover:bg-raised hover:text-ink aria-disabled:pointer-events-none aria-disabled:opacity-50" :aria-disabled="unavailable ? 'true' : null" @click="preparePlatform($event, target)"><i aria-hidden="true" class="text-lg" :class="target.icon"></i>{{ target.label }}</a>
      </div>
      <p v-if="shareNotice" role="status" class="m-0 mt-2.5 rounded-ctl border border-brand-ink/15 bg-brand-soft/25 px-3 py-2 text-xs leading-relaxed text-brand-ink">{{ shareNotice }}</p>
      <p v-else class="m-0 mt-2 text-[11px] leading-relaxed text-ink-4">We copy the image first, so you can paste it straight into the post.</p>
    </section>

    <section>
      <div class="flex items-center justify-between gap-2">
        <label :for="`${uid}-caption`" class="text-[11px] font-semibold uppercase tracking-wider text-ink-4">Caption</label>
        <div class="-mr-2 flex items-center">
          <button v-if="captionEdited" type="button" class="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-ctl border-0 bg-transparent px-2 text-xs font-medium text-ink-3 hover:bg-raised hover:text-ink" @click="captionDraft = caption"><i aria-hidden="true" class="fas fa-undo text-[10px]"></i>Reset</button>
          <button type="button" class="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-ctl border-0 bg-transparent px-2 text-xs font-semibold text-brand-ink hover:bg-raised" @click="copyCaption"><i aria-hidden="true" :class="captionCopied ? 'fas fa-check' : 'far fa-copy'"></i><span aria-live="polite">{{ captionCopied ? 'Copied!' : 'Copy caption' }}</span></button>
        </div>
      </div>
      <textarea :id="`${uid}-caption`" v-model="captionDraft" rows="4" class="ui-input mt-1.5 block h-auto resize-none py-2.5 text-[13px] leading-relaxed" :aria-describedby="`${uid}-caption-hint`"></textarea>
      <p :id="`${uid}-caption-hint`" class="m-0 mt-1.5 text-right text-[11px] tabular-nums" :class="captionDraft.length > BLUESKY_LIMIT ? 'text-caution' : 'text-ink-4'">{{ captionDraft.length > BLUESKY_LIMIT ? 'Too long for Bluesky · ' : '' }}{{ captionDraft.length }} / {{ BLUESKY_LIMIT }}</p>
    </section>
  </div>
</template>

<script>
import { recapShareTargets } from '@/utils/recapCanvas.js';
import { canCopyRecapImage, canShareRecapImage, copyRecapImage, prepareRecapImage } from '@/utils/recapSharing.js';

let nextId = 0;

/**
 * Sharing controls shared by the recap and year recap dialogs.
 * Emits `before-action` ahead of every export so story playback can pause.
 */
export default {
  name: 'RecapShareActions',
  props: {
    blob: { type: Blob, default: null },
    filename: { type: String, required: true },
    caption: { type: String, required: true },
    shareTitle: { type: String, required: true },
    disabled: { type: Boolean, default: false },
    downloadLabel: { type: String, default: 'Download PNG' },
    // Hosts with their own download button hide it here to avoid two identical actions.
    hideDownload: { type: Boolean, default: false },
  },
  emits: ['before-action'],
  data() {
    return {
      uid: `recap-share-${++nextId}`, BLUESKY_LIMIT: 300,
      captionDraft: this.caption, exporting: false, error: '', shareNotice: '',
      imageCopied: false, captionCopied: false, imageTimer: null, captionTimer: null, noticeTimer: null, active: true,
    };
  },
  computed: {
    unavailable() { return this.disabled || !this.blob || this.exporting; },
    captionEdited() { return this.captionDraft !== this.caption; },
    targets() { return recapShareTargets(null, { title: this.shareTitle, caption: this.captionDraft }); },
    canCopyImage() { return canCopyRecapImage(); },
    canShare() { return canShareRecapImage(this.blob); },
  },
  watch: {
    caption(value) { this.captionDraft = value; },
    blob() {
      // A new image makes earlier confirmations and errors stale.
      this.error = this.shareNotice = '';
      this.imageCopied = this.captionCopied = false;
      for (const timer of [this.imageTimer, this.captionTimer, this.noticeTimer]) clearTimeout(timer);
    },
  },
  beforeUnmount() {
    this.active = false;
    for (const timer of [this.imageTimer, this.captionTimer, this.noticeTimer]) clearTimeout(timer);
    document.removeEventListener('visibilitychange', this.expireNoticeWhenVisible);
  },
  methods: {
    copied(kind) {
      if (!this.active) return;
      clearTimeout(this[`${kind}Timer`]);
      this[`${kind}Copied`] = true;
      this[`${kind}Timer`] = setTimeout(() => { this[`${kind}Copied`] = false; }, 2500);
    },
    showShareNotice(message) {
      if (!this.active) return;
      clearTimeout(this.noticeTimer);
      this.shareNotice = message;
      this.expireNoticeWhenVisible();
    },
    expireNoticeWhenVisible() {
      // Platform shortcuts open a new tab: keep the notice until the viewer comes back to read it.
      document.removeEventListener('visibilitychange', this.expireNoticeWhenVisible);
      if (!this.active || !this.shareNotice) return;
      if (document.hidden) { document.addEventListener('visibilitychange', this.expireNoticeWhenVisible); return; }
      clearTimeout(this.noticeTimer);
      this.noticeTimer = setTimeout(() => { this.shareNotice = ''; }, 5000);
    },
    download() {
      this.$emit('before-action');
      const url = URL.createObjectURL(this.blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = this.filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    async copyImage() {
      this.$emit('before-action');
      try {
        await copyRecapImage(this.blob);
        this.error = '';
        this.copied('image');
      } catch { this.error = 'Image copying is unavailable here. Download the PNG to attach it instead.'; }
    },
    async copyCaption() {
      this.$emit('before-action');
      try {
        await navigator.clipboard.writeText(this.captionDraft);
        this.error = '';
        this.copied('caption');
      } catch { this.error = 'Clipboard unavailable. Select the caption text to copy it.'; }
    },
    async share() {
      this.$emit('before-action');
      this.exporting = true;
      try {
        await navigator.share({ files: [new File([this.blob], this.filename, { type: 'image/png' })], title: this.shareTitle, text: this.captionDraft });
      } catch (error) {
        if (error.name !== 'AbortError') {
          this.download();
          this.showShareNotice('Sharing is unavailable here. PNG saved so you can attach it.');
        }
      } finally { if (this.active) this.exporting = false; }
    },
    preparePlatform(event, target) {
      if (this.unavailable) { event.preventDefault(); return; }
      this.$emit('before-action');
      // Keep the real anchor navigation synchronous, preserving browser activation
      // and a usable link even when clipboard permissions are refused.
      prepareRecapImage({ blob: this.blob, download: this.download, save: target.id === 'reddit' }).then(result => {
        this.showShareNotice(result === 'copied' ? `Image copied. Paste it into your ${target.label} ${target.id === 'discord' ? 'conversation' : 'post'}.${target.id === 'reddit' ? ' PNG also saved for upload.' : ''}` : `PNG saved. Attach it to your ${target.label} post.`);
      });
    },
  },
};
</script>
