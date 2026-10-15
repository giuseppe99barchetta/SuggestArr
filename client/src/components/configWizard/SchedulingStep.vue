<template>
  <div>
    <p class="mb-6 text-[0.9rem] leading-relaxed text-ink-4">
      Choose how often SuggestArr should run automatically. Each run it will scan your recently
      watched content, find similar titles via TMDB, and submit requests to Seer —
      so new content keeps appearing in your request queue without any manual effort.
    </p>

    <div class="mb-5 grid grid-cols-3 gap-3 min-[541px]:grid-cols-5">
      <button
        v-for="opt in scheduleOptions"
        :key="opt.value"
        type="button"
        class="relative flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border-[1.5px] px-2 pt-[1.1rem] pb-[0.9rem] text-center transition hover:-translate-y-0.5"
        :class="currentValue === opt.value ? 'border-brand bg-brand/12 text-ink shadow-[0_0_0_3px] shadow-brand/20' : 'border-white/10 bg-white/4 text-ink-3 hover:border-white/20 hover:bg-white/7'"
        @click="select(opt.value)"
      >
        <div v-if="opt.recommended" class="absolute -top-[9px] -right-[9px] whitespace-nowrap rounded-full bg-brand px-[7px] py-0.5 text-[0.6rem] font-bold uppercase tracking-wider text-white">Recommended</div>
        <i :class="[opt.icon, 'mb-0.5 text-[1.4rem]', { 'text-brand-ink': currentValue === opt.value }]"></i>
        <span class="text-[0.88rem] font-semibold">{{ opt.label }}</span>
        <span class="text-[0.71rem] leading-tight text-ink-4">{{ opt.description }}</span>
      </button>
    </div>

    <p class="m-0 flex items-center gap-1.5 text-[0.8rem] text-ink-4">
      <i class="fas fa-info-circle shrink-0 opacity-60"></i>
      You can change the schedule or add more jobs anytime from <strong>Settings → Jobs</strong>.
    </p>
  </div>
</template>

<script>
export default {
  name: 'SchedulingStep',
  props: {
    config: { type: Object, required: true },
  },
  emits: ['update-config'],
  data() {
    return {
      scheduleOptions: [
        { value: 'every_hour',  label: 'Every Hour',   description: 'Runs every hour',       icon: 'fas fa-bolt' },
        { value: 'every_6h',   label: 'Every 6h',     description: 'Runs 4× per day',        icon: 'fas fa-clock' },
        { value: 'every_12h',  label: 'Every 12h',    description: 'Runs twice a day',       icon: 'fas fa-sync' },
        { value: 'daily',      label: 'Daily',        description: 'Runs once at midnight',  icon: 'fas fa-calendar-day', recommended: true },
        { value: 'weekly',     label: 'Weekly',       description: 'Runs every Monday',      icon: 'fas fa-calendar-week' },
      ],
    };
  },
  computed: {
    currentValue() {
      return this.config.WIZARD_SCHEDULE || 'daily';
    },
  },
  methods: {
    select(value) {
      this.$emit('update-config', 'WIZARD_SCHEDULE', value);
    },
  },
  mounted() {
    if (!this.config.WIZARD_SCHEDULE) {
      this.$emit('update-config', 'WIZARD_SCHEDULE', 'daily');
    }
  },
};
</script>
