<template>
  <div class="settings-content-filters">
    <div class="section-header">
      <h2>Content Filters</h2>
      <p>Configure content filtering and suggestion criteria</p>
    </div>

    <div class="settings-grid">
      <!-- TMDB Rating Filters -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-star"></i>
          TMDB Rating Filters
        </h3>

        <div class="form-row">
          <div class="form-group">
            <label for="tmdbThreshold">Minimum Rating</label>
            <input
              id="tmdbThreshold"
              v-model.number="localConfig.FILTER_TMDB_THRESHOLD"
              type="number"
              min="0"
              max="10"
              step="0.1"
              placeholder="6.0"
              class="form-control"
              :disabled="isLoading"
            />
            <small class="form-help">Minimum TMDB rating (0-10)</small>
          </div>

          <div class="form-group">
            <label for="tmdbMinVotes">Minimum Votes</label>
            <input
              id="tmdbMinVotes"
              v-model.number="localConfig.FILTER_TMDB_MIN_VOTES"
              type="number"
              min="0"
              placeholder="100"
              class="form-control"
              :disabled="isLoading"
            />
            <small class="form-help">Minimum number of votes</small>
          </div>
        </div>
      </div>

      <!-- Genre Exclusions -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-theater-masks"></i>
          Genre Exclusions
        </h3>

        <div class="form-group">
          <label for="genreExcludes">Exclude Genres</label>
          <div class="genre-selector">
            <div
              v-for="genre in availableGenres"
              :key="genre.id"
              class="genre-item"
            >
              <input
                :id="`genre-${genre.id}`"
                v-model="localConfig.FILTER_GENRES_EXCLUDE"
                :value="genre.id"
                type="checkbox"
                class="genre-checkbox"
                :disabled="isLoading"
              />
              <label :for="`genre-${genre.id}`" class="genre-label">
                {{ genre.name }}
              </label>
            </div>
          </div>
          <small class="form-help">
            Select genres to exclude from suggestions
          </small>
        </div>
      </div>

      <!-- Release Filters -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-calendar"></i>
          Release Filters
        </h3>

        <div class="form-group">
          <label for="releaseYear">Minimum Release Year</label>
          <input
            id="releaseYear"
            v-model.number="localConfig.FILTER_RELEASE_YEAR"
            type="number"
            min="1900"
            :max="currentYear"
            placeholder="2010"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">
            Only include content released in or after this year
          </small>
        </div>

        <div class="form-group">
          <label for="numSeasons">Maximum TV Seasons</label>
          <input
            id="numSeasons"
            v-model.number="localConfig.FILTER_NUM_SEASONS"
            type="number"
            min="1"
            max="50"
            placeholder="10"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">
            Maximum number of seasons for TV shows (leave empty for no limit)
          </small>
        </div>
      </div>

      <!-- Language & Rating -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-language"></i>
          Language & Rating
        </h3>

        <BaseDropdown
          v-model="localConfig.FILTER_LANGUAGE"
          :options="languageOptions"
          label="Preferred Language"
          help-text="Preferred language for content"
          :disabled="isLoading"
          id="filterLanguage"
        />

        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="localConfig.FILTER_INCLUDE_NO_RATING"
              type="checkbox"
              :disabled="isLoading"
            />
            <span class="checkbox-text">Include content without ratings</span>
          </label>
          <small class="form-help">
            Include content that doesn't have a TMDB rating
          </small>
        </div>
      </div>

      <!-- Streaming Services -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-tv"></i>
          Streaming Services
        </h3>

        <div class="form-group">
          <label for="streamingServices">Exclude Streaming Services</label>
          <div class="streaming-selector">
            <div
              v-for="service in availableStreamingServices"
              :key="service.id"
              class="streaming-item"
            >
              <input
                :id="`service-${service.id}`"
                v-model="localConfig.FILTER_STREAMING_SERVICES"
                :value="service.id"
                type="checkbox"
                class="streaming-checkbox"
                :disabled="isLoading"
              />
              <label :for="`service-${service.id}`" class="streaming-label">
                {{ service.name }}
              </label>
            </div>
          </div>
          <small class="form-help">
            Select streaming services to exclude from suggestions
          </small>
        </div>

        <BaseDropdown
          v-model="localConfig.FILTER_REGION_PROVIDER"
          :options="regionOptions"
          label="Region Provider"
          help-text="Region for streaming service availability"
          :disabled="isLoading"
          id="regionProvider"
        />
      </div>

      <!-- Request & Download Filters -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-filter"></i>
          Request & Download Filters
        </h3>

        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="localConfig.EXCLUDE_DOWNLOADED"
              type="checkbox"
              :disabled="isLoading"
            />
            <span class="checkbox-text">Exclude downloaded content</span>
          </label>
          <small class="form-help">
            Don't suggest content that is already downloaded
          </small>
        </div>

        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="localConfig.EXCLUDE_REQUESTED"
              type="checkbox"
              :disabled="isLoading"
            />
            <span class="checkbox-text">Exclude requested content</span>
          </label>
          <small class="form-help">
            Don't suggest content that is already requested
          </small>
        </div>

        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="localConfig.HONOR_JELLYSEER_DISCOVERY"
              type="checkbox"
              :disabled="isLoading"
            />
            <span class="checkbox-text">Honor Overseer/Jellyseer discovery settings</span>
          </label>
          <small class="form-help">
            Respect the discovery settings configured in Overseer/Jellyseer
          </small>
        </div>
      </div>
    </div>

    <!-- Save Button -->
    <div class="settings-actions">
      <button
        @click="saveSettings"
        class="btn btn-primary"
        :disabled="isLoading || !hasChanges"
      >
        <i class="fas fa-save"></i>
        {{ isLoading ? 'Saving...' : 'Save Changes' }}
      </button>

      <button
        @click="resetToDefaults"
        class="btn btn-outline"
        :disabled="isLoading"
      >
        <i class="fas fa-undo"></i>
        Reset to Defaults
      </button>
    </div>
  </div>
