<template>
  <AppDialog width="max-w-3xl" title="Dry run preview" icon="fas fa-eye" @close="$emit('close')">
    <template #subtitle>
      {{ job.name }}<template v-if="cachedAt"> · from {{ formatCachedAt(cachedAt) }}</template> · nothing was requested
    </template>

    <div class="flex flex-col gap-4">
      <div class="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-ctl border border-edge bg-panel-2 px-4 py-3 text-sm">
        <span class="text-ink-2"><strong class="text-lg text-ink">{{ wouldRequestCount }}</strong> would be requested</span>
        <span v-if="filteredOutCount > 0" class="text-ink-3"><strong class="text-ink-2">{{ filteredOutCount }}</strong> skipped</span>

        <div v-if="hasFilterData && filteredOutCount > 0" role="radiogroup" aria-label="Show" class="ml-auto flex rounded-ctl border border-edge-strong bg-canvas p-1">
          <button
            v-for="option in [{ all: true, label: `All ${items.length}` }, { all: false, label: `To request ${wouldRequestCount}` }]"
            :key="option.label"
            type="button"
            role="radio"
            :aria-checked="showAll === option.all ? 'true' : 'false'"
            class="h-7 cursor-pointer rounded-[7px] border-0 px-3 text-xs font-semibold"
            :class="showAll === option.all ? 'bg-raised text-ink' : 'bg-transparent text-ink-3 hover:text-ink'"
            @click="showAll = option.all"
          >{{ option.label }}</button>
        </div>
      </div>

      <div v-if="displayedItems.length === 0" class="flex flex-col items-center gap-2 py-10 text-center">
        <i aria-hidden="true" class="fas fa-check-circle text-3xl text-good"></i>
        <p class="m-0 font-semibold text-ink">Nothing new to request</p>
        <p class="m-0 max-w-sm text-[13px] text-ink-3">All matching content is already downloaded, requested, or the filters returned no results.</p>
      </div>

      <ul v-else class="m-0 flex list-none flex-col gap-2 p-0">
        <li
          v-for="item in displayedItems"
          :key="item.tmdb_id"
          class="flex gap-3.5 rounded-ctl border border-edge bg-panel-2 p-3"
          :class="{ 'opacity-60': !itemWouldRequest(item) }"
        >
          <div class="h-[69px] w-[46px] shrink-0 overflow-hidden rounded-[6px] bg-raised">
            <img v-if="item.poster_path" :src="posterUrl(item.poster_path)" :alt="item.title" loading="lazy" class="h-full w-full object-cover" />
            <div v-else class="grid h-full place-items-center text-ink-4"><i aria-hidden="true" :class="item.media_type === 'tv' ? 'fas fa-tv' : 'fas fa-film'"></i></div>
          </div>

          <div class="flex min-w-0 flex-1 flex-col gap-1">
            <div class="flex min-w-0 items-center gap-2">
              <span class="min-w-0 flex-1 truncate text-sm font-semibold text-ink">{{ item.title }}</span>
              <span v-if="item.already_downloaded" class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide bg-notice/15 text-notice">In library</span>
              <span v-else-if="item.already_requested" class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide bg-caution/15 text-caution">Requested</span>
              <span v-else-if="itemWouldRequest(item)" class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide bg-good/15 text-good">Will request</span>
            </div>

            <div class="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-ink-3">
              <span class="font-semibold">{{ item.media_type === 'tv' ? 'TV' : 'Movie' }}</span>
              <span v-if="releaseYear(item)">{{ releaseYear(item) }}</span>
              <span v-if="item.vote_average" class="text-caution"><i aria-hidden="true" class="fas fa-star mr-0.5 text-[10px]"></i>{{ Number(item.vote_average).toFixed(1) }}</span>
              <button
                v-if="hasTrailerTarget(item)"
                type="button"
                class="cursor-pointer border-0 bg-transparent p-0 text-xs font-semibold text-ink-3 hover:text-bad disabled:cursor-default disabled:opacity-50"
                :disabled="trailerUnavailable(item)"
                @click.stop="watchTrailer(item)">
                <i aria-hidden="true" class="mr-1" :class="openingTrailer.includes(trailerKey(item)) ? 'fas fa-spinner fa-spin' : 'fab fa-youtube'"></i>{{ withoutTrailer.includes(trailerKey(item)) ? 'No trailer' : 'Trailer' }}
              </button>
            </div>

            <div v-if="hasFilters(item)" class="flex flex-wrap gap-1">
              <template v-for="(filter, key) in activeFilters(item)" :key="key">
                <span
                  v-if="filter.passed !== undefined"
                  class="inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-px text-[10px] font-medium"
                  :class="filterBadgeClass(filter)"
                  :title="filterTitle(filter)"
                >
                  <i aria-hidden="true" class="text-[8px]" :class="filterIcon(filter)"></i>
                  {{ filter.label }}
                  <span v-if="filter.value != null" class="opacity-75">{{ filter.value }}</span>
                </span>
              </template>
            </div>

            <p v-if="!itemWouldRequest(item)" class="m-0 text-xs text-caution"><i aria-hidden="true" class="fas fa-ban mr-1 text-[10px]"></i>{{ skipReason(item) }}</p>
            <p v-if="item.rationale" class="m-0 text-xs italic text-brand-ink"><i aria-hidden="true" class="fas fa-magic mr-1"></i>{{ item.rationale }}</p>
            <p v-if="item.overview" class="m-0 text-xs leading-snug text-ink-3">{{ truncate(item.overview, 120) }}</p>
            <p v-if="item.source && item.source.title" class="m-0 truncate text-xs text-ink-4">Similar to <span class="text-ink-2">{{ item.source.title }}</span></p>
            <p v-if="sourceOriginLabel(item)" class="m-0 text-xs text-ink-4">
              <i :class="sourceOriginLabel(item).icon"></i> Seeded from {{ sourceOriginLabel(item).name }} watch history
            </p>
          </div>
        </li>
      </ul>
    </div>

    <template #footer>
      <button type="button" class="ui-btn" @click="$emit('close')">Close</button>
      <button v-if="wouldRequestCount > 0" type="button" class="ui-btn-primary" @click="$emit('run')"><i aria-hidden="true" class="fas fa-bolt"></i>Run job now</button>
    </template>
  </AppDialog>
