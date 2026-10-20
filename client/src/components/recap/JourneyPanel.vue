<template>
  <div v-if="recap || error" class="flex flex-col gap-3">
    <section aria-labelledby="journey-title" class="overflow-hidden rounded-card border border-edge bg-panel">
      <div class="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-4 gap-y-5 bg-linear-to-r from-brand-soft/25 via-panel to-panel p-5 sm:gap-x-6 sm:p-6 lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:gap-x-8">
        <button v-if="recap" type="button" aria-label="Open your badges" class="relative grid h-16 w-16 cursor-pointer place-items-center rounded-full border border-brand-ink/25 bg-linear-to-br from-brand-soft to-panel p-0 shadow-sm ring-4 ring-brand-soft/20 transition-shadow hover:ring-brand-soft/50 sm:row-span-2 sm:h-20 sm:w-20" @click="showBadges = true">
          <div aria-hidden="true" class="text-center">
            <i v-if="medallion?.icon" :class="medallion.icon" class="text-2xl text-brand-ink"></i>
            <template v-else-if="medallion">
              <span class="block text-2xl font-extrabold leading-none tracking-tight text-brand-ink sm:text-[28px]">{{ medallion.text }}</span>
              <span class="mt-1 block text-[9px] font-semibold uppercase tracking-widest text-brand-ink/80">{{ medallion.unit }}</span>
            </template>
            <span v-else class="text-sm font-bold text-brand-ink">Start</span>
          </div>
          <span v-if="latestBadge" class="absolute -bottom-1 -right-1 grid h-6 w-6 place-items-center rounded-full border border-brand-ink/25 bg-brand-soft text-[11px] text-brand-ink"><i aria-hidden="true" class="fas fa-award"></i></span>
        </button>
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
          <p v-if="recap.total && (hitRate || recap.streak?.current)" class="m-0 mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-3">
            <span v-if="hitRate"><i aria-hidden="true" class="fas fa-play-circle mr-1 text-brand-ink"></i>{{ recap.hit_rate }}% of picks watched</span>
            <span v-if="recap.streak?.current"><i aria-hidden="true" class="fas fa-fire mr-1 text-caution"></i>{{ recap.streak.current }}-month watch streak</span>
          </p>
        </div>
        <div class="col-span-2 flex min-w-0 flex-col gap-1.5 sm:col-span-1 sm:col-start-2 lg:col-start-3 lg:row-span-2 lg:row-start-1 lg:min-w-48">
          <button v-if="recap" type="button" class="ui-btn w-full border-brand-ink/25 bg-brand-soft/40 text-brand-ink hover:border-brand-ink/60 hover:bg-brand-soft/60" @click="showRecap = true">Create your recap<i aria-hidden="true" class="fas fa-arrow-right ml-1 text-xs"></i></button>
          <button v-if="yearSeason.available" type="button" class="inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-ctl border-0 bg-transparent px-3 text-xs font-medium text-ink-3 hover:bg-raised hover:text-brand-ink" @click="showYearRecap = true"><i aria-hidden="true" class="fas fa-film"></i>Year recap</button>
        </div>
      </div>
      <div v-if="announceYear" class="relative flex items-start gap-3 border-t border-edge bg-linear-to-br from-caution/10 to-panel p-5 sm:gap-4 sm:px-6">
        <span aria-hidden="true" class="grid h-10 w-10 shrink-0 place-items-center rounded-ctl border border-caution/30 bg-caution/10 text-caution"><i class="fas fa-film"></i></span>
        <div class="min-w-0 flex-1 pr-8">
          <p class="m-0 mb-1 text-[11px] font-semibold uppercase tracking-widest text-caution">{{ yearSeason.year }} in stories</p>
          <h3 class="m-0 text-base font-bold leading-snug text-ink">Your year on screen is ready</h3>
          <p class="m-0 mt-1 text-sm text-ink-3">Discoveries, the picks you watched and the milestones you unlocked, ready to share.</p>
          <button type="button" class="ui-btn mt-3" @click="openAnnouncedYear"><i aria-hidden="true" class="fas fa-play"></i>Play your {{ yearSeason.year }} stories</button>
        </div>
        <button type="button" class="absolute right-3 top-3 grid h-10 w-10 cursor-pointer place-items-center rounded-ctl border-0 bg-transparent text-ink-4 transition-colors hover:bg-raised hover:text-ink" :aria-label="`Dismiss ${yearSeason.year} recap announcement`" @click="dismissYearAnnouncement"><i aria-hidden="true" class="fas fa-times"></i></button>
      </div>
      <AppDialog v-if="showRecap && recap && !recap.total" title="Your SuggestArr recap" icon="fas fa-award" @close="showRecap = false">
        <p class="m-0 text-sm text-ink-2">{{ recap.has_linked_profiles ? 'Your recap will be ready after your first successful title request.' : 'Link your Plex, Jellyfin or Emby account in My profile to build your personal recap.' }}</p>
      </AppDialog>
      <RecapDialog v-else-if="showRecap && recap" :recap="recap" @close="showRecap = false" @show-badges="showBadges = true" />
      <BadgesDialog v-if="showBadges && recap" :recap="recap" @close="showBadges = false" @support="showSupport = true" />
      <SupportDialog v-if="showSupport" :can-manage-reminders="Boolean(recap?.can_support)" @close="showSupport = false" @preferences-changed="preferencesChanged" />
      <BadgeUnlockedDialog v-if="celebration.length && !showRecap && !showBadges && !showSupport && !showYearRecap" :badges="celebration" @close="dismissCelebration" @support="openFromCelebration('showSupport')" @show-badges="openFromCelebration('showBadges')" />
      <YearRecapStories v-if="showYearRecap && yearSeason.available" :is-admin="currentUser?.role === 'admin'" :initial-year="yearSeason.year" @close="showYearRecap = false" />
    </section>
    <!-- No overflow-hidden here: it would clip the reminder options menu. -->
    <aside v-if="prompt" aria-labelledby="support-prompt-title" class="rounded-card border border-brand-ink/25 bg-linear-to-br from-brand-soft/35 via-panel to-panel p-5 sm:p-6">
      <div class="flex items-start gap-4">
        <span aria-hidden="true" class="hidden h-11 w-11 shrink-0 place-items-center rounded-full bg-brand-soft/60 text-brand-ink ring-4 ring-brand-soft/20 sm:grid"><i class="fas fa-heart"></i></span>
        <div class="min-w-0 flex-1">
          <p class="m-0 text-[11px] font-semibold uppercase tracking-widest text-brand-ink">{{ prompt.milestone.toLocaleString('en-US') }} titles requested</p>
          <h3 id="support-prompt-title" class="m-0 mt-1 text-base font-bold leading-snug text-ink">Enjoying the discoveries?</h3>
          <p class="m-0 mt-1 max-w-xl text-sm leading-relaxed text-ink-3">A little support helps me keep building SuggestArr in my spare time.</p>
          <div class="mt-4 flex flex-wrap items-center gap-2">
            <button type="button" class="ui-btn-primary" @click="showSupport = true"><i aria-hidden="true" class="fas fa-heart"></i>Support SuggestArr</button>
            <button type="button" class="ui-btn border-transparent bg-transparent text-ink-3 hover:border-transparent hover:bg-raised hover:text-ink" :disabled="saving" @click="act('dismiss')">Not now</button>
            <ActionMenu class="ml-auto" label="Reminder options" :items="reminderMenu" />
          </div>
          <p v-if="saveError" role="alert" class="ui-alert-bad mt-3">{{ saveError }}</p>
        </div>
      </div>
    </aside>
  </div>