</template>

<script>
import BaseDropdown from '@/components/common/BaseDropdown.vue';

export default {
  name: 'SettingsContentFilters',
  components: {
    BaseDropdown
  },
  props: {
    config: {
      type: Object,
      required: true,
    },
    isLoading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['save-section'],
  data() {
    return {
      localConfig: {},
      originalConfig: {},
      availableGenres: [
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
        { id: 37, name: 'Western' },
      ],
      availableStreamingServices: [
        { id: 'netflix', name: 'Netflix' },
        { id: 'amazon', name: 'Amazon Prime' },
        { id: 'hulu', name: 'Hulu' },
        { id: 'disney', name: 'Disney+' },
        { id: 'hbo', name: 'HBO Max' },
        { id: 'apple', name: 'Apple TV+' },
        { id: 'paramount', name: 'Paramount+' },
        { id: 'peacock', name: 'Peacock' },
        { id: 'starz', name: 'STARZ' },
        { id: 'showtime', name: 'Showtime' },
      ],
      languageOptions: [
        { value: '', label: 'All Languages' },
        { value: 'en', label: 'English' },
        { value: 'es', label: 'Spanish' },
        { value: 'fr', label: 'French' },
        { value: 'de', label: 'German' },
        { value: 'it', label: 'Italian' },
        { value: 'ja', label: 'Japanese' },
        { value: 'ko', label: 'Korean' },
        { value: 'zh', label: 'Chinese' },
        { value: 'pt', label: 'Portuguese' },
        { value: 'ru', label: 'Russian' }
      ],
      regionOptions: [
        { value: '', label: 'All Regions' },
        { value: 'US', label: 'United States' },
        { value: 'GB', label: 'United Kingdom' },
        { value: 'CA', label: 'Canada' },
        { value: 'AU', label: 'Australia' },
        { value: 'DE', label: 'Germany' },
        { value: 'FR', label: 'France' },
        { value: 'IT', label: 'Italy' },
        { value: 'ES', label: 'Spain' },
        { value: 'JP', label: 'Japan' },
        { value: 'BR', label: 'Brazil' },
        { value: 'MX', label: 'Mexico' },
        { value: 'IN', label: 'India' }
      ]
    };
  },
  computed: {
    hasChanges() {
      return JSON.stringify(this.localConfig) !== JSON.stringify(this.originalConfig);
    },
    currentYear() {
      return new Date().getFullYear();
    },
  },
  watch: {
    config: {
      immediate: true,
      handler(newConfig) {
        this.localConfig = { ...newConfig };
        this.originalConfig = { ...newConfig };

        // Ensure arrays are properly initialized
        if (!Array.isArray(this.localConfig.FILTER_GENRES_EXCLUDE)) {
          this.localConfig.FILTER_GENRES_EXCLUDE = [];
        }
        if (!Array.isArray(this.localConfig.FILTER_STREAMING_SERVICES)) {
          this.localConfig.FILTER_STREAMING_SERVICES = [];
        }
        if (!Array.isArray(this.localConfig.SELECTED_USERS)) {
          this.localConfig.SELECTED_USERS = [];
        }
      },
    },
  },
  methods: {
    async saveSettings() {
      try {
        await this.$emit('save-section', {
          section: 'content_filters',
          data: {
            FILTER_TMDB_THRESHOLD: this.localConfig.FILTER_TMDB_THRESHOLD || null,
            FILTER_TMDB_MIN_VOTES: this.localConfig.FILTER_TMDB_MIN_VOTES || null,
            FILTER_GENRES_EXCLUDE: this.localConfig.FILTER_GENRES_EXCLUDE || [],
            FILTER_RELEASE_YEAR: this.localConfig.FILTER_RELEASE_YEAR || null,
            FILTER_NUM_SEASONS: this.localConfig.FILTER_NUM_SEASONS || null,
            FILTER_LANGUAGE: this.localConfig.FILTER_LANGUAGE || null,
            FILTER_INCLUDE_NO_RATING: this.localConfig.FILTER_INCLUDE_NO_RATING,
            FILTER_STREAMING_SERVICES: this.localConfig.FILTER_STREAMING_SERVICES || [],
            FILTER_REGION_PROVIDER: this.localConfig.FILTER_REGION_PROVIDER || null,
            EXCLUDE_DOWNLOADED: this.localConfig.EXCLUDE_DOWNLOADED,
            EXCLUDE_REQUESTED: this.localConfig.EXCLUDE_REQUESTED,
            HONOR_JELLYSEER_DISCOVERY: this.localConfig.HONOR_JELLYSEER_DISCOVERY,
          },
        });

        this.originalConfig = { ...this.localConfig };
      } catch (error) {
        console.error('Error saving content filter settings:', error);
      }
    },

    async resetToDefaults() {
      const defaults = {
        FILTER_TMDB_THRESHOLD: null,
        FILTER_TMDB_MIN_VOTES: null,
        FILTER_GENRES_EXCLUDE: [],
        FILTER_RELEASE_YEAR: null,
        FILTER_NUM_SEASONS: null,
        FILTER_LANGUAGE: null,
        FILTER_INCLUDE_NO_RATING: true,
        FILTER_STREAMING_SERVICES: [],
        FILTER_REGION_PROVIDER: null,
        EXCLUDE_DOWNLOADED: true,
        EXCLUDE_REQUESTED: true,
        HONOR_JELLYSEER_DISCOVERY: false,
      };

      if (confirm('Are you sure you want to reset all content filter settings to their defaults?')) {
        this.localConfig = { ...this.localConfig, ...defaults };
        await this.saveSettings();
      }
    },
  },
};
</script>

<style scoped>
.settings-content-filters {
  color: var(--color-text-primary);
}

.section-header {
  margin-bottom: 2rem;
}

.section-header h2 {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
  color: var(--color-text-primary);
}

.section-header p {
  color: var(--color-text-muted);
  font-size: 1rem;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 2rem;
  margin-bottom: 2rem;
}

.settings-group {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--border-radius-md);
  padding: 1.5rem;
}

