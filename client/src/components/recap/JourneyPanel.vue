<template>
  <section v-if="recap || error" aria-labelledby="journey-title" class="overflow-hidden rounded-card border border-edge bg-panel">
    <div class="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-4 gap-y-5 bg-linear-to-r from-brand-soft/25 via-panel to-panel p-5 sm:gap-x-6 sm:p-6 lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:gap-x-8">
      <div v-if="recap" aria-hidden="true" class="relative grid h-16 w-16 place-items-center rounded-full border border-brand-ink/25 bg-linear-to-br from-brand-soft to-panel shadow-sm ring-4 ring-brand-soft/20 sm:row-span-2 sm:h-20 sm:w-20">
        <div class="text-center">
          <template v-if="latestBadge?.kind === 'titles'">
            <span class="block text-2xl font-extrabold leading-none tracking-tight text-brand-ink sm:text-[28px]">{{ latestBadge.threshold.toLocaleString('en-US', { notation: 'compact', maximumFractionDigits: 0 }) }}</span>
            <span class="mt-1 block text-[9px] font-semibold uppercase tracking-widest text-brand-ink/80">titles</span>
          </template>
          <span v-else class="text-sm font-bold text-brand-ink">{{ latestBadge ? '1 year' : 'Start' }}</span>
        </div>
        <span v-if="latestBadge" class="absolute -bottom-1 -right-1 grid h-6 w-6 place-items-center rounded-full border border-brand-ink/25 bg-brand-soft text-[11px] text-brand-ink"><i class="fas fa-award"></i></span>
      </div>
      <div class="min-w-0" :class="!recap ? 'col-span-2' : ''">
        <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
          <h2 id="journey-title" class="m-0 text-xs font-medium text-ink-3">Your SuggestArr journey</h2>
          <span v-if="recap" class="order-3 basis-full text-[11px] text-ink-4 sm:order-none sm:basis-auto"><span class="mr-2 hidden text-edge-strong sm:inline" aria-hidden="true">/</span>{{ recap.scope === 'installation' ? 'This installation' : 'Your linked profiles' }}</span>
          <p v-if="recap" class="order-2 m-0 basis-full text-lg font-bold leading-snug tracking-tight text-ink sm:order-3 sm:text-xl">{{ latestBadge?.label || 'Discover your next milestone' }}</p>
        </div>
        <p v-if="error" role="alert" class="m-0 mt-2 text-sm text-bad">{{ error }} <button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-brand-ink underline" @click="load">Try again</button></p>
      </div>
      <div v-if="recap" class="col-span-2 min-w-0 sm:col-span-1 sm:col-start-2 lg:row-start-2 lg:-mt-2">
        <p v-if="!recap.has_linked_profiles" class="m-0 text-sm leading-relaxed text-ink-3"><router-link :to="{ name: 'DashboardTab', params: { tab: 'profile' } }">Link your media account</router-link> to start your personal recap.</p>
        <p v-else-if="!recap.total" class="m-0 text-sm leading-relaxed text-ink-3">Your journey starts with the first successful title request.</p>
        <template v-else-if="recap.next_badge">
          <progress class="block h-1.5 w-full max-w-xl appearance-none overflow-hidden rounded-full border-0 bg-raised [&::-webkit-progress-bar]:rounded-full [&::-webkit-progress-bar]:bg-raised [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:bg-brand [&::-moz-progress-bar]:rounded-full [&::-moz-progress-bar]:bg-brand" :value="recap.total" :max="recap.next_badge.threshold" :aria-label="`Progress toward ${recap.next_badge.label}`"></progress>
          <div class="mt-2 flex max-w-xl flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-[11px]">
            <span class="text-ink-3">{{ Math.max(0, recap.next_badge.threshold - recap.total).toLocaleString('en-US') }} more titles to unlock</span>
            <span class="text-ink-4">Next: {{ recap.next_badge.label }}</span>
          </div>
        </template>
        <p v-else class="m-0 text-xs text-ink-3">Every title milestone unlocked.</p>
      </div>
      <div class="col-span-2 flex min-w-0 flex-col gap-1.5 sm:col-span-1 sm:col-start-2 lg:col-start-3 lg:row-span-2 lg:row-start-1 lg:min-w-48">
        <button v-if="recap" type="button" class="ui-btn w-full border-brand-ink/25 bg-brand-soft/40 text-brand-ink hover:border-brand-ink/60 hover:bg-brand-soft/60" @click="showRecap = true">Create your recap<i aria-hidden="true" class="fas fa-arrow-right ml-1 text-xs"></i></button>
        <button v-if="yearSeason.available" type="button" class="inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-ctl border-0 bg-transparent px-3 text-xs font-medium text-ink-3 hover:bg-raised hover:text-brand-ink" @click="showYearRecap = true"><i aria-hidden="true" class="fas fa-film"></i>Year recap</button>
      </div>
    </div>
    <div v-if="prompt" class="relative border-t border-edge bg-linear-to-br from-brand-soft/25 to-panel p-5 sm:px-6">
      <button type="button" class="absolute right-3 top-3 grid h-10 w-10 cursor-pointer place-items-center rounded-ctl border-0 bg-transparent text-ink-4 transition-colors hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-50" aria-label="Dismiss support reminder" :disabled="saving" @click="act('dismiss')"><i aria-hidden="true" class="fas fa-times"></i></button>
      <div class="flex items-start gap-3 sm:gap-4">
        <span aria-hidden="true" class="mt-0.5 hidden h-10 w-10 shrink-0 place-items-center rounded-ctl border border-brand-ink/15 bg-brand-soft/40 text-brand-ink sm:grid"><i class="far fa-heart"></i></span>
        <div class="min-w-0 flex-1">
          <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center lg:gap-8">
            <div class="pr-8 lg:pr-0">
              <p class="m-0 mb-1.5 text-[11px] font-semibold uppercase tracking-widest text-brand-ink">A milestone worth celebrating</p>
              <h3 class="m-0 text-base font-bold leading-snug text-ink">{{ prompt.milestone.toLocaleString('en-US') }} titles requested with SuggestArr</h3>
              <p class="m-0 mt-2 max-w-xl text-sm leading-relaxed text-ink-3">Enjoying the discoveries? A little support helps me keep building SuggestArr in my spare time.</p>
            </div>
            <button type="button" class="ui-btn w-full border-brand-ink/25 bg-brand-soft/40 text-brand-ink hover:border-brand-ink/60 hover:bg-brand-soft/60 lg:mr-9 lg:w-auto" @click="showSupport = true"><i aria-hidden="true" class="fas fa-heart"></i>Support SuggestArr<i aria-hidden="true" class="fas fa-arrow-right ml-1 text-xs"></i></button>
          </div>
          <SupportReminderOptions class="mt-2 max-w-sm" :saving="saving" allow-snooze @select="act" />
        </div>
      </div>
      <p v-if="saveError" role="alert" class="ui-alert-bad mt-3">{{ saveError }}</p>
    </div>
    <AppDialog v-if="showRecap && recap && !recap.total" title="Your SuggestArr recap" icon="fas fa-award" @close="showRecap = false">
      <p class="m-0 text-sm text-ink-2">{{ recap.has_linked_profiles ? 'Your recap will be ready after your first successful title request.' : 'Link your Plex, Jellyfin or Emby account in My profile to build your personal recap.' }}</p>
    </AppDialog>
    <RecapDialog v-else-if="showRecap && recap" :recap="recap" @close="showRecap = false" />
    <SupportDialog v-if="showSupport" @close="showSupport = false" @preferences-changed="preferencesChanged" />
    <YearRecapStories v-if="showYearRecap && yearSeason.available" :is-admin="currentUser?.role === 'admin'" :initial-year="yearSeason.year" @close="showYearRecap = false" />
  </section>