</template>

<script>
import { getRecap, claimRecapPrompt, saveRecapPreference, syncWatchActivity } from '@/api/recapApi.js';
import { badgeMedallion, latestBadge, markBadgesSeen, newlyUnlocked, showHitRate } from '@/utils/recapBadges.js';
import BadgeUnlockedDialog from './BadgeUnlockedDialog.vue';
import BadgesDialog from './BadgesDialog.vue';
import ActionMenu from '@/components/ui/ActionMenu.vue';
import AppDialog from '@/components/ui/AppDialog.vue';
import RecapDialog from './RecapDialog.vue';
import SupportDialog from './SupportDialog.vue';
import YearRecapStories from './YearRecapStories.vue';
import { yearRecapSeason } from '@/utils/yearRecapSeason.js';

const announcementKey = year => `suggestarr-year-recap-announced:${year}`;
const readFlag = key => { try { return window.localStorage.getItem(key) === '1'; } catch { return false; } };
const writeFlag = key => { try { window.localStorage.setItem(key, '1'); } catch { /* Dismissal lasts this visit. */ } };

export default {
  name: 'JourneyPanel',
  components: { ActionMenu, AppDialog, BadgeUnlockedDialog, BadgesDialog, RecapDialog, SupportDialog, YearRecapStories },
  props: { currentUser: { type: Object, default: null } },
  data: () => ({
    recap: null, prompt: null, showRecap: false, showBadges: false, showSupport: false, showYearRecap: false,
    saving: false, error: '', saveError: '', active: true,
    yearSeason: yearRecapSeason(), seasonTimer: null, celebration: [], announcementDismissed: false,
  }),
  computed: {
    latestBadge() { return latestBadge(this.recap?.badges); },
    medallion() { return this.latestBadge ? badgeMedallion(this.latestBadge) : null; },
    hitRate() { return showHitRate(this.recap); },
    reminderMenu() {
      return [
        { label: 'Remind me in 30 days', icon: 'far fa-clock', onSelect: () => this.act('remind_later') },
        { label: 'I already supported', icon: 'fas fa-check', onSelect: () => this.act('supported') },
        { label: "Don't show these reminders", icon: 'far fa-bell-slash', onSelect: () => this.act('disable') },
      ];
    },
    /** Dev-only preview of the badge celebration or support reminder: `?demo=badge` or `?demo=support`. */
    demo() { return import.meta.env.DEV ? this.$route?.query.demo : null; },
    announceYear() {
      return Boolean(this.yearSeason.available && this.recap?.total && !this.announcementDismissed
        && !readFlag(announcementKey(this.yearSeason.year)));
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
        this.showRecapData(recap);
        if (this.demo === 'support') this.prompt = { milestone: 100 };
        else if (recap.can_support && recap.preferences.reminder_mode === 'enabled') {
          try { this.prompt = await claimRecapPrompt(); } catch { /* Retry on the next Home visit. */ }
        }
        if (recap.watch_tracking) this.syncWatched();
      } catch { this.error = 'Your journey could not be loaded.'; }
    },
    showRecapData(recap) {
      this.recap = recap;
      this.celebration = this.demo === 'badge' && recap.badges.length
        ? [{ ...recap.badges[0], unlocked: true, unlocked_at: new Date().toISOString() }]
        : newlyUnlocked(recap, this.currentUser?.id);
    },
    /** Picks watched since the last scan can unlock badges; refresh quietly when they do. */
    async syncWatched() {
      try {
        const result = await syncWatchActivity();
        if (!this.active || !result?.matched) return;
        const recap = await getRecap();
        if (this.active) this.showRecapData(recap);
      } catch { /* The recap stays usable without watch data. */ }
    },
    dismissCelebration() {
      if (this.recap) markBadgesSeen(this.recap, this.currentUser?.id);
      this.celebration = [];
    },
    /** Continue from the celebration to support or the badge gallery; the badges count as seen. */
    openFromCelebration(dialog) {
      this.dismissCelebration();
      this[dialog] = true;
    },
    dismissYearAnnouncement() {
      writeFlag(announcementKey(this.yearSeason.year));
      this.announcementDismissed = true;
    },
    openAnnouncedYear() {
      this.dismissYearAnnouncement();
      this.showYearRecap = true;
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
