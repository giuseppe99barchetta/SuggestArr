<template>
  <span aria-hidden="true" class="grid shrink-0 place-items-center rounded-full border text-center" :class="[SIZES[size].box, unlocked ? 'border-brand-ink/40 bg-linear-to-br from-brand-soft to-panel text-brand-ink shadow-lg shadow-brand/20' : 'border-edge-strong bg-panel-2 text-ink-4']">
    <i v-if="content.icon" :class="[content.icon, SIZES[size].icon]"></i>
    <span v-else class="leading-none">
      <span class="block font-extrabold tracking-tight" :class="SIZES[size].text">{{ content.text }}</span>
      <span class="mt-0.5 block font-semibold uppercase tracking-wider opacity-80" :class="SIZES[size].unit">{{ content.unit }}</span>
    </span>
  </span>
</template>

<script>
import { badgeMedallion } from '@/utils/recapBadges.js';

const SIZES = {
  xs: { box: 'h-8 w-8', icon: 'text-xs', text: 'text-[10px]', unit: 'hidden' },
  sm: { box: 'h-11 w-11', icon: 'text-base', text: 'text-sm', unit: 'text-[7px]' },
  md: { box: 'h-16 w-16 border-2', icon: 'text-2xl', text: 'text-xl', unit: 'text-[8px]' },
  lg: { box: 'h-20 w-20 border-2', icon: 'text-3xl', text: 'text-2xl', unit: 'text-[9px]' },
};

export default {
  name: 'BadgeMedallion',
  props: { badge: { type: Object, required: true }, size: { type: String, default: 'md' } },
  data: () => ({ SIZES }),
  computed: {
    content() { return badgeMedallion(this.badge); },
    unlocked() { return this.badge.unlocked; },
  },
};
</script>
