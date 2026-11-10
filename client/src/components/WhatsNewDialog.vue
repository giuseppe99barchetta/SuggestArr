<template>
  <AppDialog width="max-w-2xl" :title="entry.title" :subtitle="`What's new · ${position}`" icon="fas fa-gift" body-class="p-0" @close="$emit('close')">
    <div class="flex flex-col sm:min-h-[26rem]" aria-live="polite" data-testid="whats-new-slide">
      <transition mode="out-in" enter-active-class="transition duration-200 motion-reduce:transition-none" leave-active-class="transition duration-150 motion-reduce:transition-none" :enter-from-class="enterFrom" :leave-to-class="leaveTo">
        <div :key="index" class="flex min-w-0 flex-1 flex-col">
          <!-- The illustration is the point of each slide: big, labelled, tinted by what kind of change it is. -->
          <div class="relative flex h-56 shrink-0 items-center justify-center overflow-hidden border-b border-edge px-4 max-sm:h-40" :class="toneClass(slide.tone)" aria-hidden="true">
            <span class="pointer-events-none absolute -top-16 -right-10 h-56 w-56 rounded-full bg-current opacity-[0.08] blur-2xl"></span>
            <span class="pointer-events-none absolute -bottom-20 -left-10 h-48 w-48 rounded-full bg-current opacity-[0.06] blur-2xl"></span>
            <WhatsNewArt v-if="slide.art" :art="slide.art" class="relative block h-52 w-full max-w-lg max-sm:h-36" />
            <span v-else class="relative block h-52 w-full max-w-lg max-sm:h-36 [&>svg]:h-full [&>svg]:w-full" v-html="iconSvg(slide.icon)"></span>
          </div>
          <div class="flex flex-col gap-4 p-5 max-sm:p-4">
            <h3 class="m-0 text-xl font-bold text-ink">{{ slide.heading }}</h3>
            <div class="grid gap-3 sm:grid-cols-2">
              <section class="rounded-ctl border border-edge bg-panel-2/60 p-3.5">
                <p class="m-0 mb-1.5 flex items-center gap-1.5 text-[11px] font-bold tracking-wider text-ink-4 uppercase"><i aria-hidden="true" class="fas fa-bolt text-brand-ink"></i>What changed</p>
                <p class="m-0 text-sm leading-relaxed text-ink-2">{{ slide.changes }}</p>
              </section>
              <section class="rounded-ctl border border-edge bg-panel-2/60 p-3.5">
                <p class="m-0 mb-1.5 flex items-center gap-1.5 text-[11px] font-bold tracking-wider text-ink-4 uppercase"><i aria-hidden="true" class="fas fa-user-check text-good"></i>What it means for you</p>
                <p class="m-0 text-sm leading-relaxed text-ink-2">{{ slide.impact }}</p>
              </section>
            </div>
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
import WhatsNewArt from '@/components/WhatsNewArt.vue';

// Most slides are drawn from data (WhatsNewArt). The rare `icon` slide uses a file in
// src/assets/whats-new/<entry id>/<icon>.svg, inlined so `currentColor` follows the tone.
const ICONS = import.meta.glob('../assets/whats-new/*/*.svg', { eager: true, query: '?raw', import: 'default' });

const TONES = {
  brand: 'bg-gradient-to-br from-brand/25 via-brand/10 to-transparent text-brand-ink',
  good: 'bg-gradient-to-br from-good/25 via-good/10 to-transparent text-good',
  caution: 'bg-gradient-to-br from-caution/25 via-caution/10 to-transparent text-caution',
};

/**
 * Step-through release note: one slide per change, with an icon, what changed and what it means.
 * Open it with v-if; it emits `close` (Escape, backdrop, X or Done), `navigate` (slide button) and `all-notes`.
 */
export default {
  name: 'WhatsNewDialog',
  components: { AppDialog, WhatsNewArt },
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
