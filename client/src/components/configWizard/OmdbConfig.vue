<template>
  <div class="config-section">
    <h3 class="section-title">IMDB Rating Integration</h3>
    <p class="section-description">
      Optionally configure IMDB-based rating filtering using the
      <a href="https://www.omdbapi.com/" target="_blank" rel="noopener noreferrer" class="link">OMDb API</a>
      (free key at <a href="https://www.omdbapi.com/apikey.aspx" target="_blank" rel="noopener noreferrer" class="link">omdbapi.com</a>).
      This lets you filter recommendations by their IMDB rating instead of, or in addition to, TMDB ratings.
      This step is optional — you can skip it and configure it later from the dashboard.
    </p>

    <!-- Rating Source Card -->
    <div class="settings-card">
      <h4 class="card-title">Rating Source</h4>
      <p class="form-help mb-3">
        <i class="fas fa-info-circle"></i>
        Choose which rating source to use when filtering recommendations.
      </p>

      <div class="rating-source-options">
        <label
          v-for="option in ratingSourceOptions"
          :key="option.value"
          class="rating-source-option"
          :class="{ active: localRatingSource === option.value }"
        >
          <input
            type="radio"
            :value="option.value"
            v-model="localRatingSource"
            @change="handleRatingSourceChange(option.value)"
            class="rating-source-radio"
          />
          <div class="option-content">
            <span class="option-label">{{ option.label }}</span>
            <span class="option-desc">{{ option.description }}</span>
          </div>
        </label>
      </div>
    </div>

    <!-- OMDb API Key Card (shown when IMDB source is selected) -->
    <div class="settings-card" v-if="localRatingSource !== 'tmdb'">
      <h4 class="card-title">OMDb API Configuration</h4>

      <div class="form-group">
        <label for="OMDB_API_KEY" class="form-label">OMDb API Key</label>
        <div class="input-group">
          <input
            type="text"
            :value="config.OMDB_API_KEY"
            @input="handleApiKeyInput"
            @keyup.enter="testOmdbApi"
            :disabled="testState.isTesting"
            class="form-input"
            id="OMDB_API_KEY"
            placeholder="Enter your OMDb API Key"
          />
          <button
            type="button"
            @click="testOmdbApi"
            :disabled="testState.isTesting || !config.OMDB_API_KEY"
            :class="[
              'btn btn-test',
              {
                'btn-success': testState.status === 'success',
                'btn-danger': testState.status === 'fail',
                'btn-primary': testState.status === null && config.OMDB_API_KEY,
                'btn-disabled': !config.OMDB_API_KEY
              }
            ]"
          >
            <span v-if="testState.isTesting" class="btn-content">
              <i class="fas fa-spinner fa-spin"></i>
              <span class="hidden btn-text">Testing</span>
            </span>
            <span v-else-if="testState.status === 'success'" class="btn-content">
              <i class="fas fa-check"></i>
              <span class="hidden btn-text">Valid</span>
            </span>
            <span v-else-if="testState.status === 'fail'" class="btn-content">
              <i class="fas fa-times"></i>
              <span class="hidden btn-text">Failed</span>
            </span>
            <span v-else class="btn-content">
              <i class="fas fa-play"></i>
              <span class="hidden btn-text">Test</span>
            </span>
          </button>
        </div>
        <small class="form-help">
          Free tier: 1,000 requests/day. Get your key at
          <a href="https://www.omdbapi.com/apikey.aspx" target="_blank" rel="noopener noreferrer" class="link">omdbapi.com</a>
        </small>
      </div>

      <div v-if="testState.status === 'success'" class="alert alert-success" role="alert">
        <i class="fas fa-check-circle"></i>
        <span>OMDb API Key validated successfully!</span>
      </div>
      <div v-if="testState.status === 'fail'" class="alert alert-danger" role="alert">
        <i class="fas fa-exclamation-circle"></i>
        <span>Failed to validate OMDb API Key. Please check your key and try again.</span>
      </div>
    </div>

    <!-- Navigation Buttons -->
    <div class="flex justify-between mt-8 gap-4">
      <button @click="$emit('previous-step')"
        class="btn-secondary w-full flex items-center justify-center gap-2 py-4 px-8">
        <i class="fas fa-arrow-left"></i>
        Back
      </button>

      <button @click="$emit('skip-step')"
        class="btn-skip w-full flex items-center justify-center gap-2 py-4 px-8">
        <i class="fas fa-forward"></i>
        Skip
      </button>

      <button @click="submit" :disabled="!canProceed"
        class="btn-primary w-full flex items-center justify-center gap-2 py-4 px-8"
        :class="{ 'opacity-50 cursor-not-allowed': !canProceed }">
        Next Step
        <i class="fas fa-arrow-right"></i>
      </button>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  props: ['config'],
  data() {
    return {
      localRatingSource: this.config.FILTER_RATING_SOURCE || 'tmdb',
      testState: {
        status: null,
        isTesting: false
      },
      ratingSourceOptions: [
        {
          value: 'tmdb',
          label: 'TMDB Only',
          description: 'Use TMDB ratings (current default). No OMDb API key required.'
        },
        {
          value: 'imdb',
          label: 'IMDB Only',
          description: 'Use IMDB ratings via OMDb API. Requires an OMDb API key.'
        },
        {
          value: 'both',
          label: 'Both (stricter)',
          description: 'Content must pass both TMDB and IMDB thresholds. Requires an OMDb API key.'
        }
      ]
    };
  },
  computed: {
    canProceed() {
      if (this.localRatingSource === 'tmdb') return true;
      return this.testState.status === 'success';
    }
  },
  methods: {
    handleRatingSourceChange(value) {
      this.$emit('update-config', 'FILTER_RATING_SOURCE', value);
      this.testState.status = null;
    },
    handleApiKeyInput(event) {
      const value = event.target.value;
      this.$emit('update-config', 'OMDB_API_KEY', value);
      this.testState.status = null;
    },
    async testOmdbApi() {
      if (!this.config.OMDB_API_KEY) return;
      this.testState.isTesting = true;
      this.testState.status = null;
      try {
        await axios.post('/api/omdb/test', { api_key: this.config.OMDB_API_KEY });
        this.testState.status = 'success';
      } catch {
        this.testState.status = 'fail';
      } finally {
        this.testState.isTesting = false;
      }
    },
    submit() {
      if (this.canProceed) {
        this.$emit('next-step');
      }
    }
  }
};
</script>

