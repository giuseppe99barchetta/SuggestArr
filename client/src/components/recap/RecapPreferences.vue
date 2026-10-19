<template>
  <SectionCard icon="fas fa-heart" title="Support reminders" description="These preferences apply to your administrator account across browsers.">
    <form class="flex flex-col gap-3" @submit.prevent="save">
      <label for="recap-reminder-mode" class="ui-label">Reminders in Home</label>
      <select id="recap-reminder-mode" v-model="mode" class="ui-input" :disabled="loading || saving">
        <option value="enabled">Show occasional milestone and six-month reminders</option>
        <option value="supported">I already supported the project</option>
        <option value="disabled">Don't show support reminders</option>
      </select>
      <p class="m-0 text-xs text-ink-3">Your recap and badges are always available. Choosing “I already supported” needs no payment verification.</p>
      <p v-if="error" role="alert" class="ui-alert-bad">{{ error }}</p>
      <button type="submit" class="ui-btn self-start" :disabled="loading || saving">{{ saving ? 'Saving…' : 'Save preferences' }}</button>
    </form>
  </SectionCard>
</template>

<script>
import SectionCard from '@/components/ui/SectionCard.vue';
import { getRecap, saveRecapPreference } from '@/api/recapApi.js';

export default {
  name: 'RecapPreferences',
  components: { SectionCard },
  data: () => ({ mode: 'enabled', loading: true, saving: false, error: '' }),
  mounted() {
    this.load();
    window.addEventListener('suggestarr-recap-preferences', this.load);
  },
  beforeUnmount() { window.removeEventListener('suggestarr-recap-preferences', this.load); },
  methods: {
    async load() {
      this.loading = true;
      this.error = '';
      try { this.mode = (await getRecap()).preferences.reminder_mode; }
      catch { this.error = 'Unable to load support preferences.'; }
      finally { this.loading = false; }
    },
    async save() {
      this.saving = true;
      this.error = '';
      try {
        const action = { enabled: 'enable', supported: 'supported', disabled: 'disable' }[this.mode];
        await saveRecapPreference(action);
        window.dispatchEvent(new Event('suggestarr-recap-preferences'));
        this.$toast.success('Support reminder preferences saved.');
      } catch { this.error = 'Unable to save your preferences. Please try again.'; }
      finally { this.saving = false; }
    },
  },
};
</script>
