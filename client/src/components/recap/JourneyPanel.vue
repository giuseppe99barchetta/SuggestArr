<template>
  <section v-if="recap || error" aria-labelledby="journey-title" class="overflow-hidden rounded-card border border-edge bg-panel">
    <div class="flex flex-wrap items-center justify-between gap-5 p-5 sm:p-6">
      <div class="flex min-w-0 flex-1 items-center gap-4">
        <span aria-hidden="true" class="grid h-14 w-14 shrink-0 place-items-center rounded-card bg-brand-soft text-2xl text-brand-ink" :class="recap?.total >= 10 ? 'motion-safe:animate-pop' : ''"><i class="fas fa-award"></i></span>
        <div class="min-w-0 flex-1">
          <h2 id="journey-title" class="m-0 text-[17px] font-bold text-ink">Your SuggestArr journey</h2>
          <template v-if="recap">
            <p class="m-0 mt-1 text-sm text-ink-2"><strong>{{ recap.total.toLocaleString('en-US') }}</strong> titles requested <span class="text-ink-4">· {{ recap.scope === 'installation' ? 'This installation' : 'Your linked profiles' }}</span></p>
            <p v-if="!recap.has_linked_profiles" class="m-0 mt-2 text-sm text-ink-3"><router-link :to="{ name: 'DashboardTab', params: { tab: 'profile' } }">Link your media account</router-link> to start your personal recap.</p>
            <p v-else-if="!recap.total" class="m-0 mt-2 text-sm text-ink-3">Your journey starts with the first successful title request.</p>
            <template v-else>
              <p class="m-0 mt-1 text-xs text-brand-ink">{{ latestBadge?.label || 'Your first discoveries are on their way' }}</p>
              <div v-if="recap.next_badge" class="mt-2 max-w-md">
                <progress class="block h-1.5 w-full overflow-hidden rounded-full accent-brand" :value="recap.total" :max="recap.next_badge.threshold" :aria-label="`Progress toward ${recap.next_badge.label}`"></progress>
                <span class="mt-1 block text-[11px] text-ink-4">{{ recap.next_badge.threshold.toLocaleString('en-US') }} titles · {{ recap.next_badge.label }}</span>
              </div>
            </template>
          </template>
          <p v-if="error" role="alert" class="m-0 mt-2 text-sm text-bad">{{ error }} <button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-brand-ink underline" @click="load">Try again</button></p>
        </div>
      </div>
      <button v-if="recap" type="button" class="ui-btn shrink-0" @click="showRecap = true"><i aria-hidden="true" class="fas fa-image"></i>Create your recap</button>
    </div>
    <div v-if="prompt" class="relative border-t border-brand-soft bg-brand-soft/20 p-5 sm:p-6">
      <button type="button" class="absolute right-3 top-3 grid h-8 w-8 cursor-pointer place-items-center rounded-ctl border-0 bg-transparent text-ink-3 hover:bg-raised" aria-label="Dismiss support reminder" :disabled="saving" @click="act('dismiss')"><i aria-hidden="true" class="fas fa-times"></i></button>
      <h3 class="m-0 pr-7 text-base font-bold text-ink">{{ prompt.milestone.toLocaleString('en-US') }} titles requested with SuggestArr</h3>
      <p class="m-0 mt-2 max-w-2xl text-sm leading-relaxed text-ink-2">I build SuggestArr in my spare time. If it makes discovering your next watch easier, consider supporting its development or sharing your recap.</p>
      <div class="mt-4 flex flex-wrap gap-2">
        <button type="button" class="ui-btn-primary" @click="showSupport = true"><i aria-hidden="true" class="fas fa-heart"></i>Support SuggestArr</button>
        <button type="button" class="ui-btn" @click="showRecap = true">Create your recap</button>
      </div>
      <div class="mt-3 flex flex-wrap gap-x-4 gap-y-2">
        <button v-for="action in reminderActions" :key="action.id" type="button" class="cursor-pointer border-0 bg-transparent p-0 text-xs text-ink-3 hover:text-ink disabled:opacity-50" :disabled="saving" @click="act(action.id)">{{ action.label }}</button>
      </div>
      <p v-if="saveError" role="alert" class="ui-alert-bad mt-3">{{ saveError }}</p>
    </div>
    <AppDialog v-if="showRecap && recap && !recap.total" title="Your SuggestArr recap" icon="fas fa-award" @close="showRecap = false">
      <p class="m-0 text-sm text-ink-2">{{ recap.has_linked_profiles ? 'Your recap will be ready after your first successful title request.' : 'Link your Plex, Jellyfin or Emby account in My profile to build your personal recap.' }}</p>
    </AppDialog>
    <RecapDialog v-else-if="showRecap && recap" :recap="recap" @close="showRecap = false" />
    <SupportDialog v-if="showSupport" @close="showSupport = false" @preferences-changed="preferencesChanged" />
  </section>
</template>

<script>
import { getRecap, claimRecapPrompt, saveRecapPreference } from '@/api/recapApi.js';
import AppDialog from '@/components/ui/AppDialog.vue';
import RecapDialog from './RecapDialog.vue';
import SupportDialog from './SupportDialog.vue';

export default {
  name: 'JourneyPanel',
  components: { AppDialog, RecapDialog, SupportDialog },
  props: { currentUser: { type: Object, default: null } },
  data: () => ({
    recap: null, prompt: null, showRecap: false, showSupport: false,
    saving: false, error: '', saveError: '', active: true,
    reminderActions: [
      { id: 'remind_later', label: 'Remind me in 30 days' },
      { id: 'supported', label: 'I already supported' },
      { id: 'disable', label: "Don't show these reminders" },
    ],
  }),
  computed: {
    latestBadge() {
      const unlocked = this.recap?.badges.filter(badge => badge.unlocked) || [];
      return unlocked.filter(badge => badge.kind === 'titles').at(-1) || unlocked.at(-1);
    },
  },
  mounted() {
    this.load();
    window.addEventListener('suggestarr-recap-preferences', this.refreshPreferences);
  },
  beforeUnmount() {
    this.active = false;
    window.removeEventListener('suggestarr-recap-preferences', this.refreshPreferences);
  },
  methods: {
    async load() {
      this.error = '';
      try {
        const recap = await getRecap();
        if (!this.active) return;
        this.recap = recap;
        if (recap.can_support && recap.preferences.reminder_mode === 'enabled') {
          try { this.prompt = await claimRecapPrompt(); } catch { /* Retry on the next Home visit. */ }
        }
      } catch { this.error = 'Your journey could not be loaded.'; }
    },
    async act(action) {
      this.saving = true;
      this.saveError = '';
      try {
        const preferences = await saveRecapPreference(action);
        this.preferencesChanged(preferences);
      } catch { this.saveError = 'Unable to save your choice. Please try again.'; }
      finally { this.saving = false; }
    },
    preferencesChanged(preferences) {
      this.recap.preferences = preferences;
      this.prompt = null;
      window.dispatchEvent(new Event('suggestarr-recap-preferences'));
    },
    async refreshPreferences() {
      try {
        const recap = await getRecap();
        if (this.active && this.recap) {
          this.recap.preferences = recap.preferences;
          if (recap.preferences.reminder_mode !== 'enabled') this.prompt = null;
        }
      } catch { /* Existing recap remains usable. */ }
    },
  },
};
</script>
