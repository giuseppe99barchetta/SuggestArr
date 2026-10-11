<template>
  <section class="flex min-w-0 flex-col rounded-card border border-edge bg-panel p-5">
    <header class="mb-4 flex items-start gap-3.5">
      <span v-if="icon" class="flex h-10 w-10 shrink-0 items-center justify-center rounded-ctl bg-raised text-ink-2"><i aria-hidden="true" :class="icon"></i></span>
      <div class="flex min-w-0 flex-1 flex-col gap-1">
        <h2 class="m-0 text-[17px] font-bold text-ink">{{ title }}</h2>
        <p v-if="description" class="m-0 text-[13px] leading-relaxed text-ink-3">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="flex shrink-0 gap-2"><slot name="actions" /></div>
    </header>
    <slot />
  </section>
</template>

<script>
/** Settings card with an icon, title and one-line purpose; the body goes in the default slot. */
export default {
  name: 'SectionCard',
  props: {
    icon: { type: String, default: '' },
    title: { type: String, required: true },
    description: { type: String, default: '' },
  },
};
</script>
