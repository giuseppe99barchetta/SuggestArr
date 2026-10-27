<template>
  <div class="flex flex-col gap-5">
    <!-- AI Enhancement (shown when LLM is configured) -->
    <div v-if="llmConfigured" class="flex items-start gap-3 rounded-ctl border border-brand/50 bg-brand-soft/40 px-4 py-3">
      <BaseCheckbox v-model="localFilters.use_llm">
        <span class="flex items-center gap-2 font-semibold text-ink">
          <i aria-hidden="true" class="fas fa-robot w-4 text-brand-ink"></i>
          Use AI recommendations
        </span>
      </BaseCheckbox>
      <InfoTip class="mt-0.5" text="Your configured LLM reads the whole watch history and picks titles itself, instead of the standard TMDb “similar titles” search." />
    </div>

    <div class="grid gap-x-6 gap-y-1 sm:grid-cols-2">
      <div v-for="toggle in behaviorToggles" :key="toggle.key" class="flex items-center gap-1.5 py-1.5">
        <BaseCheckbox v-model="localFilters[toggle.key]" :disabled="toggle.tracker && !trackerUsable(toggle.tracker)">
          <span class="font-medium text-ink" :class="{ 'opacity-50': toggle.tracker && !trackerUsable(toggle.tracker) }">{{ toggle.label }}</span>
        </BaseCheckbox>
        <InfoTip :text="(toggle.tracker && trackerWarnings[toggle.tracker]) || toggle.help" />
      </div>
    </div>

    <div class="grid gap-x-6 gap-y-4 sm:grid-cols-2">
      <div v-for="slider in sliders" :key="slider.key" class="flex flex-col gap-1.5">
        <div class="flex items-center gap-1.5 text-[13px] font-semibold text-ink-2">
          <label :for="slider.key">{{ slider.label }}</label>
          <InfoTip :text="slider.help" />
          <span class="ml-auto font-mono text-ink">{{ localFilters[slider.key] || slider.fallback }}</span>
        </div>
        <input
          :id="slider.key"
          v-model.number="localFilters[slider.key]"
          type="range"
          :min="slider.min"
          :max="slider.max"
          :step="slider.step"
          class="w-full accent-brand"
        />
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import { waitForAuthReady } from '@/composables/useAuth';
import {
  listTraktMediaUsers, listSimklMediaUsers,
  getMyTraktStatus, getMySimklStatus,
} from '@/api/api';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import InfoTip from '@/components/ui/InfoTip.vue';
import { trackerState, trackerWarning, trackerUsers } from './trackerState.js';

const DEFAULTS = {
  use_llm: false,
  max_similar_movie: 5,
  max_similar_tv: 2,
  max_content: 10,
  search_size: 20,
  honor_seer_discovery: false,
  only_first_movie_in_collection: false,
  use_trakt_as_seed: true,
  use_trakt_as_exclusion: true,
  use_trakt_ratings: true,
  use_simkl_as_seed: true,
  use_simkl_as_exclusion: true
};

/**
 * Tuning for recommendation jobs: AI mode, behaviour switches and the similarity sliders.
 * Binds to the whole job form and only touches the keys above inside `filters`.
 */
