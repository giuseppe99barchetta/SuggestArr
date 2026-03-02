<template>
  <div class="scheduling-step">
    <p class="step-intro">
      Choose how often SuggestArr should run automatically. Each run it will scan your recently
      watched content, find similar titles via TMDB, and submit requests to Overseerr / Jellyseerr —
      so new content keeps appearing in your request queue without any manual effort.
    </p>

    <div class="schedule-grid">
      <button
        v-for="opt in scheduleOptions"
        :key="opt.value"
        type="button"
        class="schedule-card"
        :class="{ 'is-selected': currentValue === opt.value }"
        @click="select(opt.value)"
      >
        <div v-if="opt.recommended" class="rec-badge">Recommended</div>
        <i :class="['schedule-icon', opt.icon]"></i>
        <span class="schedule-label">{{ opt.label }}</span>
        <span class="schedule-sub">{{ opt.description }}</span>
      </button>
    </div>

    <p class="schedule-note">
      <i class="fas fa-info-circle"></i>
      You can change the schedule or add more jobs anytime from <strong>Settings → Jobs</strong>.
    </p>
  </div>
</template>

<script>
export default {
  name: 'SchedulingStep',
  props: {
    config: { type: Object, required: true },
    wizardMode: { type: Boolean, default: false },
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

<style scoped>
.step-intro {
  color: var(--color-text-muted);
  font-size: 0.9rem;
  line-height: 1.6;
  margin-bottom: 1.5rem;
}

.schedule-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.schedule-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 1.1rem 0.5rem 0.9rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1.5px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  color: var(--color-text-secondary);
  text-align: center;
}

.schedule-card:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateY(-2px);
}

.schedule-card.is-selected {
  background: rgba(79, 70, 229, 0.12);
  border-color: var(--color-primary);
  color: var(--color-text-primary);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.2);
}

.schedule-icon {
  font-size: 1.4rem;
  margin-bottom: 0.15rem;
}

.schedule-card.is-selected .schedule-icon {
  color: var(--color-primary);
}

.schedule-label {
  font-size: 0.88rem;
  font-weight: 600;
}

.schedule-sub {
  font-size: 0.71rem;
  color: var(--color-text-muted);
  line-height: 1.3;
}

.rec-badge {
  position: absolute;
  top: -9px;
  right: -9px;
  background: var(--color-primary);
  color: white;
  font-size: 0.6rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 20px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

.schedule-note {
  color: var(--color-text-muted);
  font-size: 0.8rem;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.schedule-note i {
  flex-shrink: 0;
  opacity: 0.6;
}

@media (max-width: 540px) {
  .schedule-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
