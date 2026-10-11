<template>
  <article
    class="relative flex flex-col overflow-hidden rounded-card border bg-panel transition-colors"
    :class="selected ? 'border-brand-ink ring-2 ring-brand-ink/60' : 'border-edge hover:border-edge-strong'"
  >
    <button
      type="button"
      class="relative block aspect-[2/3] w-full cursor-pointer border-0 bg-raised p-0"
      :aria-label="`Show details for ${title}`"
      @click="$emit('open')"
    >
      <img v-if="poster" :src="poster" alt="" loading="lazy" class="absolute inset-0 h-full w-full object-cover" />
      <span v-else class="absolute inset-0 flex items-center justify-center text-3xl text-ink-4"><i :class="placeholderIcon"></i></span>
      <span v-if="badge" class="absolute left-2.5 top-2.5 rounded-md px-2 py-0.5 text-[11px] font-bold" :class="toneClass">{{ badge }}</span>
    </button>
    <slot name="overlay" />
    <div class="flex flex-1 flex-col gap-1.5 p-3">
      <h3 class="m-0 line-clamp-2 text-sm font-bold leading-snug text-ink">{{ title }}</h3>
      <slot />
      <div v-if="$slots.actions" class="mt-auto flex gap-1.5 pt-1.5">
        <slot name="actions" />
      </div>
    </div>
  </article>
</template>

<script>
const TONES = {
  caution: 'bg-caution text-[#1a1405]',
  notice: 'bg-notice text-[#06131f]',
  good: 'bg-good text-[#05180e]',
  bad: 'bg-bad text-[#2a0c0b]',
  neutral: 'bg-canvas/80 text-ink',
};

/**
 * Poster card used by every media grid (requests, approvals, AI results).
 * Clicking the poster emits `open`; buttons go in the `actions` slot.
 */
export default {
  name: 'MediaCard',
  props: {
    title: { type: String, required: true },
    poster: { type: String, default: '' },
    badge: { type: String, default: '' },
    tone: { type: String, default: 'neutral' },
    selected: { type: Boolean, default: false },
    placeholderIcon: { type: String, default: 'fas fa-film' },
  },
  emits: ['open'],
  computed: {
    toneClass() {
      return TONES[this.tone] || TONES.neutral;
    },
  },
};
</script>
