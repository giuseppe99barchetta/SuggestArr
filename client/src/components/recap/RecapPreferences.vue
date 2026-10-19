<template>
  <SectionCard icon="fas fa-heart" title="Support reminders" description="These preferences apply to your administrator account across browsers.">
    <div class="mb-5 flex flex-col gap-3 rounded-card border border-brand-ink/20 bg-linear-to-br from-brand-soft/30 to-panel p-4 sm:flex-row sm:items-center sm:gap-5">
      <p class="m-0 flex-1 text-sm leading-relaxed text-ink-2">SuggestArr is built in my spare time, one feature at a time. If it has helped you find something great to watch, a coffee is the nicest way to say thanks, and it keeps new ideas coming.</p>
      <button type="button" class="ui-btn shrink-0 justify-center border-brand-ink/25 bg-brand-soft/40 text-brand-ink hover:border-brand-ink/60 hover:bg-brand-soft/60" @click="showSupport = true"><i aria-hidden="true" class="fas fa-mug-hot"></i>Buy me a coffee</button>
    </div>
    <fieldset class="m-0 flex min-w-0 flex-col gap-2 border-0 p-0" :disabled="loading || saving">
      <legend class="ui-label mb-2 p-0">Reminders in Home</legend>
      <label
        v-for="option in options"
        :key="option.value"
        class="flex cursor-pointer items-start gap-3 rounded-ctl border p-3.5 transition-colors has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand"
        :class="mode === option.value ? 'border-brand-ink/50 bg-brand-soft/30' : 'border-edge bg-panel-2 hover:border-edge-strong hover:bg-raised'"
      >
        <input type="radio" name="recap-reminder-mode" class="sr-only" :value="option.value" :checked="mode === option.value" @change="choose(option.value)" />
        <span aria-hidden="true" class="mt-0.5 grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full border-2 transition-colors" :class="mode === option.value ? 'border-brand-ink' : 'border-ink-4'">
          <span class="h-2 w-2 rounded-full bg-brand-ink transition-transform motion-reduce:transition-none" :class="mode === option.value ? 'scale-100' : 'scale-0'"></span>
        </span>
        <span class="min-w-0 flex-1">
          <span class="block text-sm font-semibold text-ink">{{ option.label }}</span>
          <span class="mt-0.5 block text-xs leading-relaxed text-ink-3">{{ option.caption }}</span>
        </span>
        <i v-if="saving && pending === option.value" aria-hidden="true" class="fas fa-spinner fa-spin mt-0.5 text-ink-3"></i>
      </label>
    </fieldset>
    <p class="m-0 mt-3 text-xs leading-relaxed text-ink-4">Your recap and badges are always available. Choosing “I already supported” needs no payment verification.</p>
    <p v-if="error" role="alert" class="ui-alert-bad mt-3">{{ error }}</p>
    <SupportDialog v-if="showSupport" :can-manage-reminders="false" @close="showSupport = false" />
  </SectionCard>
</template>

<script>
import SectionCard from '@/components/ui/SectionCard.vue';
import SupportDialog from './SupportDialog.vue';
import { getRecap, saveRecapPreference } from '@/api/recapApi.js';

export default {
  name: 'RecapPreferences',
  components: { SectionCard, SupportDialog },
  data: () => ({
    mode: 'enabled', pending: '', loading: true, saving: false, error: '', showSupport: false,
    options: [
      { value: 'enabled', label: 'Show occasional reminders', caption: 'A friendly note at milestones and every six months.' },
      { value: 'supported', label: 'I already supported the project', caption: 'Thank you! No reminders will be shown.' },
      { value: 'disabled', label: "Don't show support reminders", caption: 'Keep Home free of any support prompts.' },
    ],
  }),
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
    /** Saves right away; a failed save reverts the selection so the UI never lies about the stored state. */
    async choose(value) {
      const previous = this.mode;
      this.mode = value;
      this.pending = value;
      this.saving = true;
      this.error = '';
      try {
        const action = { enabled: 'enable', supported: 'supported', disabled: 'disable' }[value];
        await saveRecapPreference(action);
        window.dispatchEvent(new Event('suggestarr-recap-preferences'));
        this.$toast.success('Support reminder preferences saved.');
      } catch {
        this.mode = previous;
        this.error = 'Unable to save your preferences. Please try again.';
      } finally { this.saving = false; }
    },
  },
};
</script>
