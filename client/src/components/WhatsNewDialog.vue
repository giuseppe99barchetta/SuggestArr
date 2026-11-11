<template>
  <AppDialog width="max-w-3xl" :title="entry.title" :subtitle="`What's new · ${position}`" icon="fas fa-wand-magic-sparkles" body-class="p-0" @close="$emit('close')">
    <div class="overflow-hidden" aria-live="polite" data-testid="whats-new-slide">
      <transition mode="out-in" enter-active-class="transition duration-200 motion-reduce:transition-none" leave-active-class="transition duration-150 motion-reduce:transition-none" :enter-from-class="enterFrom" :leave-to-class="leaveTo">
        <div :key="index" class="grid min-w-0 sm:grid-cols-[minmax(0,15rem)_minmax(0,1fr)]">
          <!-- Visual: the slide's icon on a tinted panel; decorative only. -->
          <div class="relative flex items-center justify-center overflow-hidden border-edge py-8 max-sm:border-b sm:border-r sm:py-0" :class="tone.panel" aria-hidden="true">
            <div class="absolute inset-0 opacity-[.14]" :class="tone.text" style="background-image: radial-gradient(currentColor 1px, transparent 1px); background-size: 14px 14px; mask-image: radial-gradient(circle at center, #000 30%, transparent 75%);"></div>
            <div class="absolute h-44 w-44 rounded-full border opacity-30" :class="tone.ring"></div>
            <div class="absolute h-64 w-64 rounded-full border opacity-15" :class="tone.ring"></div>
            <div class="absolute h-28 w-28 rounded-full blur-2xl" :class="tone.glow"></div>
            <div class="relative flex h-20 w-20 items-center justify-center rounded-2xl border bg-panel/80 shadow-lg backdrop-blur-sm max-sm:h-16 max-sm:w-16" :class="[tone.ring, tone.text]">
              <i class="fas text-[2rem] max-sm:text-2xl" :class="slide.icon"></i>
            </div>
            <span class="absolute bottom-3 left-4 font-mono text-[11px] font-semibold tracking-widest opacity-70 max-sm:hidden" :class="tone.text">{{ String(index + 1).padStart(2, '0') }} / {{ String(entry.slides.length).padStart(2, '0') }}</span>
          </div>

          <div class="flex min-w-0 flex-col gap-3 p-6 max-sm:p-4">
            <h3 class="m-0 text-xl leading-snug font-bold text-ink">{{ slide.heading }}</h3>
            <p class="m-0 text-[15px] leading-relaxed text-ink-2">{{ slide.text }}</p>
            <ul v-if="slide.points?.length" class="m-0 mt-1 flex list-none flex-col gap-2.5 p-0">
              <li v-for="point in slide.points" :key="point" class="flex gap-2.5 text-sm leading-snug text-ink-3">
                <i aria-hidden="true" class="fas fa-circle-check mt-0.5 shrink-0" :class="tone.text"></i>
                <span>{{ point }}</span>
              </li>
            </ul>
          </div>
        </div>
      </transition>
    </div>

    <template #footer>
      <div class="mr-auto flex w-28 items-center gap-1 max-sm:w-20" role="group" aria-label="Slides">
        <button
          v-for="(item, i) in entry.slides"
          :key="i"
          type="button"
          class="h-1.5 min-w-0 flex-1 cursor-pointer rounded-full border-0 p-0 transition-colors"
          :class="i <= index ? 'bg-brand' : 'bg-edge-strong hover:bg-ink-4'"
          :aria-label="`Go to slide ${i + 1} of ${entry.slides.length}: ${item.heading}`"
          :aria-current="i === index ? 'step' : null"
          @click="go(i)"
        ></button>
      </div>
      <a :href="releasesUrl" target="_blank" rel="noopener" aria-label="All release notes" class="mr-1 text-xs text-ink-3 underline underline-offset-2 hover:text-ink max-sm:mr-0 max-sm:p-2 max-sm:no-underline"><span class="max-sm:hidden">All release notes</span><span class="sm:hidden"><i aria-hidden="true" class="fas fa-clock-rotate-left"></i></span></a>
      <button v-if="index > 0" type="button" class="ui-btn" @click="go(index - 1)"><i aria-hidden="true" class="fas fa-arrow-left"></i>Back</button>
      <button v-if="!isLast" type="button" class="ui-btn-primary" @click="go(index + 1)">Next<i aria-hidden="true" class="fas fa-arrow-right ml-1"></i></button>
      <button v-else type="button" class="ui-btn-primary" @click="$emit('close')">Done</button>
    </template>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import { RELEASES_URL } from '@/data/releaseNotes.js';

// Full class names, so Tailwind keeps them.
const TONES = {
  brand: { panel: 'bg-gradient-to-br from-brand/30 via-brand/10 to-transparent', text: 'text-brand-ink', ring: 'border-brand/50', glow: 'bg-brand/40' },
  good: { panel: 'bg-gradient-to-br from-good/25 via-good/10 to-transparent', text: 'text-good', ring: 'border-good/50', glow: 'bg-good/35' },
  caution: { panel: 'bg-gradient-to-br from-caution/25 via-caution/10 to-transparent', text: 'text-caution', ring: 'border-caution/50', glow: 'bg-caution/35' },
};

/**
 * Step-through release note: one slide per change, with an icon, a heading, a short text and
 * optional `points`. Open it with v-if; it emits `close` (Escape, backdrop, X or Done).
 */
export default {
  name: 'WhatsNewDialog',
  components: { AppDialog },
  props: {
    /** The release note, whose `slides` were already filtered for this viewer. */
    entry: { type: Object, required: true },
  },
  emits: ['close'],
  data() {
    return { index: 0, direction: 1 };
  },
  computed: {
    slide() {
      return this.entry.slides[this.index];
    },
    tone() {
      return TONES[this.slide.tone] || TONES.brand;
    },
    releasesUrl() {
      return RELEASES_URL;
    },
    isLast() {
      return this.index === this.entry.slides.length - 1;
    },
    position() {
      return `${this.index + 1} of ${this.entry.slides.length}`;
    },
    enterFrom() {
      return this.direction > 0 ? 'translate-x-4 opacity-0' : '-translate-x-4 opacity-0';
    },
    leaveTo() {
      return this.direction > 0 ? '-translate-x-4 opacity-0' : 'translate-x-4 opacity-0';
    },
  },
  mounted() {
    window.addEventListener('keydown', this.onKey);
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this.onKey);
  },
  methods: {
    go(target) {
      if (target < 0 || target >= this.entry.slides.length || target === this.index) return;
      this.direction = target > this.index ? 1 : -1;
      this.index = target;
    },
    onKey(event) {
      if (event.key === 'ArrowRight') this.go(this.index + 1);
      else if (event.key === 'ArrowLeft') this.go(this.index - 1);
    },
  },
};
</script>
