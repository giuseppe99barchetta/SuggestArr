<template>
  <div role="status" class="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-4">
    <span class="sr-only">{{ label }}</span>
    <div v-for="n in count" :key="n" aria-hidden="true" class="flex flex-col overflow-hidden rounded-card border border-edge bg-panel">
      <div class="aspect-[2/3] w-full animate-pulse bg-raised"></div>
      <div class="flex flex-col gap-2 p-3">
        <div class="h-3.5 w-4/5 animate-pulse rounded bg-panel-2"></div>
        <div class="h-3 w-1/2 animate-pulse rounded bg-panel-2"></div>
        <div class="h-3 w-3/5 animate-pulse rounded bg-panel-2"></div>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * Loading placeholder for every MediaCard grid, shaped like the real cards.
 */
export default {
  name: 'MediaGridSkeleton',
  props: {
    count: { type: Number, default: 12 },
    label: { type: String, default: 'Loading…' },
  },
};
</script>
