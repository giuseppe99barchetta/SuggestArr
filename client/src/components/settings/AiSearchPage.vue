<template>
  <div class="ai-search-page">
    <!-- Header -->
    <div class="section-header">
      <h2><i class="fas fa-magic"></i> AI Search</h2>
      <p>Describe what you want to watch and the AI will find it for you, personalised to your viewing history.</p>
    </div>

    <!-- LLM Not Configured Warning -->
    <div v-if="!llmAvailable" class="warning-banner">
      <i class="fas fa-exclamation-triangle"></i>
      <div class="warning-content">
        <strong>LLM not configured</strong>
        <span>Set <code>OPENAI_API_KEY</code> (and optionally <code>OPENAI_BASE_URL</code> for local models) in the <strong>Advanced</strong> tab to enable AI Search.</span>
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
.ai-search-page {
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.section-header h2 {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-xs) 0;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.section-header p {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
  margin: 0;
}

/* Warning banner */
.warning-banner {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  color: var(--color-warning);
  font-size: var(--font-size-sm);
}

.warning-banner i { flex-shrink: 0; margin-top: 2px; }
.warning-content { display: flex; flex-direction: column; gap: 4px; }
.warning-content strong { color: var(--color-warning); }
.warning-content span { color: var(--color-text-secondary); }
.warning-content code {
  background: rgba(255,255,255,0.1);
  border-radius: var(--radius-sm);
  padding: 1px 5px;
  font-family: var(--font-family-mono);
  font-size: 0.8em;
}

/* Error banner */
.error-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  color: var(--color-error-light);
  font-size: var(--font-size-sm);
}

/* Search form */
.search-form {
  background: var(--color-bg-content);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.search-form.disabled {
  opacity: 0.5;
  pointer-events: none;
}

.search-input-group { position: relative; }

.search-textarea {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--radius-md);
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  padding: var(--spacing-md);
  resize: vertical;
  box-sizing: border-box;
  font-family: var(--font-family-base);
  transition: border-color var(--transition-base);
}

.search-textarea:focus {
  outline: none;
  border-color: var(--color-info);
}

.search-textarea::placeholder { color: var(--color-text-muted); }

.search-hint {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  text-align: right;
  margin-top: 4px;
}

.search-controls {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.media-type-selector {
  display: flex;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.beta-warning {
  background: rgba(255, 152, 0, 0.1);
  border: 1px solid rgba(255, 152, 0, 0.4);
  padding: 12px;
  border-radius: 10px;
  margin-bottom: 20px;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-full);
  cursor: pointer;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
  transition: all var(--transition-base);
  user-select: none;
}

.radio-label input[type="radio"] { display: none; }

.radio-label:hover {
  border-color: var(--color-info);
  color: var(--color-info);
}

.radio-label.active {
  border-color: var(--color-info);
  background: rgba(6, 182, 212, 0.12);
  color: var(--color-info);
}

.search-btn { margin-left: auto; }

/* Advanced options */
.advanced-options {
  border-top: 1px solid var(--color-border-light);
  padding-top: var(--spacing-sm);
}

.advanced-toggle {
  background: none;
  border: none;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  transition: color var(--transition-base);
}

.advanced-toggle:hover { color: var(--color-text-secondary); }

.advanced-panel {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-sm);
}

.toggle-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  cursor: pointer;
  padding: var(--spacing-xs) 0;
}

.toggle-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.toggle-label i {
  display: inline;
  margin-right: 6px;
  color: var(--color-text-muted);
}

.toggle-hint {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

.toggle-switch {
  flex-shrink: 0;
  width: 40px;
  height: 22px;
  background: var(--color-border-medium);
  border-radius: var(--radius-full);
  position: relative;
  cursor: pointer;
  transition: background var(--transition-base);
}

.toggle-switch.on { background: var(--color-info); }

.toggle-knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  transition: transform var(--transition-base);
}

.toggle-switch.on .toggle-knob { transform: translateX(18px); }

.number-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  padding: var(--spacing-xs) 0;
}

.number-input {
  width: 64px;
  background: rgba(0,0,0,0.3);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--radius-sm);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  padding: 4px 8px;
  text-align: center;
}

.number-input:focus {
  outline: none;
  border-color: var(--color-info);
}

