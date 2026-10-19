<template>
  <div class="flex flex-col gap-3">
    <div role="radiogroup" aria-label="Run frequency" class="grid grid-cols-2 gap-2 sm:grid-cols-5">
      <button
        v-for="preset in presets"
        :key="preset.value"
        type="button"
        role="radio"
        :aria-checked="localValue.type === 'preset' && localValue.value === preset.value"
        :class="chipClass(localValue.type === 'preset' && localValue.value === preset.value)"
        @click="selectPreset(preset.value)"
      >
        <i aria-hidden="true" :class="preset.icon"></i>
        {{ preset.label }}
      </button>
      <button
        type="button"
        role="radio"
        :aria-checked="localValue.type === 'cron'"
        :class="chipClass(localValue.type === 'cron')"
        @click="setType('cron')"
      >
        <i aria-hidden="true" class="fas fa-code"></i>
        Custom
      </button>
    </div>

    <p v-if="localValue.type === 'preset'" class="m-0 text-xs text-ink-4">{{ presetDescription }}</p>

    <!-- Custom Cron Input -->
    <div v-else class="flex flex-col gap-2">
      <label class="ui-label" for="cronExpression">
        Cron expression
        <input
          id="cronExpression"
          v-model="localValue.value"
          type="text"
          placeholder="0 0 * * *"
          class="ui-input font-mono"
          @input="validateCron"
        />
      </label>
      <small v-if="cronError" class="text-xs text-bad">{{ cronError }}</small>
      <small v-else-if="cronPreview" class="flex items-center gap-1.5 text-xs text-notice">
        <i aria-hidden="true" class="fas fa-clock"></i>{{ cronPreview }}
      </small>
      <small v-else class="text-xs text-ink-4">Format: minute hour day month day_of_week</small>
      <div class="flex flex-wrap items-center gap-1.5">
        <span class="text-xs text-ink-4">Examples:</span>
        <button
          v-for="example in cronExamples"
          :key="example"
          type="button"
          class="cursor-pointer rounded-[8px] border border-edge bg-panel-2 px-2 py-1 font-mono text-xs text-ink-3 transition hover:border-ink-4 hover:text-ink"
          @click="setCronExample(example)"
        >
          {{ example }}
        </button>
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
          label: 'Every 12h',
          description: 'Runs at noon and midnight',
          icon: 'fas fa-sync'
        },
        {
          value: 'every_6h',
          label: 'Every 6h',
          description: 'Runs 4 times a day',
          icon: 'fas fa-bolt'
        }
      ],
      cronExamples: ['0 0 * * *', '0 */6 * * *', '30 2 * * 0', '0 0 1 * *']
    };
  },
  computed: {
    presetDescription() {
      return this.presets.find(p => p.value === this.localValue.value)?.description || '';
    },
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
      this.localValue.type = 'preset';
      this.localValue.value = value;
      this.cronError = null;
    },

    chipClass(active) {
      return [
        'flex cursor-pointer items-center justify-center gap-2 rounded-ctl border px-3 py-2 text-[13px] font-semibold transition-colors',
        active ? 'border-brand bg-brand-soft text-ink [&>i]:text-brand-ink' : 'border-edge-strong bg-panel-2 text-ink-2 hover:border-ink-4 hover:text-ink [&>i]:text-ink-4',
      ];
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
      if (!isValidField(parts[4], 0, 7)) {
        this.cronError = 'Invalid day of week field (0-7, Sunday is 0 or 7)';
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
