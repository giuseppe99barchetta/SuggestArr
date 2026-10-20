<template>
  <header class="flex flex-wrap items-center gap-x-4 gap-y-3" :class="folded ? '' : 'mb-5'">
    <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-ctl bg-raised text-ink-2"><i aria-hidden="true" :class="icon"></i></span>
    <div class="flex min-w-0 flex-[1_1_220px] flex-col gap-0.5">
      <h2 class="m-0 text-[15px] font-bold text-ink">{{ title }}</h2>
      <p class="m-0 truncate text-[13px] leading-relaxed text-ink-3" :class="{ 'whitespace-normal': !folded || !summary }">{{ folded && summary ? summary : description }}</p>
    </div>
    <span class="inline-flex items-center gap-1.5 whitespace-nowrap text-[13px] font-semibold" :class="tone.text">
      <span class="h-2 w-2 rounded-full" :class="tone.dot"></span>{{ statusText }}
    </span>
    <button v-if="status === 'status-connected'" type="button" class="ui-btn h-9 px-3 text-[13px]" :aria-expanded="String(!folded)" :aria-label="`${folded ? 'Edit' : 'Done editing'} ${title}`" @click="$emit('toggle')">
      <i aria-hidden="true" :class="folded ? 'fas fa-pen' : 'fas fa-chevron-up'"></i>{{ folded ? 'Edit' : 'Done' }}
    </button>
  </header>
</template>

<script>
const TONES = {
  'status-connected': { text: 'text-good', dot: 'bg-good' },
  'status-warning': { text: 'text-caution', dot: 'bg-caution' },
  'status-disconnected': { text: 'text-ink-3', dot: 'bg-ink-4' },
};

/**
 * Header of a service card on the Connections page: what the service is for and its state.
 * `status` takes the status-* classes the Connections page already computes.
 */
export default {
  name: 'ServiceCardHeader',
  props: {
    icon: { type: String, required: true },
    title: { type: String, required: true },
    description: { type: String, required: true },
    status: { type: String, default: 'status-disconnected' },
    statusText: { type: String, default: '' },
    // Folded cards show only this header, with `summary` (when given) in place of the description.
    folded: { type: Boolean, default: false },
    summary: { type: String, default: '' },
  },
  emits: ['toggle'],
  computed: {
    tone() {
      return TONES[this.status] || TONES['status-disconnected'];
    },
  },
};
</script>
