<template>
  <div class="base-input-wrapper" :class="wrapperClasses">
    <label v-if="label" :for="inputId" class="base-input-label">
      {{ label }}
      <span v-if="required" class="text-error">*</span>
    </label>

    <div class="base-input-container">
      <i v-if="icon" :class="`fas fa-${icon} base-input-icon base-input-icon--left`"></i>

      <input
        :id="inputId"
        ref="inputRef"
        v-bind="$attrs"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :class="inputClasses"
        @input="handleInput"
        @focus="handleFocus"
        @blur="handleBlur"
      />

      <i v-if="clearable && modelValue"
         class="fas fa-times base-input-icon base-input-icon--right base-input-clear"
         @click="handleClear"></i>
    </div>

    <p v-if="error" class="base-input-error">
      <i class="fas fa-exclamation-circle"></i>
      {{ error }}
    </p>

    <p v-else-if="hint" class="base-input-hint">
      {{ hint }}
    </p>
  </div>
</template>

<script>
import { ref, computed } from 'vue';

let inputIdCounter = 0;

export default {
  name: 'BaseInput',
  inheritAttrs: false,
  props: {
    modelValue: {
      type: [String, Number],
      default: ''
    },
    type: {
      type: String,
      default: 'text'
    },
    label: {
      type: String,
      default: null
    },
    placeholder: {
      type: String,
      default: ''
    },
    error: {
      type: String,
      default: null
    },
    hint: {
      type: String,
      default: null
    },
    icon: {
      type: String,
      default: null
    },
    disabled: {
      type: Boolean,
      default: false
    },
    readonly: {
      type: Boolean,
      default: false
    },
    required: {
      type: Boolean,
      default: false
    },
    clearable: {
      type: Boolean,
      default: false
    },
    size: {
      type: String,
      default: 'md',
      validator: (value) => ['sm', 'md', 'lg'].includes(value)
    }
  },
  emits: ['update:modelValue', 'focus', 'blur', 'clear'],
  setup(props, { emit }) {
    const inputRef = ref(null);
    const isFocused = ref(false);
    const inputId = `base-input-${inputIdCounter++}`;

    const wrapperClasses = computed(() => ({
      'base-input-wrapper--disabled': props.disabled,
      'base-input-wrapper--error': props.error,
      'base-input-wrapper--focused': isFocused.value
    }));

    const inputClasses = computed(() => [
      'base-input',
      `base-input--${props.size}`,
      {
        'base-input--with-icon-left': props.icon,
        'base-input--with-icon-right': props.clearable && props.modelValue
      }
    ]);

    const handleInput = (event) => {
      emit('update:modelValue', event.target.value);
    };

    const handleFocus = (event) => {
      isFocused.value = true;
      emit('focus', event);
    };

    const handleBlur = (event) => {
      isFocused.value = false;
      emit('blur', event);
    };

    const handleClear = () => {
      emit('update:modelValue', '');
      emit('clear');
      inputRef.value?.focus();
    };

    return {
      inputRef,
      inputId,
      wrapperClasses,
      inputClasses,
      handleInput,
      handleFocus,
      handleBlur,
      handleClear
    };
  }
};
</script>

<style scoped>
.base-input-wrapper {
  width: 100%;
}

.base-input-label {
  display: block;
  margin-bottom: var(--spacing-xs);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
}

.base-input-container {
  position: relative;
  width: 100%;
}

.base-input {
  width: 100%;
  font-family: var(--font-family-base);
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  transition: var(--transition-all);
}

.base-input:hover:not(:disabled) {
  border-color: var(--color-border-medium);
}

.base-input:focus {
  outline: none;
  border-color: var(--color-border-focus);
  box-shadow: 0 0 0 3px var(--color-primary-alpha-10);
}

.base-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.base-input::placeholder {
  color: var(--color-text-muted);
}

/* Sizes */
.base-input--sm {
  height: var(--input-height-sm);
  padding: 0 var(--input-padding-x);
  font-size: var(--font-size-sm);
}

.base-input--md {
  height: var(--input-height-md);
  padding: 0 var(--input-padding-x);
}

.base-input--lg {
  height: var(--input-height-lg);
  padding: 0 var(--input-padding-x);
  font-size: var(--font-size-lg);
}

/* With Icons */
.base-input--with-icon-left {
  padding-left: 40px;
}

.base-input--with-icon-right {
  padding-right: 40px;
}

.base-input-icon {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-muted);
  pointer-events: none;
}

.base-input-icon--left {
  left: 12px;
}

.base-input-icon--right {
  right: 12px;
}

.base-input-clear {
  pointer-events: auto;
  cursor: pointer;
  transition: var(--transition-fast);
}

.base-input-clear:hover {
  color: var(--color-text-primary);
}

/* Error State */
.base-input-wrapper--error .base-input {
  border-color: var(--color-error);
}

.base-input-wrapper--error .base-input:focus {
  box-shadow: 0 0 0 3px var(--color-error-alpha-10);
}

.base-input-error {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  margin-top: var(--spacing-xs);
  font-size: var(--font-size-sm);
  color: var(--color-error);
}

.base-input-hint {
  margin-top: var(--spacing-xs);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}
</style>
