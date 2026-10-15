<template>
  <div class="flex flex-col gap-6">
    <PageHeader title="AI Search" subtitle="Describe what you feel like watching. The AI finds matching titles, personalised to your viewing history." />

    <div v-if="!llmAvailable" role="alert" class="flex flex-wrap items-center gap-3 rounded-card border border-caution/40 bg-caution/10 px-4 py-3.5">
      <i aria-hidden="true" class="fas fa-exclamation-triangle text-caution"></i>
      <p class="m-0 flex-[1_1_280px] text-sm text-ink-2"><strong class="text-ink">No AI provider configured.</strong> Add one in the AI provider settings to use AI Search.</p>
      <router-link :to="{ name: 'DashboardTab', params: { tab: 'ai_provider' } }" class="inline-flex h-9 items-center rounded-[8px] bg-caution px-3.5 text-[13px] font-bold text-[#1a1405] no-underline hover:text-[#1a1405]">Set up AI provider</router-link>
    </div>

    <form class="flex flex-col gap-4 rounded-card border border-edge bg-panel p-4 sm:p-5" :class="{ 'opacity-60': !llmAvailable }" @submit.prevent="runSearch">
      <label class="flex flex-col gap-1.5">
        <span class="sr-only">What do you want to watch?</span>
        <textarea
          v-model="query"
          :disabled="!llmAvailable || isSearching"
          rows="3"
          placeholder="A psychological thriller from the 90s with a twist ending… or feel-good anime about friendship"
          class="w-full resize-y rounded-ctl border border-edge-strong bg-canvas px-4 py-3 text-[15px] leading-relaxed text-ink outline-none placeholder:text-ink-4 focus:border-brand-ink disabled:cursor-not-allowed"
          @keydown.enter.exact.prevent="runSearch"
        ></textarea>
        <span class="self-end text-xs text-ink-4">Enter to search · Shift + Enter for a new line</span>
      </label>

      <div class="flex flex-wrap items-center justify-between gap-3">
        <div role="radiogroup" aria-label="Media type" class="flex rounded-ctl border border-edge-strong bg-canvas p-1">
          <button
            v-for="option in mediaTypeOptions"
            :key="option.value"
            type="button"
            role="radio"
            :aria-checked="mediaType === option.value ? 'true' : 'false'"
            :disabled="isSearching"
            class="inline-flex h-9 cursor-pointer items-center gap-2 rounded-[8px] border-0 px-3.5 text-[13px] font-semibold"
            :class="mediaType === option.value ? 'bg-raised text-white' : 'bg-transparent text-ink-3 hover:text-ink'"
            @click="mediaType = option.value"
          >
            <i aria-hidden="true" :class="option.icon"></i>{{ option.label }}
          </button>
        </div>
        <button type="submit" class="inline-flex h-[42px] cursor-pointer items-center gap-2 rounded-ctl border-0 bg-brand px-5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50" :disabled="!llmAvailable || isSearching || !query.trim()">
          <i aria-hidden="true" :class="isSearching ? 'fas fa-spinner fa-spin' : 'fas fa-magic'"></i>{{ isSearching ? 'Searching…' : 'Search' }}
        </button>
      </div>

      <details class="group border-t border-edge pt-3">
        <summary class="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-ink-3 hover:text-ink">
          <i aria-hidden="true" class="fas fa-chevron-right text-xs transition-transform group-open:rotate-90"></i>Search options
        </summary>
        <div class="mt-3 grid gap-2 sm:grid-cols-2">
          <button
            v-for="toggle in toggles"
            :key="toggle.key"
            type="button"
            role="switch"
            :aria-checked="$data[toggle.key] ? 'true' : 'false'"
            class="flex cursor-pointer items-center gap-3 rounded-ctl border border-edge bg-panel-2 p-3 text-left hover:border-edge-strong"
            @click="toggleOption(toggle.key)"
          >
            <span class="flex min-w-0 flex-1 flex-col gap-0.5">
              <span class="text-sm font-semibold text-ink">{{ toggle.title }}</span>
              <span class="text-xs leading-snug text-ink-4">{{ toggle.hint }}</span>
            </span>
            <span class="relative inline-block h-[22px] w-10 shrink-0 rounded-full transition-colors" :class="$data[toggle.key] ? 'bg-brand' : 'bg-edge-strong'"><span class="absolute top-[3px] h-4 w-4 rounded-full bg-white transition-all" :class="$data[toggle.key] ? 'left-[21px]' : 'left-[3px]'"></span></span>
          </button>
          <label class="flex items-center gap-3 rounded-ctl border border-edge bg-panel-2 p-3">
            <span class="flex min-w-0 flex-1 flex-col gap-0.5">
              <span class="text-sm font-semibold text-ink">Max results</span>
              <span class="text-xs leading-snug text-ink-4">Between 4 and 24</span>
            </span>
            <input v-model.number="maxResults" type="number" min="4" max="24" step="4" :disabled="isSearching" class="h-9 w-20 rounded-[8px] border border-edge-strong bg-canvas px-2.5 text-sm text-ink" />
          </label>
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-3">
          <button type="button" class="inline-flex h-9 cursor-pointer items-center gap-2 rounded-[8px] border border-edge-strong bg-transparent px-3 text-[13px] font-semibold text-ink-2 hover:text-bad disabled:opacity-50" :disabled="isResettingSeen" @click="resetSeen">
            <i aria-hidden="true" :class="isResettingSeen ? 'fas fa-spinner fa-spin' : 'fas fa-trash-alt'"></i>{{ isResettingSeen ? 'Clearing…' : 'Clear recommendation history' }}
          </button>
          <span class="text-xs text-ink-4">Lets titles from earlier AI searches show up again.</span>
        </div>
      </details>
    </form>

    <div v-if="recentSearches.length > 0" class="flex flex-wrap items-center gap-2">
      <span class="text-xs font-semibold uppercase tracking-wider text-ink-4">Recent</span>
      <button
        v-for="(search, i) in recentSearches"
        :key="i"
        type="button"
        class="h-8 max-w-[280px] cursor-pointer truncate rounded-full border border-edge-strong bg-panel px-3 text-[13px] text-ink-2 hover:border-brand-ink hover:text-ink disabled:opacity-50"
        :disabled="isSearching"
        :title="search"
        @click="rerunSearch(search)"
      >{{ search }}</button>
      <button type="button" class="h-8 cursor-pointer rounded-full border-0 bg-transparent px-2 text-[13px] text-ink-4 hover:text-ink" @click="clearHistory">Clear</button>
    </div>

    <div v-if="queryInterpretation && hasInterpretation" class="flex flex-wrap items-center gap-2 text-[13px]">
      <span class="font-semibold text-ink-3"><i aria-hidden="true" class="fas fa-brain mr-1.5 text-brand-ink"></i>Understood as</span>
      <span v-if="interpGenres" class="rounded-full bg-raised px-3 py-1 text-ink-2">{{ interpGenres }}</span>
      <span v-if="interpYears" class="rounded-full bg-raised px-3 py-1 text-ink-2">{{ interpYears }}</span>
      <span v-if="interpLang" class="rounded-full bg-raised px-3 py-1 text-ink-2">{{ interpLang.toUpperCase() }}</span>
      <span v-if="interpMinRating" class="rounded-full bg-raised px-3 py-1 text-ink-2"><i aria-hidden="true" class="fas fa-star mr-1 text-caution"></i>{{ interpMinRating }}+</span>
    </div>

    <p v-if="errorMessage" role="alert" class="m-0 rounded-card border border-bad/40 bg-bad/10 px-4 py-3 text-sm text-ink-2"><i aria-hidden="true" class="fas fa-exclamation-circle mr-2 text-bad"></i>{{ errorMessage }}</p>

    <div v-if="isSearching" class="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-4">
      <div v-for="i in Math.min(maxResults, 12)" :key="i" class="aspect-[2/3] animate-pulse rounded-card bg-panel"></div>
    </div>

    <section v-else-if="results.length > 0" class="flex flex-col gap-4">
      <h2 class="m-0 text-[19px] font-bold text-ink">{{ results.length }} {{ results.length === 1 ? 'match' : 'matches' }}</h2>
      <div class="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-4">
        <MediaCard
          v-for="item in results"
          :key="item.id + '-' + item.media_type"
          :title="item.title"
          :poster="item.poster_path || ''"
          :badge="item.source === 'ai_suggestion' ? 'AI pick' : (item.media_type === 'tv' ? 'TV' : 'Movie')"
          :tone="item.source === 'ai_suggestion' ? 'brand' : 'neutral'"
          :placeholder-icon="item.media_type === 'tv' ? 'fas fa-tv' : 'fas fa-film'"
          @open="openModal(item)"
        >
          <span class="text-xs font-semibold text-ink-2">
            {{ item.media_type === 'tv' ? 'TV' : 'Movie' }}<template v-if="releaseYear(item)"> · {{ releaseYear(item) }}</template><template v-if="item.rating"> · <i aria-hidden="true" class="fas fa-star text-caution"></i> {{ Number(item.rating).toFixed(1) }}</template>
          </span>
          <template #actions>
            <button
              type="button"
              class="h-9 flex-1 cursor-pointer rounded-[8px] border-0 text-[13px] font-bold disabled:cursor-default"
              :class="requestButtonTone(item)"
              :disabled="isRequested(item) || isRequesting(item)"
              @click="requestItem(item)"
            >
              <i aria-hidden="true" :class="requestButtonIcon(item)" class="mr-1"></i>{{ requestButtonLabel(item) }}
            </button>
            <button type="button" class="h-9 w-9 cursor-pointer rounded-[8px] border hover:text-good" :class="feedbackOf(item) === 'like' ? 'border-good bg-good/15 text-good' : 'border-edge-strong bg-transparent text-ink-3'" :aria-pressed="feedbackOf(item) === 'like' ? 'true' : 'false'" aria-label="More like this" title="More like this" @click="toggleFeedback(item, 'like')"><i aria-hidden="true" class="fas fa-thumbs-up"></i></button>
            <button type="button" class="h-9 w-9 cursor-pointer rounded-[8px] border hover:text-bad" :class="feedbackOf(item) === 'dislike' ? 'border-bad bg-bad/15 text-bad' : 'border-edge-strong bg-transparent text-ink-3'" :aria-pressed="feedbackOf(item) === 'dislike' ? 'true' : 'false'" aria-label="Don't show this again" title="Don't show this again" @click="toggleFeedback(item, 'dislike')"><i aria-hidden="true" class="fas fa-thumbs-down"></i></button>
          </template>
        </MediaCard>
      </div>
    </section>

    <div v-else-if="hasSearched" class="flex flex-col items-center gap-2 rounded-card border border-dashed border-edge-strong px-6 py-14 text-center">
      <i aria-hidden="true" class="fas fa-search text-4xl text-ink-4"></i>
      <h2 class="m-0 text-lg font-bold text-ink">No matches</h2>
      <p class="m-0 max-w-md text-sm text-ink-3">Try describing it differently, widen the media type, or relax the search options.</p>
    </div>

    <div v-else-if="llmAvailable" class="grid gap-3 sm:grid-cols-3">
      <button
        v-for="example in examples"
        :key="example"
        type="button"
        class="cursor-pointer rounded-card border border-edge bg-panel p-4 text-left text-sm leading-relaxed text-ink-2 hover:border-brand-ink hover:text-ink"
        @click="rerunSearch(example)"
      >
        <span class="mb-2 block text-brand-ink"><i aria-hidden="true" class="fas fa-magic"></i></span>{{ example }}
      </button>
    </div>

    <MediaDetailsModal
      v-if="selectedItem"
      :item="selectedItem"
      :trailer-url="trailerUrl"
      :placeholder-icon="selectedItem.media_type === 'tv' ? 'fas fa-tv' : 'fas fa-film'"
      rationale-title="Why the AI picked this"
      @close="closeModal"
    >
      <template #badges>
        <span v-if="selectedItem.votes" class="rounded-md bg-raised px-2 py-1 text-ink-2">{{ formatVotes(selectedItem.votes) }} votes</span>
        <span v-if="selectedItem.original_language" class="rounded-md bg-raised px-2 py-1 text-ink-2"><i aria-hidden="true" class="fas fa-globe"></i> {{ selectedItem.original_language.toUpperCase() }}</span>
      </template>
      <template #actions>
        <div class="flex gap-1.5">
          <button
            type="button"
            class="h-10 cursor-pointer rounded-ctl border-0 px-4 text-sm font-bold disabled:cursor-default"
            :class="requestButtonTone(selectedItem)"
            :disabled="isRequested(selectedItem) || isRequesting(selectedItem)"
            @click="requestItem(selectedItem)"
          >
            <i aria-hidden="true" :class="requestButtonIcon(selectedItem)" class="mr-1"></i>{{ requestButtonLabel(selectedItem) }}
          </button>
          <button type="button" class="h-10 w-10 cursor-pointer rounded-ctl border" :class="feedbackOf(selectedItem) === 'like' ? 'border-good bg-good/15 text-good' : 'border-edge-strong bg-transparent text-ink-3'" :aria-pressed="feedbackOf(selectedItem) === 'like' ? 'true' : 'false'" aria-label="More like this" title="More like this" @click="toggleFeedback(selectedItem, 'like')"><i aria-hidden="true" class="fas fa-thumbs-up"></i></button>
          <button type="button" class="h-10 w-10 cursor-pointer rounded-ctl border" :class="feedbackOf(selectedItem) === 'dislike' ? 'border-bad bg-bad/15 text-bad' : 'border-edge-strong bg-transparent text-ink-3'" :aria-pressed="feedbackOf(selectedItem) === 'dislike' ? 'true' : 'false'" aria-label="Don't show this again" title="Don't show this again" @click="toggleFeedback(selectedItem, 'dislike')"><i aria-hidden="true" class="fas fa-thumbs-down"></i></button>
        </div>
      </template>
    </MediaDetailsModal>
  </div>
