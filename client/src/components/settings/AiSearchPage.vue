<template>
  <div class="ai-search-page">
    <!-- Header -->
    <div class="section-header">
      <h2>AI Search</h2>
      <p>Describe what you want to watch and the AI will find it for you, personalised to your viewing history.</p>
    </div>

    <!-- LLM Not Configured Warning -->
    <div v-if="!llmAvailable" class="warning-banner">
      <i class="fas fa-exclamation-triangle"></i>
      <div class="warning-content">
        <strong>LLM not configured</strong>
        <span>Complete the configuration for the AI Integration in the <strong>Advanced</strong> tab, under <strong>Experimental Features</strong> card to enable AI Search.</span>
      </div>
    </div>

    <!-- Beta Warning -->
    <div class="beta-warning">
      <i class="fas fa-flask"></i>
      <span>
        AI Search is currently in BETA. Features and results may change.
      </span>
    </div>

    <!-- Search Form -->
    <div class="search-form" :class="{ disabled: !llmAvailable }">
      <div class="search-input-group">
        <textarea
          v-model="query"
          :disabled="!llmAvailable || isSearching"
          class="search-textarea"
          placeholder="Describe what you want to watch... e.g. 'A psychological thriller from the 90s with a twist ending' or 'Feel-good anime with strong friendships'"
          rows="3"
          @keydown.ctrl.enter="runSearch"
        ></textarea>
        <div class="search-hint">Ctrl + Enter to search</div>
      </div>

      <div class="search-controls">
        <div class="media-type-selector">
          <label class="radio-label" :class="{ active: mediaType === 'movie' }">
            <input type="radio" v-model="mediaType" value="movie" :disabled="isSearching" />
            <i class="fas fa-film"></i> Movies
          </label>
          <label class="radio-label" :class="{ active: mediaType === 'tv' }">
            <input type="radio" v-model="mediaType" value="tv" :disabled="isSearching" />
            <i class="fas fa-tv"></i> TV Shows
          </label>
          <label class="radio-label" :class="{ active: mediaType === 'both' }">
            <input type="radio" v-model="mediaType" value="both" :disabled="isSearching" />
            <i class="fas fa-layer-group"></i> Both
          </label>
        </div>

        <button
          @click="runSearch"
          :disabled="!llmAvailable || isSearching || !query.trim()"
          class="btn btn-primary search-btn"
        >
          <i :class="isSearching ? 'fas fa-spinner fa-spin' : 'fas fa-search'"></i>
          {{ isSearching ? 'Searching...' : 'Search' }}
        </button>
      </div>

      <!-- Advanced Options -->
      <div class="advanced-options">
        <button class="advanced-toggle" @click="showAdvanced = !showAdvanced" type="button">
          <i :class="showAdvanced ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
          Advanced Options
        </button>
        <div v-if="showAdvanced" class="advanced-panel">
          <label class="toggle-option">
            <span class="toggle-label">
              <i class="fas fa-history"></i>
              Use viewing history
              <span class="toggle-hint">Let the AI personalise results based on what you've already watched</span>
            </span>
            <div class="toggle-switch" :class="{ on: useHistory }" @click="useHistory = !useHistory">
              <div class="toggle-knob"></div>
            </div>
          </label>
          <label class="toggle-option">
            <span class="toggle-label">
              <i class="fas fa-eye-slash"></i>
              Exclude already watched
              <span class="toggle-hint">Hide titles you've already seen from results</span>
            </span>
            <div class="toggle-switch" :class="{ on: excludeWatched }" @click="excludeWatched = !excludeWatched">
              <div class="toggle-knob"></div>
            </div>
          </label>
          <div class="number-option">
            <span class="toggle-label">
              <i class="fas fa-list-ol"></i>
              Max results
              <span class="toggle-hint">Number of results to return (4–24)</span>
            </span>
            <input
              v-model.number="maxResults"
              type="number"
              min="4"
              max="24"
              step="4"
              class="number-input"
              :disabled="isSearching"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Recent Searches -->
    <div v-if="recentSearches.length > 0" class="recent-searches">
      <span class="recent-label"><i class="fas fa-history"></i> Recent:</span>
      <div class="recent-chips">
        <button
          v-for="(search, i) in recentSearches"
          :key="i"
          @click="rerunSearch(search)"
          class="recent-chip"
          :disabled="isSearching"
          :title="search"
        >{{ search }}</button>
      </div>
      <button class="recent-clear" @click="clearHistory" title="Clear search history">
        <i class="fas fa-times"></i>
      </button>
    </div>

    <!-- Query Interpretation Badge -->
    <div v-if="queryInterpretation && hasInterpretation" class="interpretation-bar">
      <i class="fas fa-brain"></i>
      <span class="interp-label">AI interpreted as:</span>
      <span v-if="interpGenres" class="interp-tag">
        <i class="fas fa-film"></i> {{ interpGenres }}
      </span>
      <span v-if="interpYears" class="interp-tag">
        <i class="fas fa-calendar"></i> {{ interpYears }}
      </span>
      <span v-if="interpLang" class="interp-tag">
        <i class="fas fa-globe"></i> {{ interpLang.toUpperCase() }}
      </span>
      <span v-if="interpMinRating" class="interp-tag interp-tag-rating">
        <i class="fas fa-star"></i> min {{ interpMinRating }}
      </span>
    </div>

    <!-- Error State -->
    <div v-if="errorMessage" class="error-banner">
      <i class="fas fa-exclamation-circle"></i>
      <span>{{ errorMessage }}</span>
    </div>

    <!-- Results Grid -->
    <div v-if="results.length > 0" class="results-section">
      <div class="results-header">
        <h3>
          <i class="fas fa-list"></i>
          {{ results.length }} result{{ results.length !== 1 ? 's' : '' }} found
        </h3>
      </div>

      <div class="results-grid">
        <div
          v-for="item in results"
          :key="item.id + '-' + item.media_type"
          class="result-card"
          :class="{ 'ai-pick': item.source === 'ai_suggestion' }"
        >
          <!-- Poster -->
          <div class="card-poster" @click="openModal(item)" title="Click to expand">
            <img
              v-if="item.poster_path"
              :src="item.poster_path"
              :alt="item.title"
              loading="lazy"
            />
            <div v-else class="poster-placeholder">
              <i :class="item.media_type === 'tv' ? 'fas fa-tv' : 'fas fa-film'"></i>
            </div>
            <!-- Expand hint -->
            <div class="poster-expand-hint"><i class="fas fa-expand-alt"></i></div>
          </div>

          <!-- Info -->
          <div class="card-info">
            <div class="card-title card-title-clickable" @click="openModal(item)">{{ item.title }}</div>
            <div class="card-meta">
              <span v-if="releaseYear(item)" class="meta-year">{{ releaseYear(item) }}</span>
              <span v-if="item.rating" class="meta-rating">
                <i class="fas fa-star"></i> {{ Number(item.rating).toFixed(1) }}
                <span v-if="item.votes" class="meta-votes">({{ formatVotes(item.votes) }})</span>
              </span>
              <span class="meta-type">{{ item.media_type === 'tv' ? 'TV' : 'Movie' }}</span>
            </div>

            <!-- AI Rationale (truncated on card) -->
            <div v-if="item.rationale" class="card-rationale">
              <i class="fas fa-quote-left"></i>
              {{ item.rationale }}
            </div>

            <!-- Request Button -->
            <button
              @click="requestItem(item)"
              :disabled="requestedIds.has(item.id + '-' + item.media_type) || requestingIds.has(item.id + '-' + item.media_type)"
              class="btn request-btn"
              :class="requestButtonClass(item)"
            >
              <i :class="requestButtonIcon(item)"></i>
              {{ requestButtonLabel(item) }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State after search -->
    <div v-else-if="hasSearched && !isSearching" class="empty-state">
      <i class="fas fa-search"></i>
      <h3>No results found</h3>
      <p>Try adjusting your description or check your content filters in the General settings.</p>
    </div>

    <!-- Item Detail Modal -->
    <teleport to="body">
      <transition name="modal-fade">
        <div v-if="selectedItem" class="ai-modal-overlay" @click.self="closeModal">
          <div class="ai-modal-content" role="dialog" aria-modal="true">
            <!-- Close button -->
            <button class="ai-modal-close" @click="closeModal" aria-label="Close">
              <i class="fas fa-times"></i>
            </button>

            <div class="ai-modal-layout">
              <!-- Left: Poster -->
              <div class="ai-modal-poster-section">
                <img
                  v-if="selectedItem.poster_path"
                  :src="selectedItem.poster_path"
                  :alt="selectedItem.title"
                  class="ai-modal-poster"
                />
                <div v-else class="ai-modal-poster-placeholder">
                  <i :class="selectedItem.media_type === 'tv' ? 'fas fa-tv' : 'fas fa-film'"></i>
                </div>
              </div>

              <!-- Right: Details -->
              <div class="ai-modal-details">
                <h2 class="ai-modal-title">{{ selectedItem.title }}</h2>

                <!-- Badges -->
                <div class="ai-badge-row">
                  <span class="ai-badge ai-badge-media">
                    <i :class="selectedItem.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
                    {{ selectedItem.media_type === 'tv' ? 'TV SHOW' : 'MOVIE' }}
                  </span>
                  <span v-if="selectedItem.rating" class="ai-badge ai-badge-rating">
                    <i class="fas fa-star"></i>
                    {{ Number(selectedItem.rating).toFixed(1) }}
                    <span v-if="selectedItem.votes" class="ai-badge-votes">· {{ formatVotes(selectedItem.votes) }}</span>
                  </span>
                  <span v-if="releaseYear(selectedItem)" class="ai-badge ai-badge-date">
                    <i class="fas fa-calendar"></i>
                    {{ releaseYear(selectedItem) }}
                  </span>
                  <span v-if="selectedItem.original_language" class="ai-badge ai-badge-lang">
                    <i class="fas fa-globe"></i>
                    {{ selectedItem.original_language.toUpperCase() }}
                  </span>
                </div>

                <div class="ai-modal-sep"></div>

                <!-- AI Rationale -->
                <div v-if="selectedItem.rationale" class="ai-modal-section">
                  <h3 class="ai-modal-section-title" style="color: var(--color-info)">
                    <i class="fas fa-robot"></i> Why the AI picked this
                  </h3>
                  <p class="ai-modal-text ai-modal-rationale-text">{{ selectedItem.rationale }}</p>
                </div>

                <!-- Overview -->
                <div class="ai-modal-section">
                  <h3 class="ai-modal-section-title">
                    <i class="fas fa-align-left"></i> Overview
                  </h3>
                  <p class="ai-modal-text">{{ selectedItem.overview || 'No overview available.' }}</p>
                </div>

                <!-- Request button -->
                <button
                  @click="requestItem(selectedItem)"
                  :disabled="requestedIds.has(selectedItem.id + '-' + selectedItem.media_type) || requestingIds.has(selectedItem.id + '-' + selectedItem.media_type)"
                  class="btn ai-modal-req-btn"
                  :class="requestButtonClass(selectedItem)"
                >
                  <i :class="requestButtonIcon(selectedItem)"></i>
                  {{ requestButtonLabel(selectedItem) }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </transition>
    </teleport>
  </div>
</template>

<script>
import { aiSearch, aiSearchRequest, aiSearchStatus } from '@/api/api.js';
import '@/assets/styles/aiSearchPage.css';

export default {
  name: 'AiSearchPage',

  data() {
    return {
      query: '',
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
      // Advanced options
      showAdvanced: false,
      useHistory: true,
      excludeWatched: true,
      maxResults: 12,
      // Recent search history (persisted in localStorage)
      recentSearches: JSON.parse(localStorage.getItem('suggestarr_ai_search_history') || '[]'),
    };
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
        const res = await aiSearch(this.query.trim(), this.mediaType, [], this.maxResults, this.useHistory, this.excludeWatched);
        const data = res.data;

        if (data.status === 'error') {
          this.errorMessage = data.message || 'Search failed.';
          return;
        }

        this.results = data.results || [];
        this.queryInterpretation = data.query_interpretation || null;
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
          alert(res.data.message || 'Request failed.');
        }
      } catch (err) {
        const msg = err.response?.data?.message || 'Request failed.';
        alert(msg);
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

    openModal(item) {
      this.selectedItem = item;
      document.body.style.overflow = 'hidden';
    },

    closeModal() {
      this.selectedItem = null;
      document.body.style.overflow = '';
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

    requestButtonClass(item) {
      const key = item.id + '-' + item.media_type;
      if (this.requestedIds.has(key)) return 'btn-success';
      if (this.requestingIds.has(key)) return 'btn-outline';
      return 'btn-primary';
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
      if (this.requestingIds.has(key)) return 'Requesting...';
      return 'Request';
    },
  },

  mounted() {
    this.checkLlmStatus();
    this._onKeydown = (e) => { if (e.key === 'Escape') this.closeModal(); };
    window.addEventListener('keydown', this._onKeydown);
  },

  unmounted() {
    window.removeEventListener('keydown', this._onKeydown);
    document.body.style.overflow = '';
  },
};
</script>

<style scoped>

.section-header h2 {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
  color: var(--color-text-primary);
}

.section-header p {
  color: var(--color-text-muted);
  font-size: 1rem;
}
</style>