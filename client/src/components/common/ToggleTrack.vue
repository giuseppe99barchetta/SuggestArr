<template>
  <!-- Visual switch only: the parent <button role="switch"> carries the name, state and keyboard handling. -->
  <span
    aria-hidden="true"
    class="relative inline-block h-[22px] w-10 shrink-0 rounded-full transition-colors"
    :class="on ? 'bg-brand' : 'bg-edge-strong'"
  >
    <span
      class="absolute left-[3px] top-[3px] h-4 w-4 rounded-full bg-white transition-transform"
      :class="on ? 'translate-x-[18px]' : ''"
    ></span>
  </span>
</template>

<script>
export default {
  name: 'ToggleTrack',

  props: {
    /**
     * Whether the switch is on.
     */
    on: {
      type: Boolean,
      default: false,
    },
  },
};
</script>
