<template>
  <div class="group/row relative">
    <!-- Whole cards per view (2/3/4 by width); on phones the next card peeks out as the swipe cue. -->
    <div
      ref="row"
      class="grid snap-x snap-mandatory auto-cols-[85%] grid-flow-col gap-4 overflow-x-auto overscroll-x-contain [scrollbar-width:none] sm:auto-cols-[calc((100%-1rem)/2)] lg:auto-cols-[calc((100%-2rem)/3)] xl:auto-cols-[calc((100%-3rem)/4)] [&::-webkit-scrollbar]:hidden *:snap-start"
      @scroll.passive="updateArrows"
    >
      <slot />
    </div>
    <!-- Arrows show while the pointer is over the row (or a key is focused in it), sliding in from their side. -->
    <Transition v-bind="fade">
    <button
      v-if="canScrollBack"
      type="button"
      class="absolute -left-4 top-1/2 z-10 hidden h-10 w-10 -translate-y-1/2 cursor-pointer place-items-center rounded-full border border-edge-strong bg-panel text-ink shadow-lg transition duration-200 hover:bg-panel-2 focus-visible:translate-x-0 focus-visible:opacity-100 group-hover/row:translate-x-0 group-hover/row:opacity-100 group-focus-within/row:translate-x-0 group-focus-within/row:opacity-100 motion-reduce:transition-none sm:grid [@media(hover:hover)]:translate-x-2 [@media(hover:hover)]:opacity-0"
      :aria-label="`Previous ${label}`"
      @click="page(-1)"
    >
      <i aria-hidden="true" class="fas fa-chevron-left"></i>
    </button>
    </Transition>
    <Transition v-bind="fade">
    <button
      v-if="canScrollForward"
      type="button"
      class="absolute -right-4 top-1/2 z-10 hidden h-10 w-10 -translate-y-1/2 cursor-pointer place-items-center rounded-full border border-edge-strong bg-panel text-ink shadow-lg transition duration-200 hover:bg-panel-2 focus-visible:translate-x-0 focus-visible:opacity-100 group-hover/row:translate-x-0 group-hover/row:opacity-100 group-focus-within/row:translate-x-0 group-focus-within/row:opacity-100 motion-reduce:transition-none sm:grid [@media(hover:hover)]:-translate-x-2 [@media(hover:hover)]:opacity-0"
      :aria-label="`Next ${label}`"
      @click="page(1)"
    >
      <i aria-hidden="true" class="fas fa-chevron-right"></i>
    </button>
    </Transition>
  </div>
</template>

<script>
/**
 * Horizontal row of cards that pages with arrow buttons instead of a scrollbar.
 * The arrows appear only when there is more to see in that direction.
 */
export default {
  name: 'CardRow',
  props: {
    // Names the arrows for screen readers ("Next titles ready to watch").
    label: { type: String, default: 'items' },
  },
  data() {
    return {
      canScrollBack: false,
      canScrollForward: false,
      // Arrows also fade when they appear or go at either end of the row.
      fade: {
        enterActiveClass: 'transition-opacity duration-200 motion-reduce:transition-none',
        leaveActiveClass: 'transition-opacity duration-200 motion-reduce:transition-none',
        enterFromClass: '!opacity-0',
        leaveToClass: '!opacity-0',
      },
    };
  },
  mounted() {
    this.observer = new ResizeObserver(() => this.updateArrows());
    this.observer.observe(this.$refs.row);
    this.updateArrows();
  },
  updated() {
    this.updateArrows();
  },
  beforeUnmount() {
    this.observer?.disconnect();
  },
  methods: {
    updateArrows() {
      const row = this.$refs.row;
      if (!row) return;
      this.canScrollBack = row.scrollLeft > 1;
      this.canScrollForward = row.scrollLeft + row.clientWidth < row.scrollWidth - 1;
    },
    page(direction) {
      const row = this.$refs.row;
      // One view width plus the gap lands exactly on the next whole card.
      const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      row.scrollBy({ left: direction * (row.clientWidth + 16), behavior: reduce ? 'auto' : 'smooth' });
    },
  },
};
</script>
