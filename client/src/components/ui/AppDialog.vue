<template>
  <!-- Native <dialog>: focus trap, Escape and top-layer stacking come from the browser. -->
  <dialog
    ref="dialog"
    autofocus
    class="m-auto w-[calc(100%-2rem)] max-h-[calc(100dvh-2rem)] overflow-hidden rounded-card border border-edge bg-panel p-0 text-ink shadow-2xl outline-none backdrop:bg-black/70 backdrop:backdrop-blur-sm open:flex open:flex-col"
    :class="width"
    :aria-labelledby="title ? titleId : (labelledby || null)"
    @close="$emit('close')"
    @click.self="close"
  >
    <header v-if="title" class="flex shrink-0 items-start gap-3 border-b border-edge px-6 py-4 max-sm:px-4">
      <span
        v-if="icon"
        aria-hidden="true"
        class="grid h-9 w-9 shrink-0 place-items-center rounded-ctl text-sm"
        :class="tone === 'danger' ? 'bg-bad/15 text-bad' : 'bg-brand-soft text-brand-ink'"
      ><i :class="icon"></i></span>
      <div class="min-w-0 flex-1 self-center">
        <h2 :id="titleId" class="m-0 text-base font-bold text-ink">{{ title }}</h2>
        <p v-if="subtitle || $slots.subtitle" class="m-0 mt-0.5 text-[13px] text-ink-3"><slot name="subtitle">{{ subtitle }}</slot></p>
      </div>
      <button type="button" class="-mr-2 grid h-9 w-9 shrink-0 cursor-pointer place-items-center rounded-[8px] border-0 bg-transparent text-ink-3 hover:bg-raised hover:text-ink" aria-label="Close" @click="close">
        <i aria-hidden="true" class="fas fa-times"></i>
      </button>
    </header>

    <div class="min-h-0 flex-1 overflow-y-auto" :class="title ? bodyClass : ''">
      <slot />
    </div>

    <footer v-if="$slots.footer" class="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-edge bg-panel-2/50 px-6 py-3 max-sm:px-4">
      <slot name="footer" />
    </footer>
  </dialog>
</template>

<script>
let nextId = 0;

/**
 * Modal shell around the native <dialog> element.
 * Mount it with v-if; it opens on mount and emits `close` on Escape, backdrop click or close().
 * Pass `title` for the standard header with close button; the `footer` slot sticks to the bottom.
 */
export default {
  name: 'AppDialog',
  props: {
    width: { type: String, default: 'max-w-lg' },
    labelledby: { type: String, default: '' },
    title: { type: String, default: '' },
    subtitle: { type: String, default: '' },
    icon: { type: String, default: '' },
    tone: { type: String, default: '' },
    bodyClass: { type: String, default: 'p-6 max-sm:p-4' },
  },
  emits: ['close'],
  data() {
    return { titleId: `app-dialog-title-${++nextId}` };
  },
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
