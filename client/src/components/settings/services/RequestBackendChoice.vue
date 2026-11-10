<template>
  <div data-testid="request-backend-choice" role="radiogroup" aria-label="Request backend" class="grid grid-cols-1 gap-3 md:grid-cols-3">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="radio"
      :aria-checked="current === option.value"
      :disabled="disabled"
      class="relative flex min-w-0 cursor-pointer flex-col gap-1.5 rounded-xl border-2 p-4 text-left transition duration-200"
      :class="current === option.value ? 'border-brand bg-brand/6 shadow-[0_0_0_3px] shadow-brand/25' : 'border-edge bg-panel hover:border-brand-ink'"
      @click="select(option.value)"
    >
      <span class="flex items-center gap-2 text-[0.95rem] font-semibold text-ink">
        <i aria-hidden="true" :class="option.icon"></i>{{ option.label }}
        <i v-if="current === option.value" aria-hidden="true" class="fas fa-check-circle ml-auto text-good"></i>
      </span>
      <span class="text-[0.82rem] leading-normal text-ink-3">{{ option.description }}</span>
    </button>
  </div>
</template>

<script>
/**
 * Picks where requests are delivered: Seer, straight to Radarr/Sonarr, or both
 * (Seer requests, Radarr/Sonarr as an extra library check).
 * Works with `v-model` (dashboard) and with the setup wizard's `config` + `update-config` pair.
 */
export const REQUEST_BACKENDS = [
  { value: 'seer', label: 'Seer', icon: 'fas fa-inbox',
    description: 'Requests go through Seer: users, approvals in Seer, expiry and replacement of rejected requests.' },
  { value: 'arr', label: 'Radarr & Sonarr', icon: 'fas fa-bolt',
    description: 'Titles are added straight to Radarr and Sonarr. No Seer needed; Seer-only features are off.' },
  { value: 'both', label: 'Both', icon: 'fas fa-layer-group',
    description: 'Seer keeps handling requests; Radarr and Sonarr also tell SuggestArr what you already own.' },
];

export default {
  name: 'RequestBackendChoice',
  inheritAttrs: false, // the wizard passes generic step props this component does not use
  props: {
    modelValue: { type: String, default: null },
    config: { type: Object, default: null },
    disabled: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'update-config'],
  data() {
    return { options: REQUEST_BACKENDS };
  },
  computed: {
    current() {
      return this.modelValue || this.config?.REQUEST_BACKEND || 'seer';
    },
  },
  mounted() {
    // Make the (default) choice part of the wizard's config so it is saved explicitly.
    if (this.config && !this.config.REQUEST_BACKEND) this.$emit('update-config', 'REQUEST_BACKEND', 'seer');
  },
  methods: {
    select(value) {
      this.$emit('update:modelValue', value);
      this.$emit('update-config', 'REQUEST_BACKEND', value);
    },
  },
};
</script>
