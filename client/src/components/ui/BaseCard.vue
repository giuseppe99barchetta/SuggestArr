<template>
  <div :class="cardClasses">
    <div v-if="$slots.header || title" class="base-card-header">
      <slot name="header">
        <h3 v-if="title" class="base-card-title">{{ title }}</h3>
      </slot>
    </div>

    <div class="base-card-body">
      <slot></slot>
    </div>

    <div v-if="$slots.footer" class="base-card-footer">
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
    variant: {
      type: String,
      default: 'default',
      validator: (value) => ['default', 'elevated', 'outline', 'ghost'].includes(value)
    },
    padding: {
      type: String,
      default: 'md',
      validator: (value) => ['none', 'sm', 'md', 'lg'].includes(value)
    },
    hoverable: {
      type: Boolean,
      default: false
    }
  },
  setup(props) {
    const cardClasses = computed(() => [
      'base-card',
      `base-card--${props.variant}`,
      `base-card--padding-${props.padding}`,
      {
        'base-card--hoverable': props.hoverable
      }
    ]);

    return {
      cardClasses
    };
  }
};
</script>

<style scoped>
.base-card {
  background: var(--card-bg);
  border-radius: var(--card-border-radius);
  transition: var(--transition-all);
}

/* Variants */
.base-card--default {
  border: 1px solid var(--color-border-light);
}

.base-card--elevated {
  box-shadow: var(--shadow-lg);
}

.base-card--outline {
  border: 2px solid var(--color-border-medium);
}

.base-card--ghost {
  background: transparent;
}

/* Padding */
.base-card--padding-none .base-card-body {
  padding: 0;
}

.base-card--padding-sm .base-card-body {
  padding: var(--spacing-sm);
}

.base-card--padding-md .base-card-body {
  padding: var(--spacing-lg);
}

.base-card--padding-lg .base-card-body {
  padding: var(--spacing-xl);
}

/* Hoverable */
.base-card--hoverable {
  cursor: pointer;
}

.base-card--hoverable:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-xl);
  border-color: var(--color-border-medium);
}

/* Header */
.base-card-header {
  padding: var(--spacing-lg);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--color-border-light);
}

.base-card-title {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

/* Body */
.base-card-body {
  /* Padding set by padding variants */
}

/* Footer */
.base-card-footer {
  padding: var(--spacing-lg);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-border-light);
}
</style>
