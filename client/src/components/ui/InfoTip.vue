<template>
  <span class="inline-flex align-middle" @mouseenter="show" @mouseleave="hide">
    <button
      ref="trigger"
      type="button"
      class="grid h-5 w-5 cursor-help place-items-center rounded-full border-0 bg-transparent p-0 text-[12px] text-ink-4 hover:text-brand-ink focus-visible:text-brand-ink"
      :aria-label="label"
      :aria-describedby="open ? tipId : null"
      @focus="show"
      @blur="hide"
      @click.prevent="open ? hide() : show()"
      @keydown.esc.stop="hide"
    ><i aria-hidden="true" class="fas fa-circle-info"></i></button>
    <!-- Teleported and fixed so the scrolling modal body never clips it. -->
    <Teleport to="body">
      <span
        v-if="open"
        :id="tipId"
        role="tooltip"
        class="pointer-events-none fixed z-[1100] w-max max-w-[18rem] rounded-[8px] border border-edge-strong bg-raised px-3 py-2 text-xs font-normal leading-snug text-ink-2 shadow-xl"
        :style="position"
      >{{ text }}</span>
    </Teleport>
  </span>
</template>

<script>
let nextId = 0;
const GAP = 8;
const MARGIN = 12;
const MAX_WIDTH = 288;

/**
 * Small "i" button that explains a field on hover, focus or tap.
 * The bubble is placed above the icon, or below when there is no room, and kept inside the viewport.
 */
export default {
  name: 'InfoTip',
  props: {
    /** Explanation shown in the bubble. */
    text: { type: String, required: true },
    /** Accessible name of the icon button. */
    label: { type: String, default: 'More information' },
  },
  data() {
    return { open: false, position: {}, tipId: `info-tip-${++nextId}` };
  },
  beforeUnmount() {
    window.removeEventListener('scroll', this.hide, true);
  },
  methods: {
    show() {
      const rect = this.$refs.trigger.getBoundingClientRect();
      const width = Math.min(MAX_WIDTH, window.innerWidth - MARGIN * 2);
      const left = Math.min(Math.max(rect.left + rect.width / 2 - width / 2, MARGIN), window.innerWidth - width - MARGIN);
      const above = rect.top > 120;
      this.position = {
        left: `${left}px`,
        maxWidth: `${width}px`,
        ...(above
          ? { bottom: `${window.innerHeight - rect.top + GAP}px` }
          : { top: `${rect.bottom + GAP}px` }),
      };
      this.open = true;
      // A scroll moves the icon away from the fixed bubble, so just close it.
      window.addEventListener('scroll', this.hide, true);
    },
    hide() {
      this.open = false;
      window.removeEventListener('scroll', this.hide, true);
    },
  },
};
</script>