</template>

<script>
import axios from 'axios';
import AppDialog from '@/components/ui/AppDialog.vue';
import { openTrailer, trailerTarget } from '@/utils/trailer.js';

export default {
  name: 'DryRunResultModal',
  components: { AppDialog },
  props: {
    job: { type: Object, required: true },
    items: { type: Array, default: () => [] },
    cachedAt: { type: Number, default: null },
  },
  emits: ['close', 'run'],
  data() {
    return { showAll: true, withoutTrailer: [], openingTrailer: [] };
  },
  computed: {
    hasFilterData() {
      return this.items.some(i => i.filter_results != null);
    },
    wouldRequestCount() {
      return this.items.filter(i => this.itemWouldRequest(i)).length;
    },
    filteredOutCount() {
      return this.items.length - this.wouldRequestCount;
    },
    displayedItems() {
      if (!this.hasFilterData || this.showAll) return this.items;
      return this.items.filter(i => this.itemWouldRequest(i));
    },
  },
  methods: {
    itemWouldRequest(item) {
      if (item.would_request !== undefined) return item.would_request;
      return true;
    },
    hasTrailerTarget(item) {
      return Boolean(trailerTarget(item));
    },
    trailerKey(item) {
      return `${item.media_type}:${item.tmdb_id}`;
    },
    sourceOriginLabel(item) {
      const origins = {
        trakt_history: { name: 'Trakt', icon: 'icon-trakt' },
        simkl_history: { name: 'Simkl', icon: 'icon-simkl' },
      };
      return origins[item.source?.source_origin] || null;
    },
    trailerUnavailable(item) {
      const key = this.trailerKey(item);
      return this.withoutTrailer.includes(key) || this.openingTrailer.includes(key);
    },
    async watchTrailer(item) {
      const key = this.trailerKey(item);
      // A second click while the lookup is running would open a second blank tab.
      if (this.openingTrailer.includes(key)) return;
      this.openingTrailer = [...this.openingTrailer, key];
      try {
        const outcome = await openTrailer(axios, item);
        if (outcome === 'none') {
          this.withoutTrailer = [...this.withoutTrailer, key];
        } else if (outcome === 'blocked') {
          this.$toast?.open({
            message: 'Your browser blocked the trailer tab. Allow pop-ups for this site and try again.',
            type: 'warning',
          });
        }
      } finally {
        this.openingTrailer = this.openingTrailer.filter(k => k !== key);
      }
    },
    posterUrl(path) {
      if (!path) return null;
      if (path.startsWith('http')) return path;
      return `https://image.tmdb.org/t/p/w92${path}`;
    },
    releaseYear(item) {
      const date = item.release_date;
      return date ? date.slice(0, 4) : null;
    },
    truncate(text, maxLen) {
      if (!text) return '';
      return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
    },
    hasFilters(item) {
      if (!item.filter_results) return false;
      return Object.keys(item.filter_results).some(k => k !== 'passed');
    },
    activeFilters(item) {
      if (!item.filter_results) return {};
      const { passed, ...filters } = item.filter_results; // eslint-disable-line no-unused-vars
      return filters;
    },
    filterBadgeClass(filter) {
      if (filter.passed === true) return 'border-good/25 bg-good/10 text-good';
      if (filter.passed === false) return 'border-bad/25 bg-bad/10 text-bad';
      return 'border-edge bg-raised text-ink-3';
    },
    filterIcon(filter) {
      if (filter.passed === true) return 'fas fa-check';
      if (filter.passed === false) return 'fas fa-times';
      return 'fas fa-minus';
    },
    filterTitle(filter) {
      if (filter.reason) return filter.reason;
      if (filter.passed === true) return `${filter.label}: OK`;
      if (filter.passed === null) return `${filter.label}: not configured`;
      return filter.label;
    },
    skipReason(item) {
      if (item.already_downloaded) return 'Already in your library';
      if (item.already_requested) return 'Already pending request';
      // Find first failing filter
      const fr = item.filter_results;
      if (fr) {
        for (const [key, f] of Object.entries(fr)) {
          if (key === 'passed') continue;
          if (f && f.passed === false) {
            return f.reason ? `${f.label}: ${f.reason}` : `Filtered by ${f.label}`;
          }
        }
      }
      return 'Filtered out';
    },
    formatCachedAt(ts) {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    },
  },
};
</script>
