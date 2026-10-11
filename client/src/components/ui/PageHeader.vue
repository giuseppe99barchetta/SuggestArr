<template>
  <header class="mb-7 flex flex-wrap items-end justify-between gap-4">
    <div>
      <h1 class="m-0 text-3xl font-extrabold tracking-tight text-ink">{{ title }}</h1>
      <p v-if="subtitle" class="m-0 mt-1.5 max-w-2xl text-[15px] text-ink-3">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.default" class="flex flex-wrap gap-2.5">
      <slot />
    </div>
  </header>
</template>

<script>
/** Page title row shared by every dashboard screen; actions go in the default slot. */
export default {
  name: 'PageHeader',
  props: {
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
  },
};
</script>