<style scoped>
.config-section {
  display: flex;
  flex-direction: column;
}

.section-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 0.5rem;
}

.section-description {
  color: var(--color-text-muted);
  font-size: 0.9rem;
  line-height: 1.5;
  margin-bottom: 1.5rem;
}

.link {
  color: var(--color-primary);
  text-decoration: none;
  border-bottom: 1px dotted var(--color-primary);
  transition: all 0.2s ease;
}

.link:hover {
  color: var(--color-primary-hover);
  border-bottom-style: solid;
}

/* Rating source selector */
.rating-source-options {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.rating-source-option {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
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
  gap: 0.15rem;
}

.option-label {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-primary);
}

.option-desc {
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.mb-3 {
  margin-bottom: 0.75rem;
}

/* Form elements */
.form-label {
  display: block;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 0.5rem;
}

.input-group {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.form-input {
  flex: 1;
  min-width: 200px;
  min-height: 40px;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--border-radius-sm);
  padding: 0 1rem;
  color: var(--color-text-primary);
  font-size: 0.9rem;
  transition: var(--transition-base);
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
}

.form-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-help {
  display: block;
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  margin-top: 0.35rem;
  line-height: 1.4;
}

/* Test button */
.btn-test {
  min-width: 100px;
  height: 44px;
  padding: 0 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-weight: 600;
  font-size: 0.9rem;
  border-radius: var(--border-radius-sm);
  transition: var(--transition-base);
  border: none;
  cursor: pointer;
  white-space: nowrap;
  background: grey;
}

.btn-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-text { white-space: nowrap; }

.btn-primary { background: var(--color-primary); color: white; }
.btn-primary:hover:not(:disabled) { background: var(--color-primary-hover); }
.btn-success { background: var(--color-success); color: white; }
.btn-success:hover:not(:disabled) { background: #218838; }
.btn-danger { background: var(--color-danger); color: white; }
.btn-danger:hover:not(:disabled) { background: #dc2626; }

.btn-secondary {
  background: var(--color-bg-interactive);
  color: var(--color-text-primary);
  border: 2px solid var(--color-border-medium);
  border-radius: var(--border-radius-sm);
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition-base);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-bg-active);
}

.btn-skip {
  background: transparent;
  color: var(--color-text-muted);
  border: 2px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition-base);
  font-size: 0.9rem;
}

.btn-skip:hover {
  border-color: var(--color-border-medium);
  color: var(--color-text-secondary);
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Alerts */
.alert {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  border-radius: var(--border-radius-sm);
  margin-top: 1rem;
  font-size: 0.9rem;
  line-height: 1.4;
}

.alert-success {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid var(--color-success);
  color: var(--color-success);
}

.alert-danger {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--color-danger);
  color: var(--color-danger);
}

/* Flex utilities */
.flex { display: flex; }
.justify-between { justify-content: space-between; }
.items-center { align-items: center; }
.gap-2 { gap: 0.5rem; }
.gap-4 { gap: 1rem; }
.mt-8 { margin-top: 2rem; }
.py-4 { padding-top: 1rem; padding-bottom: 1rem; }
.px-8 { padding-left: 2rem; padding-right: 2rem; }
.w-full { width: 100%; }
.hidden { display: inline; }

@media (max-width: 768px) {
  .input-group { flex-direction: column; align-items: stretch; }
  .form-input { min-width: auto; }
  .btn-test { min-width: auto; }
  .flex.justify-between { flex-direction: column; }
  .btn-skip, .btn-secondary, .btn-primary { justify-content: center; }
  .rating-source-options { gap: 0.5rem; }
}
</style>
