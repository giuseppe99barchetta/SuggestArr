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
  setup(props, { slots }) {
    const cardClasses = computed(() => [
      'card',
      `card--${props.variant}`,
      `card--${props.size}`,
      `card--padding-${props.padding}`,
      {
        'card--interactive': props.hoverable || props.variant === 'interactive'
      }
    ]);

    const hasHeaderContent = computed(() =>
      props.title ||
      props.description ||
      slots.header ||
      slots.headerIcon
    )
        
    const headerClasses = computed(() => [
      'card-header',
      {
        'card-header--empty': !hasHeaderContent.value
      }
    ])

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
/* These rules mirror the canonical .card* styles from primitives/card.css */

:deep(.base-card) {
  position: relative;
  background: var(--card-bg, var(--surface-elevated));
  border: 1px solid var(--card-border-color, var(--color-border-light));
  border-radius: var(--card-border-radius, var(--radius-lg));
  overflow: hidden;
  transition: var(--transition-base);
}

:deep(.base-card--default) {
  background: var(--card-bg, var(--surface-base));
  border: 1px solid var(--color-border-light);
  box-shadow: none;
}

:deep(.base-card--elevated) {
  background: var(--card-bg, var(--surface-elevated));
  border: none;
  box-shadow: var(--shadow-md);
}

:deep(.base-card--outline) {
  background: transparent;
  border: 2px solid var(--color-border-medium);
  box-shadow: none;
}

:deep(.base-card--ghost) {
  background: transparent;
  border: none;
  box-shadow: none;
}

:deep(.base-card--hoverable) {
  cursor: pointer;
}

:deep(.base-card--hoverable:hover) {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
  border-color: var(--color-border-medium);
}

:deep(.base-card-header) {
  padding: var(--card-header-padding, var(--spacing-lg));
  border-bottom: 1px solid var(--card-divider-color, var(--color-border-light));
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

:deep(.base-card-title) {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--card-title-color, var(--color-text-primary));
  flex: 1;
}

:deep(.base-card-body) {
  padding: var(--card-body-padding, var(--spacing-lg));
}

:deep(.base-card-footer) {
  padding: var(--card-footer-padding, var(--spacing-lg));
  border-top: 1px solid var(--card-divider-color, var(--color-border-light));
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}
</style>