</template>

<script>
import PageHeader from '@/components/ui/PageHeader.vue';
import MediaCard from '@/components/ui/MediaCard.vue';
import MediaDetailsModal from '@/components/MediaDetailsModal.vue';
import axios from 'axios';
import { aiSearch, aiSearchRequest, aiSearchStatus, aiSearchFeedbackList, aiSearchFeedbackSet, aiSearchFeedbackDelete, aiSearchSeenClear } from '@/api/api.js';
import { loadTrailerUrl } from '@/utils/trailer.js';

const MEDIA_TYPE_OPTIONS = [
  { value: 'movie', label: 'Movies', icon: 'fas fa-film' },
  { value: 'tv', label: 'TV shows', icon: 'fas fa-tv' },
  { value: 'both', label: 'Both', icon: 'fas fa-layer-group' },
];

const TOGGLES = [
  { key: 'useHistory', title: 'Use viewing history', hint: "Personalise results with what you've already watched" },
  { key: 'excludeWatched', title: 'Exclude already watched', hint: "Hide titles you've already seen" },
  { key: 'excludeSeen', title: 'Hide earlier AI picks', hint: 'Skip titles from previous AI searches' },
];

const EXAMPLES = [
  'A tense sci-fi thriller set in space, nothing too gory',
  'Feel-good comedies for a lazy Sunday',
  'Award-winning foreign films from the last ten years',
];

