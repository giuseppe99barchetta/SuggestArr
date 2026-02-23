<template>
  <div class="job-filters">
    <!-- Rating Source Selector -->
    <div class="form-group">
      <label>Rating Source</label>
      <div class="rating-source-options">
        <label
          v-for="option in ratingSourceOptions"
          :key="option.value"
          class="rating-source-option"
          :class="{ active: localFilters.rating_source === option.value }"
        >
          <input
            type="radio"
            :value="option.value"
            v-model="localFilters.rating_source"
            class="rating-source-radio"
          />
          <div class="option-content">
            <span class="option-label">{{ option.label }}</span>
            <span class="option-desc">{{ option.description }}</span>
          </div>
        </label>
      </div>
    </div>

    <!-- TMDB Rating Filter (hidden when source is imdb-only) -->
    <div v-if="localFilters.rating_source !== 'imdb'" class="form-group">
      <label>{{ localFilters.rating_source === 'both' ? 'Minimum Rating (TMDB)' : 'Minimum Rating' }}: {{ localFilters.vote_average_gte || 0 }}</label>
      <input
        v-model.number="localFilters.vote_average_gte"
        type="range"
        min="0"
        max="10"
        step="0.5"
        class="form-range"
      />
      <div class="range-labels">
        <span>0</span>
        <span>5</span>
        <span>10</span>
      </div>
    </div>

    <!-- TMDB Vote Count Filter (hidden when source is imdb-only) -->
    <div v-if="localFilters.rating_source !== 'imdb'" class="form-group">
      <label for="voteCount">{{ localFilters.rating_source === 'both' ? 'Minimum Vote Count (TMDB)' : 'Minimum Vote Count' }}</label>
      <input
        id="voteCount"
        v-model.number="localFilters.vote_count_gte"
        type="number"
        min="0"
        step="100"
        placeholder="e.g., 1000"
        class="form-control"
      />
      <small class="form-help">Filter out content with too few votes</small>
    </div>

    <!-- IMDB Rating Filter (shown when IMDB is part of rating source) -->
    <div v-if="localFilters.rating_source !== 'tmdb'" class="form-group">
      <label>IMDB Minimum Rating: {{ (localFilters.imdb_rating_gte || 0).toFixed(1) }}</label>
      <input
        v-model.number="localFilters.imdb_rating_gte"
        type="range"
        min="0"
        max="10"
        step="0.1"
        class="form-range imdb-range"
      />
      <div class="range-labels">
        <span>0</span>
        <span>5</span>
        <span>10</span>
      </div>
      <small class="form-help">
        <i class="fas fa-star" style="color: #f5c518;"></i>
        Filter by IMDB community rating — requires OMDb API key configured in Services
      </small>
    </div>

    <!-- IMDB Vote Count Filter (shown when IMDB is part of rating source) -->
    <div v-if="localFilters.rating_source !== 'tmdb'" class="form-group">
      <label for="imdbVotes">IMDB Minimum Vote Count</label>
      <input
        id="imdbVotes"
        v-model.number="localFilters.imdb_min_votes"
        type="number"
        min="0"
        step="1"
        placeholder="e.g., 10000"
        class="form-control"
      />
      <small class="form-help">Filter out content with too few IMDB votes (more votes = more reliable rating)</small>
    </div>

    <!-- "Both must pass" notice -->
    <div v-if="localFilters.rating_source === 'both'" class="rating-both-notice">
      <i class="fas fa-info-circle"></i>
      Content must pass <strong>both</strong> TMDB and IMDB thresholds to be recommended.
    </div>

    <!-- Include No Rating Toggle -->
    <div class="form-group">
      <label class="toggle-item inline">
        <input
          v-model="localFilters.include_no_rating"
          type="checkbox"
        />
        <span class="toggle-label-modal">
          {{ localFilters.rating_source !== 'tmdb' ? 'Include content without IMDB rating' : 'Include content without rating' }}
        </span>
      </label>
      <small class="form-help">Also include content that doesn't have any rating data yet</small>
    </div>

    <!-- Minimum Seasons Filter (TV only) -->
    <div v-if="mediaType === 'tv'" class="form-group">
      <label for="minSeasons">Minimum Seasons: {{ localFilters.min_seasons || 1 }}</label>
      <input
        id="minSeasons"
        v-model.number="localFilters.min_seasons"
        type="range"
        min="1"
        max="10"
        step="1"
        class="form-range"
      />
      <small class="form-help">Only include TV shows with at least this many seasons</small>
    </div>

    <!-- Minimum Runtime Filter -->
    <div class="form-group">
      <label for="minRuntime">Minimum Runtime (minutes)</label>
      <input
        id="minRuntime"
        v-model.number="localFilters.min_runtime"
        type="number"
        min="0"
        step="1"
        placeholder="e.g., 60"
        class="form-control"
      />
      <small class="form-help">Exclude short content below this runtime — useful to filter out clips and shorts</small>
    </div>

    <!-- Release Date Filter -->
    <div class="form-group">
      <label>Release Date Range</label>
      <div class="date-range">
        <div class="date-field">
          <span class="date-label">From</span>
          <input v-model="releaseDateFrom" type="date" class="form-control" />
        </div>
        <div class="date-field">
          <span class="date-label">To</span>
          <input v-model="releaseDateTo" type="date" class="form-control" />
        </div>
      </div>
    </div>

    <!-- Language Filter -->
    <div class="form-group dropdown-wrapper">
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

    <!-- Genre Filters -->
    <div class="form-group">
      <label>Genres to Exclude</label>
      <div class="genre-grid" v-if="genres.length > 0">
        <button
          v-for="genre in genres"
          :key="genre.id"
          type="button"
          class="genre-btn"
          :class="{ active: isGenreExcluded(genre.id) }"
          @click="toggleGenreExclude(genre.id)"
        >
          {{ genre.name }}
        </button>
      </div>
      <p v-else class="loading-text">
        <i class="fas fa-spinner fa-spin"></i> Loading genres...
      </p>
    </div>

    <!-- Sort By -->
    <div class="form-group dropdown-wrapper">
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

