<template>
  <span
    class="inline-grid shrink-0 place-items-center rounded-full shadow-[0_2px_8px_rgba(0,0,0,0.45)]"
    :class="[state.tone, small ? 'h-5 w-5 text-[9px]' : 'h-6 w-6 text-[11px]']"
    :title="state.label"
  >
    <i aria-hidden="true" :class="state.icon"></i>
    <span class="sr-only">{{ state.label }}</span>
  </span>
</template>

<script>
import { mediaStatus } from '@/utils/mediaStatus.js';

/**
 * One small icon for how far a requested title has come: requested, downloading, available or watched.
 */
export default {
  name: 'MediaStatusBadge',
  props: {
    watchedAt: { type: [String, Number, Date], default: null },
    availability: { type: String, default: null },
    small: { type: Boolean, default: false },
  },
  computed: {
    state() {
      return mediaStatus(this.watchedAt, this.availability);
    },
  },
};
</script>
