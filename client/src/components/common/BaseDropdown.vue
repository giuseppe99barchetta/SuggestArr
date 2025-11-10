<template>
  <div class="form-group">
    <label v-if="label" :for="id">
      {{ label }}
      <span v-if="required" class="required-indicator">*</span>
    </label>
    <div class="select-wrapper">
      <select
        :id="id"
        v-model="selectedValue"
        :class="['form-control', { 'disabled': disabled }]"
        :disabled="disabled"
        @change="handleChange"
      >
        <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
        <option
          v-for="option in options"
          :key="getOptionKey(option)"
          :value="getOptionValue(option)"
          :disabled="option.disabled"
        >
          {{ getOptionLabel(option) }}
        </option>
      </select>
      <div class="chevron-indicator">
        <i class="fas fa-chevron-down"></i>
      </div>
    </div>
    <small v-if="helpText" class="form-help">{{ helpText }}</small>
    <small v-if="error" class="form-error">{{ error }}</small>
  </div>
</template>

<script>
export default {
  name: 'BaseDropdown',
  props: {
    modelValue: {
      type: [String, Number, Boolean],
      default: ''
    },
    options: {
      type: Array,
      required: true,
      default: () => []
    },
    label: {
      type: String,
      default: ''
    },
    placeholder: {
      type: String,
      default: ''
    },
    helpText: {
      type: String,
      default: ''
    },
    error: {
      type: String,
      default: ''
    },
    required: {
      type: Boolean,
      default: false
    },
    disabled: {
      type: Boolean,
      default: false
    },
    id: {
      type: String,
      default: () => `dropdown-${Math.random().toString(36).substr(2, 9)}`
    },
    optionKey: {
      type: String,
      default: 'value'
    },
    optionLabel: {
      type: String,
      default: 'label'
    },
    optionValue: {
      type: String,
      default: 'value'
    }
  },
  emits: ['update:modelValue', 'change'],
  data() {
    return {
      selectedValue: this.modelValue
    };
  },
  watch: {
    modelValue: {
      immediate: true,
      handler(newValue) {
        this.selectedValue = newValue;
      }
    }
  },
  methods: {
    handleChange(event) {
      const newValue = event.target.value;
      this.selectedValue = newValue;
      this.$emit('update:modelValue', newValue);
      this.$emit('change', newValue);
    },
    getOptionKey(option) {
      if (typeof option === 'object' && option !== null) {
        return option[this.optionKey] || option[this.optionValue] || option[this.optionLabel];
      }
      return option;
    },
    getOptionLabel(option) {
      if (typeof option === 'object' && option !== null) {
        return option[this.optionLabel] || option[this.optionValue] || option[this.optionKey];
      }
      return option;
    },
    getOptionValue(option) {
      if (typeof option === 'object' && option !== null) {
        return option[this.optionValue] || option[this.optionKey] || option[this.optionLabel];
      }
      return option;
    }
  }
};
</script>

<style scoped>
.form-group {
  margin-bottom: 1.5rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  margin-top: 0.5rem;
  font-weight: 500;
  color: #e5e7eb;
}

.required-indicator {
  color: var(--color-danger);
  margin-left: 0.25rem;
}

.select-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.select-wrapper .form-control {
  width: 100%;
  padding: 0.75rem;
  padding-right: 2.5rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-primary);
  font-size: 1rem;
  transition: var(--transition-base);
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
}

.select-wrapper .form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  background: var(--color-bg-active);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.select-wrapper .form-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.select-wrapper .form-control.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chevron-indicator {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--color-text-muted);
  font-size: 0.75rem;
  transition: transform 0.2s ease;
}

.select-wrapper:focus-within .chevron-indicator {
  transform: translateY(-50%) rotate(180deg);
  color: var(--color-primary);
}

.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: var(--color-text-muted);
  line-height: 1.4;
}

.form-error {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: var(--color-danger);
  line-height: 1.4;
}

/* Responsive styles */
@media (max-width: 768px) {
  .form-group {
    margin-bottom: 1rem;
  }
}
</style>