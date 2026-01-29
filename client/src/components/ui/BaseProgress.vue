<template>
  <div class="base-progress-wrapper">
    <div v-if="showLabel" class="base-progress-label">
      <span>{{ label }}</span>
      <span v-if="showPercentage">{{ percentage }}%</span>
    </div>

    <div class="base-progress" :class="progressClasses">
      <div
        class="base-progress-bar"
        :style="{ width: `${percentage}%` }"
      >
        <span v-if="showText && !showLabel" class="base-progress-text">
          {{ percentage }}%
        </span>
      </div>
    </div>
  </div>
</template>

<script>
import { computed } from 'vue';

export default {
  name: 'BaseProgress',
  props: {
    percentage: {
      type: Number,
      required: true,
      validator: (value) => value >= 0 && value <= 100
    },
    label: {
      type: String,
      default: null
    },
    variant: {
      type: String,
      default: 'primary',
      validator: (value) => ['primary', 'success', 'warning', 'error', 'info'].includes(value)
    },
    size: {
      type: String,
      default: 'md',
      validator: (value) => ['sm', 'md', 'lg'].includes(value)
    },
    showPercentage: {
      type: Boolean,
      default: false
    },
    showText: {
      type: Boolean,
      default: false
    },
    animated: {
      type: Boolean,
      default: true
    }
  },
  setup(props) {
    const showLabel = computed(() => props.label || props.showPercentage);

    const progressClasses = computed(() => [
      `base-progress--${props.variant}`,
      `base-progress--${props.size}`,
      {
        'base-progress--animated': props.animated
      }
    ]);

    return {
      showLabel,
      progressClasses
    };
  }
};
</script>

<style scoped>
.base-progress-wrapper {
  width: 100%;
}

.base-progress-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xs);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.base-progress {
  width: 100%;
  background: var(--progress-bg);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.base-progress-bar {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.base-progress--animated .base-progress-bar {
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Sizes */
.base-progress--sm {
  height: 4px;
}

.base-progress--md {
  height: 8px;
}

.base-progress--lg {
  height: 12px;
}

/* Variants */
.base-progress--primary .base-progress-bar {
  background: var(--color-primary);
}

.base-progress--success .base-progress-bar {
  background: var(--color-success);
}

.base-progress--warning .base-progress-bar {
  background: var(--color-warning);
}

.base-progress--error .base-progress-bar {
  background: var(--color-error);
}

.base-progress--info .base-progress-bar {
  background: var(--color-info);
}

.base-progress-text {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: white;
  padding: 0 var(--spacing-xs);
}
</style>
