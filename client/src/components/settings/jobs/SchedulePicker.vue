<template>
  <div class="schedule-picker">
    <!-- Schedule Type Toggle -->
    <div class="toggle-container">
      <button
        type="button"
        class="toggle-btn"
        :class="{ active: localValue.type === 'preset' }"
        @click="setType('preset')"
      >
        <i class="fas fa-clock"></i>
        Preset
      </button>
      <button
        type="button"
        class="toggle-btn"
        :class="{ active: localValue.type === 'cron' }"
        @click="setType('cron')"
      >
        <i class="fas fa-code"></i>
        Custom Cron
      </button>
    </div>

    <!-- Preset Options -->
    <div v-if="localValue.type === 'preset'" class="preset-list">
      <div
        v-for="preset in presets"
        :key="preset.value"
        class="preset-item"
        :class="{ active: localValue.value === preset.value }"
        @click="selectPreset(preset.value)"
      >
        <div class="preset-icon">
          <i :class="preset.icon"></i>
        </div>
        <div class="preset-info">
          <span class="preset-name">{{ preset.label }}</span>
          <span class="preset-desc">{{ preset.description }}</span>
        </div>
        <i v-if="localValue.value === preset.value" class="fas fa-check check-icon"></i>
      </div>
    </div>

    <!-- Custom Cron Input -->
    <div v-else class="cron-section">
      <div class="form-group">
        <label for="cronExpression">Cron Expression</label>
        <input
          id="cronExpression"
          v-model="localValue.value"
          type="text"
          placeholder="0 0 * * *"
          class="form-control mono"
          @input="validateCron"
        />
        <small v-if="cronError" class="form-error">{{ cronError }}</small>
        <small v-else class="form-help">Format: minute hour day month day_of_week</small>
      </div>

      <!-- Cron Examples -->
      <div class="cron-examples">
        <span class="examples-label">Examples:</span>
        <div class="example-btns">
          <button
            v-for="example in cronExamples"
            :key="example.value"
            type="button"
            class="example-btn"
            @click="setCronExample(example.value)"
          >
            {{ example.label }}
          </button>
        </div>
      </div>

      <!-- Cron Preview -->
      <div v-if="cronPreview && !cronError" class="cron-preview">
        <i class="fas fa-info-circle"></i>
        {{ cronPreview }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'SchedulePicker',
  props: {
    modelValue: {
      type: Object,
      default: () => ({ type: 'preset', value: 'daily' })
    }
  },
  emits: ['update:modelValue'],
  data() {
    return {
      localValue: { ...this.modelValue },
      cronError: null,
      isUpdating: false,
      presets: [
        {
          value: 'daily',
          label: 'Daily',
          description: 'Runs every day at midnight',
          icon: 'fas fa-calendar-day'
        },
        {
          value: 'weekly',
          label: 'Weekly',
          description: 'Runs every Monday at midnight',
          icon: 'fas fa-calendar-week'
        },
        {
          value: 'every_12h',
          label: 'Every 12 Hours',
          description: 'Runs at noon and midnight',
          icon: 'fas fa-sync'
        },
        {
          value: 'every_6h',
          label: 'Every 6 Hours',
          description: 'Runs 4 times a day',
          icon: 'fas fa-bolt'
        }
      ],
      cronExamples: [
        { label: '0 0 * * *', value: '0 0 * * *' },
        { label: '0 */6 * * *', value: '0 */6 * * *' },
        { label: '30 2 * * 0', value: '30 2 * * 0' },
        { label: '0 0 1 * *', value: '0 0 1 * *' }
      ]
    };
  },
  computed: {
    cronPreview() {
      if (this.localValue.type !== 'cron' || !this.localValue.value) return null;
      return this.describeCron(this.localValue.value);
    }
  },
  watch: {
    modelValue: {
      handler(newVal) {
        if (this.isUpdating) return;
        const newStr = JSON.stringify(newVal);
        const localStr = JSON.stringify(this.localValue);
        if (newStr !== localStr) {
          this.localValue = JSON.parse(newStr);
        }
      },
      deep: true
    },
    localValue: {
      handler(newVal) {
        if (this.isUpdating) return;
        this.isUpdating = true;
        this.$emit('update:modelValue', JSON.parse(JSON.stringify(newVal)));
        this.$nextTick(() => {
          this.isUpdating = false;
        });
      },
      deep: true
    }
  },
  methods: {
    setType(type) {
      this.localValue.type = type;
      if (type === 'preset' && !this.presets.some(p => p.value === this.localValue.value)) {
        this.localValue.value = 'daily';
      } else if (type === 'cron' && this.presets.some(p => p.value === this.localValue.value)) {
        this.localValue.value = '0 0 * * *';
      }
    },

    selectPreset(value) {
      this.localValue.value = value;
    },

    setCronExample(value) {
      this.localValue.value = value;
      this.validateCron();
    },

    validateCron() {
      const expr = this.localValue.value;
      if (!expr) {
        this.cronError = null;
        return;
      }

      const parts = expr.trim().split(/\s+/);
      if (parts.length !== 5) {
        this.cronError = 'Cron expression must have 5 fields';
        return;
      }

      const isValidField = (field, min, max) => {
        if (field === '*') return true;
        if (field.includes('/')) {
          const [base, step] = field.split('/');
          if (base !== '*' && (isNaN(base) || base < min || base > max)) return false;
          if (isNaN(step) || step < 1) return false;
          return true;
        }
        if (field.includes('-')) {
          const [start, end] = field.split('-');
          return !isNaN(start) && !isNaN(end) && start >= min && end <= max;
        }
        if (field.includes(',')) {
          return field.split(',').every(v => !isNaN(v) && v >= min && v <= max);
        }
        return !isNaN(field) && field >= min && field <= max;
      };

      if (!isValidField(parts[0], 0, 59)) {
        this.cronError = 'Invalid minute field (0-59)';
        return;
      }
      if (!isValidField(parts[1], 0, 23)) {
        this.cronError = 'Invalid hour field (0-23)';
        return;
      }
      if (!isValidField(parts[2], 1, 31)) {
        this.cronError = 'Invalid day field (1-31)';
        return;
      }
      if (!isValidField(parts[3], 1, 12)) {
        this.cronError = 'Invalid month field (1-12)';
        return;
      }
      if (!isValidField(parts[4], 0, 6)) {
        this.cronError = 'Invalid day of week field (0-6)';
        return;
      }

      this.cronError = null;
    },

    describeCron(expr) {
      const parts = expr.trim().split(/\s+/);
      if (parts.length !== 5) return '';

      const [minute, hour, day, month, dow] = parts;

      if (minute === '0' && hour === '0' && day === '*' && month === '*' && dow === '*') {
        return 'Runs every day at midnight';
      }
      if (minute === '0' && hour === '0' && day === '*' && month === '*' && dow === '0') {
        return 'Runs every Sunday at midnight';
      }
      if (minute === '0' && hour === '0' && day === '*' && month === '*' && dow === '1') {
        return 'Runs every Monday at midnight';
      }
      if (minute === '0' && hour.startsWith('*/')) {
        const interval = hour.split('/')[1];
        return `Runs every ${interval} hours`;
      }
      if (minute === '0' && hour === '0' && day === '1' && month === '*' && dow === '*') {
        return 'Runs on the 1st of every month';
      }

      const timeStr = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
      return `Runs at ${timeStr}`;
    }
  }
};
</script>

