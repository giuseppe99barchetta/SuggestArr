<template>
  <button
    :class="buttonClasses"
    :disabled="disabled || loading"
    :type="type"
    @click="handleClick"
  >
    <i v-if="loading" class="fas fa-spinner fa-spin"></i>
    <i v-else-if="icon && iconPosition === 'left'" :class="`fas fa-${icon}`"></i>
    <slot></slot>
    <i v-if="icon && iconPosition === 'right'" :class="`fas fa-${icon}`"></i>
  </button>
</template>

<script>
import { computed } from 'vue';

export default {
  name: 'BaseButton',
  props: {
    variant: {
      type: String,
      default: 'primary',
      validator: (value) => ['primary', 'secondary', 'success', 'danger', 'warning', 'ghost', 'outline'].includes(value)
    },
    size: {
      type: String,
      default: 'md',
      validator: (value) => ['sm', 'md', 'lg'].includes(value)
    },
    disabled: {
      type: Boolean,
      default: false
    },
    loading: {
      type: Boolean,
      default: false
    },
    icon: {
      type: String,
      default: null
    },
    iconPosition: {
      type: String,
      default: 'left',
      validator: (value) => ['left', 'right'].includes(value)
    },
    type: {
      type: String,
      default: 'button',
      validator: (value) => ['button', 'submit', 'reset'].includes(value)
    },
    fullWidth: {
      type: Boolean,
      default: false
    }
  },
  emits: ['click'],
  setup(props, { emit }) {
    const buttonClasses = computed(() => [
      'base-button',
      `base-button--${props.variant}`,
      `base-button--${props.size}`,
      {
        'base-button--disabled': props.disabled,
        'base-button--loading': props.loading,
        'base-button--full-width': props.fullWidth
      }
    ]);

    const handleClick = (event) => {
      if (!props.disabled && !props.loading) {
        emit('click', event);
      }
    };

    return {
      buttonClasses,
      handleClick
    };
  }
};
</script>

<style scoped>
.base-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  font-family: var(--font-family-base);
  font-weight: var(--font-weight-semibold);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: var(--transition-all);
  white-space: nowrap;
  user-select: none;
}

.base-button:active:not(.base-button--disabled) {
  transform: translateY(1px);
}

/* Sizes */
.base-button--sm {
  height: var(--btn-height-sm);
  padding: 0 var(--btn-padding-x-sm);
  font-size: var(--font-size-sm);
}

.base-button--md {
  height: var(--btn-height-md);
  padding: 0 var(--btn-padding-x-md);
  font-size: var(--font-size-base);
}

.base-button--lg {
  height: var(--btn-height-lg);
  padding: 0 var(--btn-padding-x-lg);
  font-size: var(--font-size-lg);
}

/* Variants */
.base-button--primary {
  background: var(--color-primary);
  color: white;
}

.base-button--primary:hover:not(.base-button--disabled) {
  background: var(--color-primary-hover);
  box-shadow: var(--shadow-glow);
}

.base-button--secondary {
  background: var(--color-bg-tertiary);
  color: var(--color-text-primary);
}

.base-button--secondary:hover:not(.base-button--disabled) {
  background: var(--color-bg-hover);
}

.base-button--success {
  background: var(--color-success);
  color: white;
}

.base-button--success:hover:not(.base-button--disabled) {
  background: var(--color-success-hover);
  box-shadow: var(--shadow-success);
}

.base-button--danger {
  background: var(--color-error);
  color: white;
}

.base-button--danger:hover:not(.base-button--disabled) {
  background: var(--color-error-hover);
}

.base-button--warning {
  background: var(--color-warning);
  color: white;
}

.base-button--warning:hover:not(.base-button--disabled) {
  background: var(--color-warning-hover);
}

.base-button--ghost {
  background: transparent;
  color: var(--color-text-primary);
}

.base-button--ghost:hover:not(.base-button--disabled) {
  background: var(--color-bg-interactive);
}

.base-button--outline {
  background: transparent;
  color: var(--color-primary);
  border: 1px solid var(--color-primary);
}

.base-button--outline:hover:not(.base-button--disabled) {
  background: var(--color-primary-alpha-10);
}

/* States */
.base-button--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.base-button--loading {
  cursor: wait;
}

.base-button--full-width {
  width: 100%;
}

/* Icons */
.base-button i {
  font-size: 1em;
}

.base-button .fa-spinner {
  animation: spin 1s linear infinite;
}
</style>