/* Recent searches */
.recent-searches {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.recent-label {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  flex-shrink: 0;
  padding-top: 4px;
  white-space: nowrap;
}

.recent-chips {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
  flex: 1;
}

.recent-chip {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-full);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  padding: 3px 10px;
  cursor: pointer;
  transition: all var(--transition-base);
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-chip:hover:not(:disabled) {
  border-color: var(--color-info);
  color: var(--color-info);
  background: rgba(6, 182, 212, 0.08);
}

.recent-chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.recent-clear {
  background: none;
  border: none;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: var(--font-size-xs);
  padding: 4px 6px;
  flex-shrink: 0;
  border-radius: var(--radius-sm);
  transition: color var(--transition-base);
}

.recent-clear:hover {
  color: var(--color-error-light);
}

/* Interpretation bar */
.interpretation-bar {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  background: rgba(6, 182, 212, 0.06);
  border: 1px solid rgba(6, 182, 212, 0.2);
  border-radius: var(--radius-md);
  padding: var(--spacing-sm) var(--spacing-md);
}

.interpretation-bar i { color: var(--color-info); }
.interp-label { color: var(--color-text-muted); font-size: var(--font-size-xs); }

.interp-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(6, 182, 212, 0.12);
  border: 1px solid rgba(6, 182, 212, 0.25);
  border-radius: var(--radius-full);
  padding: 2px 10px;
  color: var(--color-info-light);
  font-size: var(--font-size-xs);
}

.interp-tag-rating {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.3);
  color: var(--color-warning);
}

.interp-tag-rating i {
  color: var(--color-warning);
}

/* Results section */
.results-header h3 {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-secondary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
}

/* Result card */
.result-card {
  background: var(--color-bg-content);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: border-color var(--transition-base), transform var(--transition-base);
}

.result-card:hover {
  border-color: var(--color-border-heavy);
  transform: translateY(-2px);
}

/* Poster */
.card-poster {
  position: relative;
  aspect-ratio: 2/3;
  overflow: hidden;
  background: rgba(0,0,0,0.4);
  cursor: pointer;
}

.card-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.2s ease;
}

.card-poster:hover img { transform: scale(1.04); }

.poster-expand-hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0);
  color: rgba(255,255,255,0);
  font-size: 1.4rem;
  transition: background 0.2s, color 0.2s;
  pointer-events: none;
}

.card-poster:hover .poster-expand-hint {
  background: rgba(0,0,0,0.35);
  color: rgba(255,255,255,0.85);
}

.poster-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: var(--color-text-muted);
  font-size: 2rem;
}

.source-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  border-radius: var(--radius-full);
  padding: 2px 8px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.badge-ai {
  background: rgba(6, 182, 212, 0.85);
  color: #fff;
}

.badge-discover {
  background: rgba(100, 116, 139, 0.8);
  color: #fff;
}

