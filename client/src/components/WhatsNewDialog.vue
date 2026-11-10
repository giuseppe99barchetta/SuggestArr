<template>
  <AppDialog width="max-w-2xl" :title="entry.title" :subtitle="`What's new · ${position}`" icon="fas fa-gift" body-class="p-0" @close="$emit('close')">
    <div class="flex min-h-[19rem] flex-col gap-5 p-6 max-sm:p-4 sm:flex-row sm:items-start" aria-live="polite" data-testid="whats-new-slide">
      <transition mode="out-in" enter-active-class="transition duration-200 motion-reduce:transition-none" leave-active-class="transition duration-150 motion-reduce:transition-none" :enter-from-class="enterFrom" :leave-to-class="leaveTo">
        <div :key="index" class="flex min-w-0 flex-1 flex-col gap-5 sm:flex-row sm:items-start">
          <div class="grid h-32 w-32 shrink-0 place-items-center self-center rounded-card border sm:h-40 sm:w-40" :class="toneClass(slide.tone)" aria-hidden="true">
            <span class="block h-24 w-24 sm:h-28 sm:w-28 [&>svg]:h-full [&>svg]:w-full" v-html="iconSvg(slide.icon)"></span>
          </div>
          <div class="flex min-w-0 flex-1 flex-col gap-4">
            <h3 class="m-0 text-lg font-bold text-ink">{{ slide.heading }}</h3>
            <section>
              <p class="m-0 mb-1 text-[11px] font-bold tracking-wider text-ink-4 uppercase">What changed</p>
              <p class="m-0 text-sm leading-relaxed text-ink-2">{{ slide.changes }}</p>
            </section>
            <section>
              <p class="m-0 mb-1 text-[11px] font-bold tracking-wider text-ink-4 uppercase">What it means for you</p>
              <p class="m-0 text-sm leading-relaxed text-ink-2">{{ slide.impact }}</p>
            </section>
            <button v-if="ctaVisible" type="button" class="ui-btn self-start" @click="$emit('navigate', slide.cta.tab)">
              <i aria-hidden="true" class="fas fa-arrow-right"></i>{{ slide.cta.label }}
            </button>
          </div>
        </div>
      </transition>
    </div>

    <template #footer>
      <div class="mr-auto flex items-center gap-1.5" role="group" aria-label="Slides">
        <button
          v-for="(item, i) in entry.slides"
          :key="i"
          type="button"
          class="h-2.5 w-2.5 cursor-pointer rounded-full border-0 p-0 transition-colors"
          :class="i === index ? 'bg-brand' : 'bg-edge-strong hover:bg-ink-4'"
          :aria-label="`Go to slide ${i + 1} of ${entry.slides.length}: ${item.heading}`"
          :aria-current="i === index ? 'step' : null"
          @click="go(i)"
        ></button>
      </div>
      <select v-if="entries.length > 1" v-model="entryId" class="ui-input h-8 max-w-[11rem] py-0 text-xs" aria-label="Release notes">
        <option v-for="item in entries" :key="item.id" :value="item.id">{{ item.title }}</option>
      </select>
      <a v-if="showAllLink" href="#" class="mr-1 text-xs text-ink-3 underline underline-offset-2 hover:text-ink" @click.prevent="$emit('all-notes')">All release notes</a>
      <button v-if="index > 0" type="button" class="ui-btn" @click="go(index - 1)"><i aria-hidden="true" class="fas fa-arrow-left"></i>Back</button>
      <button v-if="!isLast" type="button" class="ui-btn-primary" @click="go(index + 1)">Next<i aria-hidden="true" class="fas fa-arrow-right ml-1"></i></button>
      <button v-else type="button" class="ui-btn-primary" @click="$emit('close')">Done</button>
    </template>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';

// Slide art lives in src/assets/whats-new/<entry id>/<icon>.svg and is inlined so `currentColor` follows the tone.
const ICONS = import.meta.glob('../assets/whats-new/*/*.svg', { eager: true, query: '?raw', import: 'default' });

const TONES = {
  brand: 'border-brand-soft bg-brand-soft/40 text-brand-ink',
  good: 'border-good/30 bg-good/10 text-good',
  caution: 'border-caution/30 bg-caution/10 text-caution',
};

/**
 * Step-through release note: one slide per change, with an icon, what changed and what it means.
 * Open it with v-if; it emits `close` (Escape, backdrop, X or Done), `navigate` (slide button) and `all-notes`.
 */
export default {
  name: 'WhatsNewDialog',
  components: { AppDialog },
  props: {
    /** Release entries, newest first, whose `slides` were already filtered for this viewer. */
    entries: { type: Array, required: true },
    /** Id of the entry to open on; the first one when empty. */
    startId: { type: String, default: '' },
    /** Dashboard tab ids this viewer can open; a slide button to another tab is hidden. */
    availableTabs: { type: Array, default: () => [] },
    showAllLink: { type: Boolean, default: false },
  },
  emits: ['close', 'navigate', 'all-notes'],
  data() {
    return { index: 0, direction: 1, entryId: this.startId || this.entries[0].id };
  },
  computed: {
    entry() {
      return this.entries.find(item => item.id === this.entryId) || this.entries[0];
    },
    slide() {
      return this.entry.slides[this.index];
    },
    isLast() {
      return this.index === this.entry.slides.length - 1;
    },
    position() {
      return `${this.index + 1} of ${this.entry.slides.length}`;
    },
    ctaVisible() {
      return !!this.slide.cta && this.availableTabs.includes(this.slide.cta.tab);
    },
    enterFrom() {
      return this.direction > 0 ? 'translate-x-4 opacity-0' : '-translate-x-4 opacity-0';
    },
    leaveTo() {
      return this.direction > 0 ? '-translate-x-4 opacity-0' : 'translate-x-4 opacity-0';
    },
  },
  watch: {
    entryId() {
      this.index = 0;
      this.direction = 1;
    },
  },
  mounted() {
    window.addEventListener('keydown', this.onKey);
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this.onKey);
  },
  methods: {
    iconSvg(name) {
      return ICONS[`../assets/whats-new/${this.entry.id}/${name}`] || '';
    },
    toneClass(tone) {
      return TONES[tone] || TONES.brand;
    },
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