.settings-group h3 {
  font-size: 1.2rem;
  margin-bottom: 1rem;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group label {
  vertical-align: middle;
  display: block;
  font-weight: 500;
  color: #e5e7eb;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
  margin-bottom: 0.5rem;
}

.checkbox-label input[type="checkbox"] {
  vertical-align: middle;
  width: 1.25rem;
  height: 1.25rem;
  accent-color: var(--color-primary);
}

.checkbox-text {
  vertical-align: middle;
  margin-left: 0.5rem;
  color: #e5e7eb;
  font-weight: 500;
}

.form-control {
  width: 100%;
  padding: 0.75rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-primary);
  font-size: 1rem;
  transition: var(--transition-base);
}

.form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  background: var(--color-bg-active);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: var(--color-text-muted);
  line-height: 1.4;
}

.genre-selector,
.streaming-selector {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 0.75rem;
  max-height: 200px;
  overflow-y: auto;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--border-radius-sm);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.genre-item,
.streaming-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.genre-checkbox,
.streaming-checkbox {
  vertical-align: middle;
  width: 1rem;
  height: 1rem;
  accent-color: var(--color-primary);
}

.genre-label,
.streaming-label {
  color: #e5e7eb;
  font-size: 0.875rem;
  cursor: pointer;
  user-select: none;
}

.genre-label:hover,
.streaming-label:hover {
  color: var(--color-primary);
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: var(--border-radius-sm);
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition-base);
  border: none;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  font-size: 0.875rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}


.btn-primary:hover:not(:disabled) {
  background: var(--button-primary-bg-hover);
}

.btn-outline {
  background: var(--color-bg-interactive);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-medium);
}

.btn-outline:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.5);
}

.settings-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  padding-top: 2rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

@media (max-width: 768px) {
  .settings-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .settings-group {
    padding: 1rem;
  }

  .form-row {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .genre-selector,
  .streaming-selector {
    grid-template-columns: 1fr;
    max-height: 300px;
  }

  .settings-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>