export default {
  name: 'RecommendationFilters',
  components: { BaseCheckbox, InfoTip },
  props: {
    modelValue: {
      type: Object,
      default: () => ({})
    },
    llmConfigured: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:modelValue'],
  data() {
    return {
      localFilters: { ...DEFAULTS },
      isUpdatingFromParent: false,
      traktConfigured: false,
      traktMediaUsers: [],
      traktSelfConnected: false,
      simklConfigured: false,
      simklMediaUsers: [],
      simklSelfConnected: false,
      sliders: [
        { key: 'max_content', label: 'Watched items to analyse', fallback: 10, min: 5, max: 50, step: 5, help: 'How many recently watched titles per user are used as a starting point.' },
        { key: 'search_size', label: 'TMDb results per search', fallback: 20, min: 10, max: 50, step: 5, help: 'How many candidates are fetched from TMDb for each watched title before filtering.' },
        { key: 'max_similar_movie', label: 'Similar movies per title', fallback: 5, min: 1, max: 10, step: 1, help: 'How many similar movies are kept for each watched movie.' },
        { key: 'max_similar_tv', label: 'Similar shows per title', fallback: 2, min: 1, max: 10, step: 1, help: 'How many similar TV shows are kept for each watched show.' },
      ],
      behaviorToggles: [
        { key: 'honor_seer_discovery', label: 'Honor Seer discovery', help: "Respect Seer's own discovery settings when requesting." },
        { key: 'only_first_movie_in_collection', label: 'Only first movie in collections', help: 'Skip sequels, while still introducing new movie collections.' },
        { key: 'use_trakt_as_seed', label: 'Use Trakt history as seed', help: 'Also use linked Trakt watch history to find similar titles.', tracker: 'trakt' },
        { key: 'use_trakt_ratings', label: 'Use Trakt ratings', help: 'Also use titles rated on Trakt (including ratings synced from streaming services). Ratings set in SuggestArr win. Needs Trakt history as seed.', tracker: 'trakt' },
        { key: 'use_trakt_as_exclusion', label: 'Skip titles watched on Trakt', help: 'Never suggest something already watched on Trakt.', tracker: 'trakt' },
        { key: 'use_simkl_as_seed', label: 'Use Simkl history as seed', help: 'Also use linked Simkl watch history to find similar titles.', tracker: 'simkl' },
        { key: 'use_simkl_as_exclusion', label: 'Skip titles completed on Simkl', help: 'Never suggest something already completed on Simkl.', tracker: 'simkl' },
      ],
    };
  },
  computed: {
    trackerStates() {
      const selectedIds = this.modelValue.user_ids || [];
      // No selection means every user is monitored.
      const userMode = selectedIds.length ? 'selected' : 'all';
      return {
        trakt: trackerState({ configured: this.traktConfigured, users: this.traktMediaUsers, selfConnected: this.traktSelfConnected, key: 'trakt', userMode, selectedIds }),
        simkl: trackerState({ configured: this.simklConfigured, users: this.simklMediaUsers, selfConnected: this.simklSelfConnected, key: 'simkl', userMode, selectedIds }),
      };
    },
    trackerWarnings() {
      return {
        trakt: trackerWarning(this.trackerStates.trakt, 'Trakt', 'Client ID / Secret'),
        simkl: trackerWarning(this.trackerStates.simkl, 'Simkl', 'Client ID'),
      };
    },
  },
  watch: {
    modelValue: {
      handler(newVal) {
        if (!newVal.filters) return;
        this.isUpdatingFromParent = true;
        this.localFilters = Object.fromEntries(Object.entries(DEFAULTS).map(([key, value]) => [key, newVal.filters[key] ?? value]));
        this.$nextTick(() => {
          this.isUpdatingFromParent = false;
        });
      },
      deep: true,
      immediate: true
    },
    localFilters: {
      handler(newVal) {
        // Don't emit if the change came from the parent
        if (!this.isUpdatingFromParent) {
          this.$emit('update:modelValue', { ...this.modelValue, filters: { ...this.modelValue.filters, ...newVal } });
        }
      },
      deep: true
    }
  },
  methods: {
    trackerUsable(tracker) {
      return this.trackerStates[tracker] === 'usable';
    },
    /** Fetch linked accounts for one tracker; null when the list is unreadable (non-admin). */
    async loadTrackerUsers(configured, list) {
      if (!configured) return [];
      try {
        const res = await list();
        return res.data?.media_users || [];
      } catch {
        return null;
      }
    },
    /**
     * Whether the current user's own media profile has the tracker linked.
     *
     * The admin list only covers users chosen in Connections, so a link made
     * from Profile against a media account that was never selected is
     * invisible there. Reading it separately lets the warning say the account
     * is linked-but-unmonitored instead of claiming nothing is linked at all.
     * A caller with no media profile gets a 404, which is not an error here.
     */
    async loadSelfProfile(configured, fetchStatus) {
      if (!configured) return null;
      try {
        const res = await fetchStatus();
        return res.data?.media_user || null;
      } catch {
        return null;
      }
    },
  },
  async mounted() {
    try {
      await waitForAuthReady();
      const statusResponse = await axios.get('/api/config/status');
      this.traktConfigured = statusResponse.data?.trakt_app_configured === true;
      this.simklConfigured = statusResponse.data?.simkl_app_configured === true;
      const [traktUsers, simklUsers, traktSelf, simklSelf] = await Promise.all([
        this.loadTrackerUsers(this.traktConfigured, listTraktMediaUsers),
        this.loadTrackerUsers(this.simklConfigured, listSimklMediaUsers),
        this.loadSelfProfile(this.traktConfigured, getMyTraktStatus),
        this.loadSelfProfile(this.simklConfigured, getMySimklStatus),
      ]);
      this.traktMediaUsers = trackerUsers(traktUsers, traktSelf);
      this.simklMediaUsers = trackerUsers(simklUsers, simklSelf);
      this.traktSelfConnected = traktSelf?.trakt?.connected === true;
      this.simklSelfConnected = simklSelf?.simkl?.connected === true;
    } catch {
      this.traktMediaUsers = [];
      this.simklMediaUsers = [];
    }
  }
};
</script>
