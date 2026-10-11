<template>
  <!-- Native <dialog>: focus trap, Escape and top-layer stacking come from the browser. -->
  <dialog
    ref="dialog"
    class="m-auto w-[calc(100%-2rem)] max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-card border border-edge bg-panel p-0 text-ink shadow-2xl backdrop:bg-black/70 backdrop:backdrop-blur-sm"
    :class="width"
    :aria-labelledby="labelledby || null"
    @close="$emit('close')"
    @click.self="$refs.dialog.close()"
  >
    <slot />
  </dialog>
</template>

<script>
/**
 * Modal shell around the native <dialog> element.
 * Mount it with v-if; it opens on mount and emits `close` on Escape, backdrop click or close().
 */
export default {
  name: 'AppDialog',
  props: {
    width: { type: String, default: 'max-w-lg' },
    labelledby: { type: String, default: '' },
  },
  emits: ['close'],
  mounted() {
    this.$refs.dialog.showModal();
  },
  methods: {
    close() {
      this.$refs.dialog.close();
    },
  },
};
</script>