</template>

<script>
import { getRecap, claimRecapPrompt, saveRecapPreference } from '@/api/recapApi.js';
import AppDialog from '@/components/ui/AppDialog.vue';
import RecapDialog from './RecapDialog.vue';
import SupportDialog from './SupportDialog.vue';
import YearRecapStories from './YearRecapStories.vue';
import SupportReminderOptions from './SupportReminderOptions.vue';
import { yearRecapSeason } from '@/utils/yearRecapSeason.js';

export default {
  name: 'JourneyPanel',
  components: { AppDialog, RecapDialog, SupportDialog, SupportReminderOptions, YearRecapStories },
  props: { currentUser: { type: Object, default: null } },
  data: () => ({
    recap: null, prompt: null, showRecap: false, showSupport: false, showYearRecap: false,
    saving: false, error: '', saveError: '', active: true,
    yearSeason: yearRecapSeason(), seasonTimer: null,
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
    window.addEventListener('focus', this.refreshYearSeason);
    this.seasonTimer = setInterval(this.refreshYearSeason, 60000);
  },
  beforeUnmount() {
    this.active = false;
    window.removeEventListener('suggestarr-recap-preferences', this.refreshPreferences);
    window.removeEventListener('focus', this.refreshYearSeason);
    clearInterval(this.seasonTimer);
  },
  methods: {
    refreshYearSeason() {
      this.yearSeason = yearRecapSeason();
      if (!this.yearSeason.available) this.showYearRecap = false;
    },
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