export default {
  name: 'JobFilters',
  components: {
    BaseDropdown
  },
  props: {
    modelValue: {
      type: Object,
      default: () => ({})
    },
    mediaType: {
      type: String,
      default: 'movie'
    }
  },
  emits: ['update:modelValue'],
  data() {
    return {
      localFilters: { rating_source: 'tmdb', ...this.modelValue },
      genres: [],
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
          description: 'Use IMDB ratings via OMDb API. Requires an OMDb API key in Services.'
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
    await this.loadGenres();
  },
  methods: {
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
    }
  }
};
</script>

<style scoped>
.job-filters {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: 0.5rem;
}

.form-control {
  width: 100%;
  padding: 0.75rem 1rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-primary);
  font-size: 1rem;
  transition: var(--transition-base);
}

.form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--shadow-glow);
}

.dropdown-wrapper {
  position: relative;
  z-index: 100;
}

.dropdown-wrapper:first-of-type {
  z-index: 101;
}

/* Make dropdown menu appear above the trigger (upward) */
.dropdown-wrapper :deep(.dropdown-menu) {
  z-index: 9999;
  top: auto;
  bottom: calc(100% + 0.5rem);
}

/* Adjust animation for upward dropdown */
.dropdown-wrapper :deep(.dropdown-slide-enter-active) {
  animation: dropdown-appear-up 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.dropdown-wrapper :deep(.dropdown-slide-leave-active) {
  animation: dropdown-disappear-up 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes dropdown-appear-up {
  0% {
    opacity: 0;
    transform: translateY(12px) scale(0.95);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes dropdown-disappear-up {
  0% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateY(8px) scale(0.98);
  }
}

.form-help {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  margin-top: 0.5rem;
}

.form-range {
  width: 100%;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--color-border-light);
  border-radius: var(--radius-full);
  outline: none;
  margin-top: 0.5rem;
}

.form-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  background: var(--color-primary);
  border-radius: 50%;
  cursor: pointer;
  transition: var(--transition-fast);
}

.form-range::-webkit-slider-thumb:hover {
  transform: scale(1.1);
  box-shadow: var(--shadow-glow);
}

.form-range::-moz-range-thumb {
  width: 18px;
  height: 18px;
  background: var(--color-primary);
  border-radius: 50%;
  cursor: pointer;
  border: none;
}

.range-labels {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  margin-top: 0.5rem;
}

.date-range {
  display: flex;
  gap: 1rem;
}

.date-field {
  flex: 1;
}

.date-label {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  margin-bottom: 0.35rem;
}

input[type="date"] {
  color-scheme: dark;
}

.genre-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 1rem;
  background: var(--color-bg-overlay-light);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-light);
  max-height: 200px;
  overflow-y: auto;
}

.genre-btn {
  padding: 0.5rem 0.75rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: var(--transition-base);
}

.genre-btn:hover {
  border-color: var(--color-border-heavy);
  color: var(--color-text-primary);
}

.genre-btn.active {
  background: var(--color-error-alpha-10);
  border-color: var(--color-error);
  color: var(--color-error);
}

.loading-text {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
}

.toggle-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
}

.toggle-item.inline {
  padding: 0.5rem 0;
}

.toggle-item input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.toggle-label-modal {
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  flex-direction: row !important;
}

/* Rating source selector */
.rating-source-options {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.rating-source-option {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-base);
  background: rgba(255, 255, 255, 0.02);
}

.rating-source-option:hover {
  border-color: var(--color-primary);
  background: rgba(255, 255, 255, 0.04);
}

.rating-source-option.active {
  border-color: var(--color-primary);
  background: rgba(59, 130, 246, 0.08);
}

.rating-source-radio {
  margin-top: 0.2rem;
  accent-color: var(--color-primary);
  flex-shrink: 0;
}

.option-content {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.option-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.option-desc {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  line-height: 1.3;
}

.imdb-range::-webkit-slider-thumb {
  background: #f5c518;
}
.imdb-range::-webkit-slider-thumb:hover {
  box-shadow: 0 0 0 3px rgba(245, 197, 24, 0.25);
}
.imdb-range::-moz-range-thumb {
  background: #f5c518;
}

.rating-both-notice {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 0.875rem;
  background: rgba(245, 197, 24, 0.08);
  border: 1px solid rgba(245, 197, 24, 0.25);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
.rating-both-notice i {
  color: #f5c518;
  flex-shrink: 0;
}

@media (max-width: 480px) {
  .date-range {
    flex-direction: column;
  }
}
</style>
