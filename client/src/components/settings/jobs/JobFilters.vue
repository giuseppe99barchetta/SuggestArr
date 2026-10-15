<template>
  <div class="flex flex-col gap-5">
    <!-- Rating Source Selector -->
    <div class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <label>Rating Source</label>
      <div class="flex flex-col gap-2">
        <label
          v-for="option in ratingSourceOptions"
          :key="option.value"
          class="flex cursor-pointer items-start gap-2.5 rounded-ctl border px-3 py-2.5 transition hover:border-brand"
          :class="localFilters.rating_source === option.value ? 'border-brand bg-brand/8' : 'border-edge bg-white/2 hover:bg-white/4'"
        >
          <input
            type="radio"
            :value="option.value"
            v-model="localFilters.rating_source"
            class="mt-1 shrink-0 accent-brand"
          />
          <div class="flex flex-col gap-0.5">
            <span class="text-sm font-semibold text-ink">{{ option.label }}</span>
            <span class="text-xs leading-tight text-ink-4">{{ option.description }}</span>
          </div>
        </label>
      </div>
    </div>

    <!-- TMDB Rating Filter (hidden when source is imdb-only) -->
    <div v-if="localFilters.rating_source !== 'imdb'" class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <label>{{ localFilters.rating_source === 'both' ? 'Minimum Rating (TMDB)' : 'Minimum Rating' }}: {{ localFilters.vote_average_gte || 0 }}</label>
      <input
        v-model.number="localFilters.vote_average_gte"
        type="range"
        min="0"
        max="10"
        step="0.5"
        class="mt-2 w-full accent-brand"
      />
      <div class="mt-2 flex justify-between text-xs text-ink-4">
        <span>0</span>
        <span>5</span>
        <span>10</span>
      </div>
    </div>

    <!-- TMDB Vote Count Filter (hidden when source is imdb-only) -->
    <div v-if="localFilters.rating_source !== 'imdb'" class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <label for="voteCount">{{ localFilters.rating_source === 'both' ? 'Minimum Vote Count (TMDB)' : 'Minimum Vote Count' }}</label>
      <input
        id="voteCount"
        v-model.number="localFilters.vote_count_gte"
        type="number"
        min="0"
        step="100"
        placeholder="e.g., 1000"
        class="ui-input"
      />
      <small class="mt-2 text-sm text-ink-4">Filter out content with too few votes</small>
    </div>

    <!-- IMDB Rating Filter (shown when IMDB is part of rating source) -->
    <div v-if="localFilters.rating_source !== 'tmdb'" class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <label>IMDB Minimum Rating: {{ (localFilters.imdb_rating_gte || 0).toFixed(1) }}</label>
      <input
        v-model.number="localFilters.imdb_rating_gte"
        type="range"
        min="0"
        max="10"
        step="0.1"
        class="mt-2 w-full accent-[#f5c518]"
      />
      <div class="mt-2 flex justify-between text-xs text-ink-4">
        <span>0</span>
        <span>5</span>
        <span>10</span>
      </div>
      <small class="mt-2 text-sm text-ink-4">
        <i class="fas fa-star text-[#f5c518]"></i>
        Filter by IMDB community rating — requires OMDb API key configured in Connections
      </small>
    </div>

    <!-- IMDB Vote Count Filter (shown when IMDB is part of rating source) -->
    <div v-if="localFilters.rating_source !== 'tmdb'" class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <label for="imdbVotes">IMDB Minimum Vote Count</label>
      <input
        id="imdbVotes"
        v-model.number="localFilters.imdb_min_votes"
        type="number"
        min="0"
        step="1"
        placeholder="e.g., 10000"
        class="ui-input"
      />
      <small class="mt-2 text-sm text-ink-4">Filter out content with too few IMDB votes (more votes = more reliable rating)</small>
    </div>

    <!-- "Both must pass" notice -->
    <div v-if="localFilters.rating_source === 'both'" class="flex items-center gap-2 rounded-ctl border border-[#f5c518]/25 bg-[#f5c518]/8 px-3.5 py-2.5 text-sm text-ink-2 [&>i]:shrink-0 [&>i]:text-[#f5c518]">
      <i class="fas fa-info-circle"></i>
      Content must pass <strong>both</strong> TMDB and IMDB thresholds to be recommended.
    </div>

    <!-- Include No Rating Toggle -->
    <div class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <div class="flex items-center gap-3 py-2">
        <BaseCheckbox v-model="localFilters.include_no_rating">
          <span class="font-medium text-ink">
            {{ localFilters.rating_source !== 'tmdb' ? 'Include content without IMDB rating' : 'Include content without rating' }}
          </span>
        </BaseCheckbox>
      </div>
      <small class="mt-2 text-sm text-ink-4">Also include content that doesn't have any rating data yet</small>
    </div>

    <!-- Minimum Seasons Filter (TV only, discover/recommendation) -->
    <div v-if="mediaType === 'tv' && jobType !== 'trakt_recommendations'" class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <label for="minSeasons">Minimum Seasons: {{ localFilters.min_seasons || 1 }}</label>
      <input
        id="minSeasons"
        v-model.number="localFilters.min_seasons"
        type="range"
        min="1"
        max="10"
        step="1"
        class="mt-2 w-full accent-brand"
      />
      <small class="mt-2 text-sm text-ink-4">Only include TV shows with at least this many seasons</small>
    </div>

    <!-- Request Seasons Option (TV-capable jobs) -->
    <div v-if="mediaType === 'tv' || mediaType === 'both'" class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <div class="flex items-center gap-3 py-2">
        <BaseCheckbox v-model="localFilters.request_first_season_only">
          <span class="font-medium text-ink">Request first season only</span>
        </BaseCheckbox>
      </div>
      <small class="mt-2 text-sm text-ink-4">Send season 1 only when requesting new TV series</small>
    </div>

    <!-- Minimum Runtime Filter -->
    <div class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <label for="minRuntime">Minimum Runtime (minutes)</label>
      <input
        id="minRuntime"
        v-model.number="localFilters.min_runtime"
        type="number"
        min="0"
        step="1"
        placeholder="e.g., 60"
        class="ui-input"
      />
      <small class="mt-2 text-sm text-ink-4">Exclude short content below this runtime — useful to filter out clips and shorts</small>
    </div>

    <!-- Release Date Filter -->
    <div class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <label>Release Date Range</label>
      <div class="flex gap-4 max-[480px]:flex-col">
        <div class="flex-1">
          <span class="mb-1.5 block text-xs text-ink-4">From</span>
          <input v-model="releaseDateFrom" type="date" class="ui-input" />
        </div>
        <div class="flex-1">
          <span class="mb-1.5 block text-xs text-ink-4">To</span>
          <input v-model="releaseDateTo" type="date" class="ui-input" />
        </div>
      </div>
    </div>

    <!-- Language Filter -->
    <div class="flex flex-col">
      <BaseDropdown
        v-model="localFilters.with_original_language"
        :options="languageOptions"
        label="Original Language"
        placeholder="Select language"
        option-key="value"
        option-label="label"
        option-value="value"
      />
    </div>

    <!-- Streaming Region & Provider Exclusion -->
    <div class="flex flex-col">
      <BaseDropdown
        v-model="localFilters.watch_region"
        :options="watchRegions"
        label="Streaming Region"
        placeholder="Use global setting"
        option-key="iso_3166_1"
        option-label="english_name"
        option-value="iso_3166_1"
        @update:modelValue="onRegionChange"
      />
      <small class="mt-2 text-sm text-ink-4">Region used to check streaming availability</small>
    </div>

    <div class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <label>Streaming Services to Exclude</label>
      <div v-if="localFilters.watch_region && watchProviders.length > 0" class="flex max-h-[200px] flex-wrap gap-2 overflow-y-auto rounded-ctl border border-edge bg-white/3 p-4">
        <button
          v-for="provider in watchProviders"
          :key="provider.provider_id"
          type="button"
          class="cursor-pointer rounded-[8px] border px-3 py-2 text-sm transition"
          :class="isProviderExcluded(provider.provider_id) ? 'border-bad bg-bad/10 text-bad' : 'border-edge bg-panel-2 text-ink-3 hover:border-ink-4 hover:text-ink'"
          @click="toggleProvider(provider)"
        >
          {{ provider.provider_name }}
        </button>
      </div>
      <p v-else-if="localFilters.watch_region && watchProviders.length === 0" class="flex items-center gap-2 p-4 text-sm text-ink-4">
        <i class="fas fa-spinner fa-spin"></i> Loading providers...
      </p>
      <p v-else class="m-0 rounded-ctl border border-edge bg-white/3 px-4 py-3 text-sm text-ink-4">
        Select a region above to choose which streaming services to exclude
      </p>
      <small class="mt-2 text-sm text-ink-4">Content already available on these services will be skipped</small>
    </div>

    <!-- Include TVOD Toggle -->
    <div class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <div class="flex items-center gap-3 py-2">
        <BaseCheckbox v-model="localFilters.include_tvod">
          <span class="font-medium text-ink">Include rent/buy (TVOD) availability</span>
        </BaseCheckbox>
      </div>
      <small class="mt-2 text-sm text-ink-4">Also match providers available for rent or purchase, not just subscription (flatrate)</small>
    </div>

    <!-- Genre Filters -->
    <div class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <label>Genres to Include</label>
      <div class="flex max-h-[200px] flex-wrap gap-2 overflow-y-auto rounded-ctl border border-edge bg-white/3 p-4" v-if="genres.length > 0">
        <button
          v-for="genre in genres"
          :key="genre.id"
          type="button"
          class="cursor-pointer rounded-[8px] border px-3 py-2 text-sm transition"
          :class="isGenreIncluded(genre.id) ? 'border-good bg-good/10 text-good' : 'border-edge bg-panel-2 text-ink-3 hover:border-ink-4 hover:text-ink'"
          @click="toggleGenreInclude(genre.id)"
        >
          {{ genre.name }}
        </button>
      </div>
      <p v-else class="flex items-center gap-2 p-4 text-sm text-ink-4">
        <i class="fas fa-spinner fa-spin"></i> Loading genres...
      </p>
      <small class="mt-2 text-sm text-ink-4">Content must match at least one selected genre</small>
    </div>

    <div class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <label>Genres to Exclude</label>
      <div class="flex max-h-[200px] flex-wrap gap-2 overflow-y-auto rounded-ctl border border-edge bg-white/3 p-4" v-if="genres.length > 0">
        <button
          v-for="genre in genres"
          :key="genre.id"
          type="button"
          class="cursor-pointer rounded-[8px] border px-3 py-2 text-sm transition"
          :class="isGenreExcluded(genre.id) ? 'border-bad bg-bad/10 text-bad' : 'border-edge bg-panel-2 text-ink-3 hover:border-ink-4 hover:text-ink'"
          @click="toggleGenreExclude(genre.id)"
        >
          {{ genre.name }}
        </button>
      </div>
      <p v-else class="flex items-center gap-2 p-4 text-sm text-ink-4">
        <i class="fas fa-spinner fa-spin"></i> Loading genres...
      </p>
    </div>

    <div class="flex flex-col [&>label]:mb-2 [&>label]:text-sm [&>label]:font-medium [&>label]:text-ink-2">
      <label for="keywordSearch">TMDb Keywords to Exclude</label>
      <div class="flex gap-2">
        <input
          id="keywordSearch"
          v-model.trim="keywordQuery"
          type="search"
          placeholder="e.g., Bollywood"
          class="ui-input flex-1"
          @keydown.enter.prevent="searchKeywords"
        />
        <button type="button" class="ui-btn" :disabled="keywordQuery.length < 2" @click="searchKeywords">
          Search
        </button>
      </div>
      <div v-if="(localFilters.without_keywords || []).length" class="flex max-h-[200px] flex-wrap gap-2 overflow-y-auto rounded-ctl border border-edge bg-white/3 p-4">
        <button
          v-for="keyword in localFilters.without_keywords"
          :key="keyword.id"
          type="button"
          class="cursor-pointer rounded-[8px] border px-3 py-2 text-sm transition border-bad bg-bad/10 text-bad"
          @click="toggleKeyword(keyword)"
        >
          {{ keyword.name }} <i class="fas fa-times"></i>
        </button>
      </div>
      <div v-if="keywordResults.length" class="flex max-h-[200px] flex-wrap gap-2 overflow-y-auto rounded-ctl border border-edge bg-white/3 p-4">
        <button
          v-for="keyword in keywordResults"
          :key="keyword.id"
          type="button"
          class="cursor-pointer rounded-[8px] border px-3 py-2 text-sm transition"
          :class="isKeywordExcluded(keyword.id) ? 'border-bad bg-bad/10 text-bad' : 'border-edge bg-panel-2 text-ink-3 hover:border-ink-4 hover:text-ink'"
          @click="toggleKeyword(keyword)"
        >
          {{ keyword.name }}
        </button>
      </div>
      <small class="mt-2 text-sm text-ink-4">Exclude titles carrying any selected TMDb keyword. Search and select the exact keyword.</small>
    </div>

    <!-- Sort By (discover jobs only) -->
    <div v-if="jobType === 'discover'" class="flex flex-col">
      <BaseDropdown
        v-model="localFilters.sort_by"
        :options="sortOptions"
        label="Sort Results By"
        placeholder="Select sort order"
        option-key="value"
        option-label="label"
        option-value="value"
      />
    </div>
  </div>