/* Card info */
.card-info {
  padding: var(--spacing-sm) var(--spacing-md) var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.card-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  line-height: var(--line-height-tight);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-title-clickable {
  cursor: pointer;
  transition: color var(--transition-base);
}

.card-title-clickable:hover { color: var(--color-info-light); }

.card-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.meta-year, .meta-type {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

.meta-rating {
  font-size: var(--font-size-xs);
  color: var(--color-warning);
  display: flex;
  align-items: center;
  gap: 3px;
}

.meta-votes {
  color: var(--color-text-muted);
  font-size: 0.9em;
}

.card-rationale {
  font-size: var(--font-size-xs);
  color: var(--color-info-light);
  font-style: italic;
  line-height: var(--line-height-relaxed);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-rationale i {
  font-size: 0.65em;
  margin-right: 3px;
  opacity: 0.7;
}

.card-overview {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  line-height: var(--line-height-normal);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.request-btn {
  margin-top: auto;
  width: 100%;
  font-size: var(--font-size-xs);
  padding: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-2xl);
  color: var(--color-text-muted);
  text-align: center;
}

.empty-state i {
  font-size: 2.5rem;
  color: var(--color-text-disabled);
}

.empty-state h3 {
  font-size: var(--font-size-lg);
  color: var(--color-text-secondary);
  margin: 0;
}

.empty-state p {
  font-size: var(--font-size-sm);
  margin: 0;
}

/* ── Modal ──────────────────────────────────────────────────── */
.ai-modal-overlay {
  position: fixed;
  inset: 0;
  background-color: var(--color-bg-overlay-heavy, rgba(0,0,0,0.8));
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 1rem;
  overflow-y: auto;
}

.ai-modal-content {
  position: relative;
  background-color: rgba(0, 0, 0, 0.82);
  backdrop-filter: blur(15px);
  border-radius: var(--border-radius-xl, 16px);
  border: 1px solid var(--color-border-light);
  max-width: 1100px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  margin: auto;
}

.ai-modal-close {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid var(--color-border-light);
  border-radius: 50%;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: var(--transition-base, all 0.2s);
  z-index: 10;
}

.ai-modal-close:hover {
  background-color: var(--color-danger, #ef4444);
  color: white;
  border-color: var(--color-danger, #ef4444);
  transform: rotate(90deg);
}

.ai-modal-layout {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  padding: 2rem;
}

@media (min-width: 768px) {
  .ai-modal-layout {
    flex-direction: row;
    gap: 3rem;
    padding: 3rem;
  }
}

@media (min-width: 1024px) {
  .ai-modal-layout {
    gap: 3.5rem;
    padding: 3.5rem 4rem;
  }
}

.ai-modal-poster-section {
  flex-shrink: 0;
  width: 100%;
}

@media (min-width: 768px) {
  .ai-modal-poster-section { width: 260px; }
}

.ai-modal-poster {
  width: 100%;
  height: auto;
  border-radius: var(--border-radius-lg, 12px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  display: block;
}

.ai-modal-poster-placeholder {
  width: 100%;
  aspect-ratio: 2/3;
  background-color: var(--color-bg-primary, #111);
  border-radius: var(--border-radius-lg, 12px);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
  font-size: 3rem;
}

.ai-modal-details {
  flex: 1;
  min-width: 0;
}

.ai-modal-title {
  font-size: 2rem;
  font-weight: bold;
  color: var(--color-text-primary);
  margin: 0 0 1rem 0;
  line-height: 1.2;
  word-wrap: break-word;
  padding-right: 2rem;
}

/* Badges */
.ai-badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.ai-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
}

.ai-badge-media {
  background-color: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.ai-badge-rating {
  background-color: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.ai-badge-votes {
  color: rgba(52, 211, 153, 0.6);
  font-weight: 400;
}

.ai-badge-date {
  background-color: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.ai-badge-lang {
  background-color: rgba(168, 85, 247, 0.2);
  color: #c084fc;
  border: 1px solid rgba(168, 85, 247, 0.3);
}

.ai-modal-sep {
  border-top: 1px solid var(--color-border-light);
  margin: 1rem 0;
}

.ai-modal-section {
  margin-bottom: 1.5rem;
}

.ai-modal-section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 0.75rem;
}

.ai-modal-text {
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin: 0;
  font-size: 0.95rem;
}

.ai-modal-rationale-text {
  font-style: italic;
  border-left: 3px solid var(--color-info);
  padding-left: 1rem;
  color: var(--color-text-secondary);
}

.ai-modal-req-btn {
  padding: 10px 24px;
  font-size: var(--font-size-sm);
}

/* Modal transition */
.modal-fade-enter-active, .modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-from, .modal-fade-leave-to {
  opacity: 0;
}

/* Reuse global btn classes */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xs);
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  border: 1px solid transparent;
  transition: all var(--transition-base);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-info);
  color: #fff;
  border-color: var(--color-info);
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-info-hover);
}

.btn-outline {
  background: transparent;
  color: var(--color-text-secondary);
  border-color: var(--color-border-medium);
}

.btn-outline:hover:not(:disabled) {
  border-color: var(--color-border-heavy);
  color: var(--color-text-primary);
}

.btn-success {
  background: rgba(16, 185, 129, 0.15);
  color: var(--color-success);
  border-color: rgba(16, 185, 129, 0.3);
  cursor: default;
}

@media (max-width: 640px) {
  .results-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .search-controls {
    flex-direction: column;
    align-items: stretch;
  }

  .search-btn {
    margin-left: 0;
  }
}
</style>
