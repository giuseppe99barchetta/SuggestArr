<template>
  <div :class="cardClasses">
    <!-- Header Section -->
    <div v-if="$slots.header || title || $slots.headerIcon" :class="headerClasses">
      <slot name="headerIcon"></slot>
      <div style="flex: 1">
        <h3 v-if="title" class="card-title">{{ title }}</h3>
        <p v-if="description" class="card-description">{{ description }}</p>
      </div>
      <slot name="header"></slot>
    </div>

    <!-- Body Section -->
    <div class="card-body" :class="bodyClasses">
      <slot></slot>
    </div>

    <!-- Footer Section -->
    <div v-if="$slots.footer" class="card-footer">
      <slot name="footer"></slot>
    </div>
  </div>
</template>

<script>
import { computed } from 'vue';

export default {
  name: 'BaseCard',
  props: {
    title: {
      type: String,
      default: null
    },
    description: {
      type: String,
      default: null
    },
    variant: {
      type: String,
      default: 'default',
      validator: (value) => ['default', 'elevated', 'outline', 'ghost', 'interactive'].includes(value)
    },
    padding: {
      type: String,
      default: 'lg',
      validator: (value) => ['none', 'sm', 'md', 'lg', 'xl'].includes(value)
    },
    size: {
      type: String,
      default: 'standard',
      validator: (value) => ['compact', 'standard', 'large'].includes(value)
    },
    hoverable: {
      type: Boolean,
      default: false
    }
  },
  setup(props) {
    const cardClasses = computed(() => [
      'card',
      `card--${props.variant}`,
      `card--${props.size}`,
      `card--padding-${props.padding}`,
      {
        'card--interactive': props.hoverable || props.variant === 'interactive'
      }
    ]);

    const headerClasses = computed(() => [
      'card-header',
      {
        'card-header--empty': !props.title && !props.$slots.header
      }
    ]);

    const bodyClasses = computed(() => {
      const map = {
        'none': 'card-body--no-padding',
        'sm': 'card-body--compact',
        'md': '',
        'lg': '',
        'xl': 'card-body--spacious'
      };
      return map[props.padding] || '';
    });

    return {
      cardClasses,
      headerClasses,
      bodyClasses
    };
  }
};
</script>

<style scoped>
/* Alias base-card classes for backward compatibility */
:deep(.base-card) { @apply card; }
:deep(.base-card--default) { @apply card--default; }
:deep(.base-card--elevated) { @apply card--elevated; }
:deep(.base-card--outline) { @apply card--outline; }
:deep(.base-card--ghost) { @apply card--ghost; }
:deep(.base-card--hoverable) { @apply card--interactive; }
:deep(.base-card-header) { @apply card-header; }
:deep(.base-card-title) { @apply card-title; }
:deep(.base-card-body) { @apply card-body; }
:deep(.base-card-footer) { @apply card-footer; }
</style>