</template>

<script>
import { jobsApi } from '@/api/jobsApi';
import BaseDropdown from '@/components/common/BaseDropdown.vue';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';

export default {
  name: 'JobFilters',
  components: {
    BaseDropdown,
    BaseCheckbox,
  },
  props: {
    modelValue: {
      type: Object,
      default: () => ({})
    },
    mediaType: {
      type: String,
      default: 'movie'
    },
    jobType: {
      type: String,
      default: 'discover'
    }
  },
  emits: ['update:modelValue'],
  data() {
    return {
      localFilters: { rating_source: 'tmdb', ...this.modelValue },
      genres: [],
      watchRegions: [],
      watchProviders: [],
      keywordQuery: '',
      keywordResults: [],
      isUpdating: false,
      ratingSourceOptions: [
        {
          value: 'tmdb',
          label: 'TMDB Only',
          description: 'Use TMDB ratings. No OMDb API key required.'
        },
        {
          value: 'imdb',
          label: 'IMDB Only',
          description: 'Use IMDB ratings via OMDb API. Requires an OMDb API key in Connections.'
        },
        {
          value: 'both',
          label: 'Both (stricter)',
          description: 'Content must pass both TMDB and IMDB thresholds.'
        }
      ],
      languageOptions: [
        { value: '', label: 'Any Language' },
        { value: 'en', label: 'English' },
        { value: 'es', label: 'Spanish' },
        { value: 'fr', label: 'French' },
        { value: 'de', label: 'German' },
        { value: 'it', label: 'Italian' },
        { value: 'pt', label: 'Portuguese' },
        { value: 'ja', label: 'Japanese' },
        { value: 'ko', label: 'Korean' },
        { value: 'zh', label: 'Chinese' },
        { value: 'hi', label: 'Hindi' },
        { value: 'ru', label: 'Russian' },
        { value: 'ar', label: 'Arabic' },
        { value: 'tr', label: 'Turkish' },
        { value: 'nl', label: 'Dutch' },
        { value: 'pl', label: 'Polish' },
        { value: 'sv', label: 'Swedish' },
        { value: 'da', label: 'Danish' },
        { value: 'no', label: 'Norwegian' },
        { value: 'fi', label: 'Finnish' },
        { value: 'th', label: 'Thai' }
      ],
      sortOptions: [
        { value: 'popularity.desc', label: 'Popularity (High to Low)' },
        { value: 'popularity.asc', label: 'Popularity (Low to High)' },
        { value: 'vote_average.desc', label: 'Rating (High to Low)' },
        { value: 'vote_average.asc', label: 'Rating (Low to High)' },
        { value: 'primary_release_date.desc', label: 'Release Date (Newest)' },
        { value: 'primary_release_date.asc', label: 'Release Date (Oldest)' },
        { value: 'revenue.desc', label: 'Revenue (Highest)' }
      ]
    };
  },
  computed: {
    releaseDateFrom: {
      get() {
        const key = this.mediaType === 'movie' ? 'primary_release_date_gte' : 'first_air_date_gte';
        return this.localFilters[key] || '';
      },
      set(value) {
        const key = this.mediaType === 'movie' ? 'primary_release_date_gte' : 'first_air_date_gte';
        this.localFilters[key] = value || null;
      }
    },
    releaseDateTo: {
      get() {
        const key = this.mediaType === 'movie' ? 'primary_release_date_lte' : 'first_air_date_lte';
        return this.localFilters[key] || '';
      },
      set(value) {
        const key = this.mediaType === 'movie' ? 'primary_release_date_lte' : 'first_air_date_lte';
        this.localFilters[key] = value || null;
      }
    }
  },
  watch: {
    modelValue: {
      handler(newVal) {
        if (this.isUpdating) return;
        const newStr = JSON.stringify(newVal);
        const localStr = JSON.stringify(this.localFilters);
        if (newStr !== localStr) {
          this.localFilters = { rating_source: 'tmdb', ...JSON.parse(newStr) };
        }
      },
      deep: true
    },
    localFilters: {
      handler(newVal) {
        if (this.isUpdating) return;
        this.isUpdating = true;
        this.$emit('update:modelValue', JSON.parse(JSON.stringify(newVal)));
        this.$nextTick(() => {
          this.isUpdating = false;
        });
      },
      deep: true
    },
    mediaType: {
      handler() {
        this.loadGenres();
      },
      immediate: true
    }
  },
  async mounted() {
    await Promise.all([
      this.loadGenres(),
      this.loadWatchRegions()
    ]);
    if (this.localFilters.watch_region) {
      await this.loadWatchProviders(this.localFilters.watch_region);
    }
  },
  methods: {
    isGenreIncluded(genreId) {
      return (this.localFilters.with_genres || []).includes(genreId);
    },

    toggleGenreInclude(genreId) {
      const included = this.localFilters.with_genres || (this.localFilters.with_genres = []);
      const index = included.indexOf(genreId);
      index === -1 ? included.push(genreId) : included.splice(index, 1);
    },

    async loadGenres() {
      try {
        const response = await jobsApi.getGenres(this.mediaType);
        if (response.status === 'success') {
          this.genres = response.genres;
        }
      } catch (error) {
        console.error('Failed to load genres:', error);
        this.genres = this.mediaType === 'movie'
          ? [
              { id: 28, name: 'Action' },
              { id: 12, name: 'Adventure' },
              { id: 16, name: 'Animation' },
              { id: 35, name: 'Comedy' },
              { id: 80, name: 'Crime' },
              { id: 99, name: 'Documentary' },
              { id: 18, name: 'Drama' },
              { id: 10751, name: 'Family' },
              { id: 14, name: 'Fantasy' },
              { id: 36, name: 'History' },
              { id: 27, name: 'Horror' },
              { id: 10402, name: 'Music' },
              { id: 9648, name: 'Mystery' },
              { id: 10749, name: 'Romance' },
              { id: 878, name: 'Science Fiction' },
              { id: 10770, name: 'TV Movie' },
              { id: 53, name: 'Thriller' },
              { id: 10752, name: 'War' },
              { id: 37, name: 'Western' }
            ]
          : [
              { id: 10759, name: 'Action & Adventure' },
              { id: 16, name: 'Animation' },
              { id: 35, name: 'Comedy' },
              { id: 80, name: 'Crime' },
              { id: 99, name: 'Documentary' },
              { id: 18, name: 'Drama' },
              { id: 10751, name: 'Family' },
              { id: 10762, name: 'Kids' },
              { id: 9648, name: 'Mystery' },
              { id: 10763, name: 'News' },
              { id: 10764, name: 'Reality' },
              { id: 10765, name: 'Sci-Fi & Fantasy' },
              { id: 10766, name: 'Soap' },
              { id: 10767, name: 'Talk' },
              { id: 10768, name: 'War & Politics' },
              { id: 37, name: 'Western' }
            ];
      }
    },

    async loadWatchRegions() {
      try {
        const response = await jobsApi.getWatchRegions();
        if (response.status === 'success') {
          this.watchRegions = response.regions;
        }
      } catch (error) {
        console.error('Failed to load watch regions:', error);
      }
    },

    async loadWatchProviders(region) {
      this.watchProviders = [];
      if (!region) return;
      try {
        const response = await jobsApi.getWatchProviders(region);
        if (response.status === 'success') {
          this.watchProviders = response.providers.slice().sort((a, b) =>
            a.provider_name.localeCompare(b.provider_name)
          );
        }
      } catch (error) {
        console.error('Failed to load watch providers:', error);
      }
    },

    async onRegionChange(region) {
      this.localFilters.with_watch_providers = [];
      await this.loadWatchProviders(region);
    },

    isProviderExcluded(providerId) {
      const excluded = this.localFilters.with_watch_providers || [];
      return excluded.some(p => String(p.provider_id) === String(providerId));
    },

    toggleProvider(provider) {
      if (!this.localFilters.with_watch_providers) {
        this.localFilters.with_watch_providers = [];
      }
      const idx = this.localFilters.with_watch_providers.findIndex(
        p => String(p.provider_id) === String(provider.provider_id)
      );
      if (idx === -1) {
        this.localFilters.with_watch_providers.push({
          provider_id: provider.provider_id,
          provider_name: provider.provider_name
        });
      } else {
        this.localFilters.with_watch_providers.splice(idx, 1);
      }
    },

    isGenreExcluded(genreId) {
      const excluded = this.localFilters.without_genres || [];
      return excluded.includes(genreId);
    },

    toggleGenreExclude(genreId) {
      if (!this.localFilters.without_genres) {
        this.localFilters.without_genres = [];
      }

      const index = this.localFilters.without_genres.indexOf(genreId);
      if (index === -1) {
        this.localFilters.without_genres.push(genreId);
      } else {
        this.localFilters.without_genres.splice(index, 1);
      }
    },

    isKeywordExcluded(keywordId) {
      return (this.localFilters.without_keywords || []).some(keyword => String(keyword.id) === String(keywordId));
    },

    toggleKeyword(keyword) {
      if (!this.localFilters.without_keywords) {
        this.localFilters.without_keywords = [];
      }
      const index = this.localFilters.without_keywords.findIndex(item => String(item.id) === String(keyword.id));
      if (index === -1) {
        this.localFilters.without_keywords.push({ id: keyword.id, name: keyword.name });
      } else {
        this.localFilters.without_keywords.splice(index, 1);
      }
    },

    async searchKeywords() {
      if (this.keywordQuery.length < 2) return;
      try {
        const response = await jobsApi.searchKeywords(this.keywordQuery);
        this.keywordResults = response.status === 'success' ? response.keywords : [];
      } catch (error) {
        console.error('Failed to search TMDb keywords:', error);
        this.keywordResults = [];
      }
    }
  }
};
</script>