export default {
  name: 'AiSearchPage',
  components: { PageHeader, MediaCard, MediaDetailsModal },
  // The dashboard shell passes settings props to every tab; this page does not use them.
  inheritAttrs: false,

  data() {
    return {
      query: '',
      mediaTypeOptions: MEDIA_TYPE_OPTIONS,
      toggles: TOGGLES,
      examples: EXAMPLES,
      mediaType: 'movie',
      isSearching: false,
      hasSearched: false,
      results: [],
      queryInterpretation: null,
      errorMessage: '',
      llmAvailable: true,
      requestedIds: new Set(),
      requestingIds: new Set(),
      // Item detail modal
      selectedItem: null,
      trailerUrl: null,
      // Advanced options
      showAdvanced: false,
      useHistory: true,
      excludeWatched: true,
      maxResults: 12,
      // Recent search history (persisted in localStorage)
      feedbackMap: {},
      excludeSeen: JSON.parse(localStorage.getItem('suggestarr_ai_exclude_seen') || 'false'),
      isResettingSeen: false,
      recentSearches: JSON.parse(localStorage.getItem('suggestarr_ai_search_history') || '[]'),
    };
  },

  watch: {
    excludeSeen(val) {
      localStorage.setItem('suggestarr_ai_exclude_seen', JSON.stringify(!!val));
    },
  },

  computed: {
    hasInterpretation() {
      const qi = this.queryInterpretation;
      if (!qi) return false;
      // For 'both' media type, interpretation is { movie: {...}, tv: {...} }
      const params = qi.genres !== undefined ? qi : (qi.movie || qi.tv || {});
      return (
        (params.genres && params.genres.length > 0) ||
        params.year_from ||
        params.year_to ||
        params.original_language ||
        params.min_rating != null
      );
    },

    interpParams() {
      const qi = this.queryInterpretation;
      if (!qi) return {};
      return qi.genres !== undefined ? qi : (qi.movie || qi.tv || {});
    },

    interpGenres() {
      const g = this.interpParams.genres;
      return g && g.length > 0 ? g.join(', ') : null;
    },

    interpYears() {
      const { year_from, year_to } = this.interpParams;
      if (year_from && year_to) return `${year_from}–${year_to}`;
      if (year_from) return `from ${year_from}`;
      if (year_to) return `until ${year_to}`;
      return null;
    },

    interpLang() {
      return this.interpParams.original_language || null;
    },

    interpMinRating() {
      const r = this.interpParams.min_rating;
      return r != null ? Number(r).toFixed(1) : null;
    },
  },

  methods: {

    async resetSeen() {
      if (this.isResettingSeen) return;
      this.isResettingSeen = true;
      try {
        await aiSearchSeenClear();
      } catch (err) {
        const msg = err.response?.data?.message || err.message || 'Failed to clear history.';
        this.errorMessage = msg;
      } finally {
        this.isResettingSeen = false;
      }
    },

    feedbackOf(item) {
      return this.feedbackMap[item.media_type + ':' + item.id] || null;
    },

    async toggleFeedback(item, kind) {
      const key = item.media_type + ':' + item.id;
      const current = this.feedbackMap[key] || null;
      try {
        if (current === kind) {
          await aiSearchFeedbackDelete(item.id, item.media_type);
          const next = { ...this.feedbackMap };
          delete next[key];
          this.feedbackMap = next;
        } else {
          const year = this.releaseYear(item);
          await aiSearchFeedbackSet(
            item.id,
            item.media_type,
            kind,
            item.title || null,
            year ? Number(year) : null,
          );
          this.feedbackMap = { ...this.feedbackMap, [key]: kind };
          if (kind === 'dislike') {
            this.results = this.results.filter(r => !(r.id === item.id && r.media_type === item.media_type));
            if (this.selectedItem && this.selectedItem.id === item.id && this.selectedItem.media_type === item.media_type) {
              this.closeModal();
            }
          }
        }
      } catch (err) {
        const msg = err.response?.data?.message || err.message || 'Failed to save feedback.';
        this.errorMessage = msg;
      }
    },

    async loadFeedback() {
      try {
        const res = await aiSearchFeedbackList();
        const map = {};
        for (const row of res.data.feedback || []) {
          map[row.media_type + ':' + row.tmdb_id] = row.feedback;
        }
        this.feedbackMap = map;
      } catch {
        // non-fatal
      }
    },

    async checkLlmStatus() {
      try {
        const res = await aiSearchStatus();
        this.llmAvailable = res.data.available;
      } catch {
        this.llmAvailable = false;
      }
    },

    async runSearch() {
      if (!this.query.trim() || this.isSearching || !this.llmAvailable) return;

      this.isSearching = true;
      this.hasSearched = false;
      this.errorMessage = '';
      this.results = [];
      this.queryInterpretation = null;

      try {
        const res = await aiSearch(this.query.trim(), this.mediaType, [], this.maxResults, this.useHistory, this.excludeWatched, this.excludeSeen);
        const data = res.data;

        if (data.status === 'error') {
          this.errorMessage = data.message || 'Search failed.';
          return;
        }

        this.results = data.results || [];
        this.queryInterpretation = data.ai_reasoning || data.query_interpretation || null;
        this.hasSearched = true;
        this.saveToHistory(this.query.trim());
      } catch (err) {
        const msg = err.response?.data?.message || err.message || 'Unexpected error.';
        this.errorMessage = msg;
      } finally {
        this.isSearching = false;
      }
    },

    async requestItem(item) {
      const key = item.id + '-' + item.media_type;
      if (this.requestedIds.has(key) || this.requestingIds.has(key)) return;

      this.requestingIds = new Set([...this.requestingIds, key]);

      try {
        const res = await aiSearchRequest(item.id, item.media_type, item.rationale || '', item, this.query.trim());
        if (res.data.status === 'success') {
          this.requestedIds = new Set([...this.requestedIds, key]);
        } else {
          this.$toast.open({ message: res.data.message || 'Request failed.', type: 'error' });
        }
      } catch (err) {
        this.$toast.open({ message: err.response?.data?.message || 'Request failed.', type: 'error' });
      } finally {
        this.requestingIds = new Set([...this.requestingIds].filter(k => k !== key));
      }
    },

    saveToHistory(query) {
      if (!query) return;
      let history = JSON.parse(localStorage.getItem('suggestarr_ai_search_history') || '[]');
      const idx = history.indexOf(query);
      if (idx !== -1) history.splice(idx, 1);
      history.unshift(query);
      history = history.slice(0, 8);
      localStorage.setItem('suggestarr_ai_search_history', JSON.stringify(history));
      this.recentSearches = history;
    },

    rerunSearch(query) {
      this.query = query;
      this.runSearch();
    },

    clearHistory() {
      localStorage.removeItem('suggestarr_ai_search_history');
      this.recentSearches = [];
    },

    toggleOption(key) {
      this[key] = !this[key];
    },

    async openModal(item) {
      this.selectedItem = item;
      this.trailerUrl = null;
      const url = await loadTrailerUrl(axios, item);
      // The modal may show another title by the time the answer arrives.
      if (this.selectedItem === item) this.trailerUrl = url;
    },

    closeModal() {
      this.selectedItem = null;
      this.trailerUrl = null;
    },

    releaseYear(item) {
      const date = item.release_date;
      if (!date) return null;
      return date.substring(0, 4);
    },

    formatVotes(votes) {
      const n = Number(votes);
      if (!n) return null;
      if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
      if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'k';
      return String(n);
    },

    isRequested(item) {
      return this.requestedIds.has(item.id + '-' + item.media_type);
    },

    isRequesting(item) {
      return this.requestingIds.has(item.id + '-' + item.media_type);
    },

    requestButtonTone(item) {
      if (this.isRequested(item)) return 'bg-good/15 text-good';
      if (this.isRequesting(item)) return 'bg-raised text-ink-3';
      return 'bg-brand text-white';
    },

    requestButtonIcon(item) {
      const key = item.id + '-' + item.media_type;
      if (this.requestedIds.has(key)) return 'fas fa-check';
      if (this.requestingIds.has(key)) return 'fas fa-spinner fa-spin';
      return 'fas fa-plus';
    },

    requestButtonLabel(item) {
      const key = item.id + '-' + item.media_type;
      if (this.requestedIds.has(key)) return 'Requested';
      if (this.requestingIds.has(key)) return 'Requesting…';
      return 'Request';
    },
  },

  mounted() {
    this.checkLlmStatus();
    this.loadFeedback();
  },
};
</script>