<style scoped>
.schedule-picker {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.toggle-container {
  display: flex;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  padding: 0.25rem;
}

.toggle-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: var(--transition-base);
  font-weight: var(--font-weight-medium);
}

.toggle-btn:hover {
  color: var(--color-text-primary);
}

.toggle-btn.active {
  background: var(--color-primary);
  color: white;
}

.preset-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.preset-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-base);
}

.preset-item:hover {
  border-color: var(--color-border-heavy);
}

.preset-item.active {
  border-color: var(--color-primary);
  background: var(--color-primary-alpha-10);
}

.preset-icon {
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-overlay-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
}

.preset-item.active .preset-icon {
  background: var(--color-primary);
  color: white;
}

.preset-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.preset-name {
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.preset-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.check-icon {
  color: var(--color-primary);
}

.cron-section .form-group {
  margin-bottom: 0.75rem;
}

.cron-section .form-group label {
  display: block;
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: 0.5rem;
}

.form-control {
  width: 100%;
  padding: 0.75rem 1rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-primary);
  font-size: 1rem;
  transition: var(--transition-base);
}

.form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--shadow-glow);
}

.form-control.mono {
  font-family: var(--font-family-mono);
}

.form-error {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--color-error);
  margin-top: 0.35rem;
}

.form-help {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  margin-top: 0.35rem;
}

.cron-examples {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.examples-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.example-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.example-btn {
  padding: 0.35rem 0.5rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: var(--transition-base);
}

.example-btn:hover {
  border-color: var(--color-border-heavy);
  color: var(--color-text-primary);
}

.cron-preview {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: var(--color-info-alpha-10);
  border-left: 3px solid var(--color-info);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  color: var(--color-info);
}
</style>
