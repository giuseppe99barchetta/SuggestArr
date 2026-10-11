<template>
  <header class="mb-5 flex flex-wrap items-start gap-x-4 gap-y-3">
    <span class="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-ctl bg-raised text-ink-2"><i :class="icon"></i></span>
    <div class="flex min-w-0 flex-[1_1_220px] flex-col gap-1">
      <div class="flex flex-wrap items-center gap-2">
        <h2 class="m-0 text-[17px] font-bold text-ink">{{ title }}</h2>
        <span class="text-[11px] font-bold tracking-wider text-ink-4">{{ required ? 'REQUIRED' : 'OPTIONAL' }}</span>
      </div>
      <p class="m-0 text-[13px] leading-relaxed text-ink-3">{{ description }}</p>
    </div>
    <span class="inline-flex items-center gap-1.5 whitespace-nowrap text-[13px] font-semibold" :class="tone.text">
      <span class="h-2 w-2 rounded-full" :class="tone.dot"></span>{{ statusText }}
    </span>
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
    required: { type: Boolean, default: false },
    status: { type: String, default: 'status-disconnected' },
    statusText: { type: String, default: '' },
  },
  computed: {
    tone() {
      return TONES[this.status] || TONES['status-disconnected'];
    },
  },
};
</script>
