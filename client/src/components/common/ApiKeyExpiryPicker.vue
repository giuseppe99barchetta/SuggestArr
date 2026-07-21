<template>
  <div class="expiry-picker">
    <button type="button" class="expiry-picker__trigger" :disabled="disabled" @click="open = !open">
      <i class="fas fa-calendar-alt"></i><span>{{ displayValue }}</span><i class="fas fa-chevron-down"></i>
    </button>
    <div v-if="open" class="expiry-picker__panel">
      <div class="expiry-picker__header">
        <button type="button" aria-label="Previous month" @click="shiftMonth(-1)"><i class="fas fa-chevron-left"></i></button>
        <strong>{{ monthLabel }}</strong>
        <button type="button" aria-label="Next month" @click="shiftMonth(1)"><i class="fas fa-chevron-right"></i></button>
      </div>
      <div class="expiry-picker__weekdays"><span v-for="day in weekdays" :key="day">{{ day }}</span></div>
      <div class="expiry-picker__days">
        <button v-for="day in days" :key="day.key" type="button" :class="{ 'expiry-picker__day--selected': day.value === modelValue, 'expiry-picker__day--past': day.past, 'expiry-picker__day--outside': !day.currentMonth }" :disabled="!day.currentMonth || day.past" @click="select(day.value)">{{ day.day }}</button>
      </div>
      <button v-if="modelValue" type="button" class="expiry-picker__clear" @click="select('')">No expiry</button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ApiKeyExpiryPicker',
  props: { modelValue: { type: String, default: '' }, disabled: Boolean },
  emits: ['update:modelValue'],
  data() { const now = new Date(); return { open: false, year: now.getFullYear(), month: now.getMonth(), weekdays: ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'] }; },
  computed: {
    monthLabel() { return new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' }).format(new Date(this.year, this.month)); },
    days() {
      const first = new Date(this.year, this.month, 1); const offset = (first.getDay() + 6) % 7;
      const start = new Date(this.year, this.month, 1 - offset); const today = new Date(); today.setHours(0, 0, 0, 0);
      return Array.from({ length: 42 }, (_, index) => { const date = new Date(start); date.setDate(start.getDate() + index); return { key: date.toISOString(), day: date.getDate(), currentMonth: date.getMonth() === this.month, past: date < today, value: this.toValue(date) }; });
    },
    displayValue() { return this.modelValue ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(`${this.modelValue}T12:00:00`)) : 'No expiry'; },
  },
  methods: {
    shiftMonth(amount) { const date = new Date(this.year, this.month + amount); this.year = date.getFullYear(); this.month = date.getMonth(); },
    select(value) { this.$emit('update:modelValue', value); this.open = false; },
    toValue(date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`; },
  },
};
</script>

<style scoped>
.expiry-picker { position: relative; }
.expiry-picker__trigger { width: 100%; min-height: var(--input-height-md); display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-sm) var(--spacing-md); color: var(--color-text-primary); background: var(--color-bg-interactive); border: 1px solid var(--color-border-light); border-radius: var(--input-border-radius); font-size: var(--font-size-base); text-align: left; }
.expiry-picker__trigger:focus-visible, .expiry-picker__trigger:hover { border-color: var(--color-primary); background: var(--color-bg-active); }
.expiry-picker__trigger:disabled { opacity: var(--alpha-50); cursor: not-allowed; }
.expiry-picker__panel { position: absolute; z-index: var(--z-dropdown, 1000); width: 100%; margin-top: var(--spacing-xs); padding: var(--spacing-md); background: var(--surface-elevated-solid); border: 1px solid var(--color-border-light); border-radius: var(--radius-md); box-shadow: var(--dropdown-shadow); }
.expiry-picker__header { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: var(--spacing-sm); margin-bottom: var(--spacing-md); color: var(--color-text-primary); text-align: center; }
.expiry-picker__header button, .expiry-picker__day, .expiry-picker__clear { color: var(--color-text-secondary); background: transparent; border: 0; border-radius: var(--radius-sm); font-size: var(--font-size-sm); }
.expiry-picker__header button, .expiry-picker__day { min-height: var(--spacing-xl); }
.expiry-picker__header button:hover, .expiry-picker__day:hover:not(:disabled) { background: var(--surface-hover); color: var(--color-text-primary); }
.expiry-picker__weekdays, .expiry-picker__days { display: grid; grid-template-columns: repeat(7, 1fr); gap: var(--spacing-2xs); text-align: center; }
.expiry-picker__weekdays { margin-bottom: var(--spacing-xs); color: var(--color-text-muted); font-size: var(--font-size-xs); }
.expiry-picker__day:disabled { cursor: not-allowed; }
.expiry-picker__day--past { color: var(--color-text-muted); background: var(--surface-glass-subtle); opacity: var(--alpha-60); text-decoration: line-through; }
.expiry-picker__day--outside { color: var(--color-text-muted); opacity: var(--alpha-30); }
.expiry-picker__day--selected { color: var(--color-text-primary); background: var(--color-primary); }
.expiry-picker__clear { display: block; width: 100%; margin-top: var(--spacing-md); padding: var(--spacing-sm); color: var(--color-text-muted); text-align: center; }
.expiry-picker__clear:hover { color: var(--color-text-primary); background: var(--surface-hover); }
</style>
