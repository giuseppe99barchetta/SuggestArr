<template>
  <div ref="root" class="relative">
    <button
      ref="trigger"
      type="button"
      class="ui-btn w-10 px-0"
      aria-haspopup="menu"
      :aria-expanded="open ? 'true' : 'false'"
      :aria-label="label"
      :title="label"
      @click="toggle"
    >
      <i aria-hidden="true" class="fas fa-ellipsis-h"></i>
    </button>
    <div
      v-if="open"
      ref="menu"
      role="menu"
      :aria-label="label"
      class="absolute right-0 top-full z-20 mt-1.5 flex min-w-[190px] flex-col rounded-ctl border border-edge-strong bg-panel-2 p-1 shadow-2xl shadow-black/40"
      @keydown="onKeydown"
    >
      <template v-for="(item, index) in items" :key="item.label">
        <div v-if="item.danger && index > 0" role="separator" class="my-1 h-px bg-edge"></div>
        <button
          type="button"
          role="menuitem"
          class="flex cursor-pointer items-center gap-2.5 rounded-[6px] border-0 bg-transparent px-3 py-2 text-left text-sm font-medium focus-visible:outline-none"
          :class="item.danger ? 'text-bad hover:bg-bad/15 focus-visible:bg-bad/15' : 'text-ink-2 hover:bg-raised hover:text-ink focus-visible:bg-raised focus-visible:text-ink'"
          @click="select(item)"
        >
          <i aria-hidden="true" :class="item.icon" class="w-4 text-center"></i>{{ item.label }}
        </button>
      </template>
    </div>
  </div>
</template>

<script>
/**
 * "More actions" button with a small menu. Closes on Escape, outside clicks and after a choice;
 * arrow keys move between items.
 */
export default {
  name: 'ActionMenu',
  props: {
    label: { type: String, default: 'More actions' },
    // [{ label, icon, onSelect, danger? }]
    items: { type: Array, required: true },
  },
  data() {
    return { open: false };
  },
  beforeUnmount() {
    document.removeEventListener('pointerdown', this.onOutside);
  },
  methods: {
    toggle() {
      if (this.open) this.close();
      else this.show();
    },
    async show() {
      this.open = true;
      document.addEventListener('pointerdown', this.onOutside);
      await this.$nextTick();
      this.menuItems()[0]?.focus();
    },
    close(refocus = false) {
      this.open = false;
      document.removeEventListener('pointerdown', this.onOutside);
      if (refocus) this.$refs.trigger?.focus();
    },
    select(item) {
      this.close();
      item.onSelect();
    },
    menuItems() {
      return [...(this.$refs.menu?.querySelectorAll('[role="menuitem"]') || [])];
    },
    onOutside(event) {
      if (!this.$refs.root?.contains(event.target)) this.close();
    },
    onKeydown(event) {
      if (event.key === 'Escape' || event.key === 'Tab') {
        if (event.key === 'Escape') event.preventDefault();
        this.close(event.key === 'Escape');
        return;
      }
      const step = { ArrowDown: 1, ArrowUp: -1 }[event.key];
      if (!step) return;
      event.preventDefault();
      const items = this.menuItems();
      const next = (items.indexOf(document.activeElement) + step + items.length) % items.length;
      items[next]?.focus();
    },
  },
};
</script>
