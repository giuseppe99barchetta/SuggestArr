<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content">
      <!-- Minimal Header -->
      <div class="modal-header">
        <h3 class="modal-title">{{ isEditing ? 'Edit Job' : 'Create New Job' }}</h3>
        <button @click="$emit('close')" class="close-btn" aria-label="Close">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <form @submit.prevent="handleSubmit" class="modal-form">
        <div class="modal-body">
          <!-- Job Type Selector -->
          <div class="settings-group">
            <h4>Job Type</h4>
            <div class="job-type-selector">
              <button
                type="button"
                class="job-type-btn"
                :class="{ active: form.job_type === 'discover' }"
                @click="setJobType('discover')"
              >
                <i class="fas fa-search"></i>
                <div class="job-type-info">
                  <span class="job-type-name">Discover</span>
                  <span class="job-type-desc">Find content using TMDb filters</span>
                </div>
              </button>
              <button
                type="button"
                class="job-type-btn"
                :class="{ active: form.job_type === 'recommendation' }"
                @click="setJobType('recommendation')"
              >
                <i class="fas fa-users"></i>
                <div class="job-type-info">
                  <span class="job-type-name">Recommendation</span>
                  <span class="job-type-desc">Based on user watch history</span>
                </div>
              </button>
            </div>
          </div>

          <!-- Info Note based on job type -->
          <div class="info-note" :class="form.job_type">
            <i :class="form.job_type === 'discover' ? 'fas fa-search' : 'fas fa-history'"></i>
            <span v-if="form.job_type === 'discover'">
              Discover Jobs find content using TMDb filters, independent from user watch history.
            </span>
            <span v-else>
              Recommendation Jobs find similar content based on what your users have watched.
            </span>
          </div>

          <!-- Basic Info -->
          <div class="settings-group">
            <h4>Basic Information</h4>

            <div class="form-group">
              <label for="jobName">Job Name</label>
              <input
                id="jobName"
                v-model="form.name"
                type="text"
                :placeholder="form.job_type === 'discover' ? 'e.g., Popular Movies 2024' : 'e.g., Weekly Recommendations'"
                class="form-control"
                required
              />
            </div>

            <div class="form-group">
              <label>Media Type</label>
              <div class="media-type-selector">
                <button
                  type="button"
                  class="media-type-btn"
                  :class="{ active: form.media_type === 'movie' }"
                  @click="form.media_type = 'movie'"
                >
                  <i class="fas fa-film"></i>
                  Movies
                </button>
                <button
                  type="button"
                  class="media-type-btn"
                  :class="{ active: form.media_type === 'tv' }"
                  @click="form.media_type = 'tv'"
                >
                  <i class="fas fa-tv"></i>
                  TV Shows
                </button>
                <button
                  v-if="form.job_type === 'recommendation'"
                  type="button"
                  class="media-type-btn"
                  :class="{ active: form.media_type === 'both' }"
                  @click="form.media_type = 'both'"
                >
                  <i class="fas fa-layer-group"></i>
                  Both
                </button>
              </div>
            </div>
          </div>

          <!-- User Selection (only for recommendation jobs) -->
          <div v-if="form.job_type === 'recommendation'" class="settings-group">
            <h4>Users to Monitor</h4>
            <RecommendationFilters v-model="form" :show-advanced="showAdvanced" :llm-configured="llmConfigured" />
          </div>

          <!-- Schedule -->
          <div class="settings-group">
            <h4>Schedule</h4>
            <SchedulePicker v-model="schedule" />
          </div>

          <!-- Advanced Settings Toggle -->
          <button type="button" class="advanced-toggle" @click="showAdvanced = !showAdvanced">
            <i :class="showAdvanced ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
            {{ showAdvanced ? 'Hide Advanced Settings' : 'Show Advanced Settings' }}
          </button>

          <!-- Advanced Settings (collapsible) -->
          <transition name="slide">
            <div v-if="showAdvanced" class="advanced-section">
              <!-- Max Results -->
              <div class="settings-group">
                <h4>Results</h4>
                <div class="form-group">
                  <label for="maxResults">Max Results: {{ form.max_results }}</label>
                  <input
                    id="maxResults"
                    v-model.number="form.max_results"
                    type="range"
                    min="5"
                    max="100"
                    step="5"
                    class="form-range"
                  />
                  <small class="form-help">
                    {{ form.job_type === 'discover' ? 'Maximum content to discover per run' : 'Maximum similar content per watched item' }}
                  </small>
                </div>
              </div>

              <!-- Filters -->
              <div class="settings-group filters-section">
                <h4>{{ form.job_type === 'discover' ? 'Discovery Filters' : 'Quality Filters' }}</h4>
                <JobFilters v-model="form.filters" :media-type="form.media_type" />
              </div>

              <!-- Spacer for dropdown overflow -->
              <div class="dropdown-spacer"></div>
            </div>
          </transition>
        </div>

        <!-- Footer outside scrollable area -->
        <div class="modal-footer">
          <button type="button" @click="$emit('close')" class="btn btn-secondary">
            Cancel
          </button>
          <button type="submit" class="btn btn-primary" :disabled="!isValid || isSaving">
            <i v-if="isSaving" class="fas fa-spinner fa-spin"></i>
            <i v-else class="fas fa-check"></i>
            {{ isEditing ? 'Update Job' : 'Create Job' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import JobFilters from './JobFilters.vue';
import RecommendationFilters from './RecommendationFilters.vue';
import SchedulePicker from './SchedulePicker.vue';
import { jobsApi } from '@/api/jobsApi';

export default {
  name: 'JobModal',
  components: {
    JobFilters,
    RecommendationFilters,
    SchedulePicker
  },
  props: {
    job: {
      type: Object,
      default: null
    }
  },
  emits: ['close', 'save'],
  data() {
    return {
      form: {
        name: '',
        job_type: 'discover',
        media_type: 'movie',
        max_results: 20,
        filters: {},
        user_ids: [],
        enabled: true
      },
      schedule: {
        type: 'preset',
        value: 'daily'
      },
      isSaving: false,
      showAdvanced: false,
      llmConfigured: false
    };
  },
  computed: {
    isEditing() {
      return this.job && this.job.id;
    },
    isValid() {
      return this.form.name.trim().length > 0 && this.form.media_type;
    }
  },
  async mounted() {
    if (this.job) {
      this.form = {
        name: this.job.name || '',
        job_type: this.job.job_type || 'discover',
        media_type: this.job.media_type || 'movie',
        max_results: this.job.max_results || 20,
        filters: this.job.filters ? JSON.parse(JSON.stringify(this.job.filters)) : {},
        user_ids: this.job.user_ids ? [...this.job.user_ids] : [],
        enabled: this.job.enabled !== false
      };
      this.schedule = {
        type: this.job.schedule_type || 'preset',
        value: this.job.schedule_value || 'daily'
      };
    }
    try {
      const llmStatus = await jobsApi.getLlmStatus();
      this.llmConfigured = llmStatus.configured === true;
    } catch {
      this.llmConfigured = false;
    }
  },
  methods: {
    setJobType(jobType) {
      this.form.job_type = jobType;
      // Reset media_type if switching from recommendation to discover and 'both' was selected
      if (jobType === 'discover' && this.form.media_type === 'both') {
        this.form.media_type = 'movie';
      }
      // Clear user_ids when switching to discover
      if (jobType === 'discover') {
        this.form.user_ids = [];
      }
    },
    async handleSubmit() {
      if (!this.isValid) return;

      this.isSaving = true;
      try {
        const jobData = {
          ...this.form,
          schedule_type: this.schedule.type,
          schedule_value: this.schedule.value
        };
        this.$emit('save', jobData);
      } finally {
        this.isSaving = false;
      }
    }
  }
};
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: var(--color-bg-overlay-heavy);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: var(--z-modal);
  padding: 1rem;
}

.modal-content {
  background: var(--color-bg-content);
  backdrop-filter: blur(20px);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.05),
    0 20px 50px -12px rgba(0, 0, 0, 0.5);
  max-width: 800px;
  width: 100%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 2rem;
  flex-shrink: 0;
}

.modal-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-text-primary);
}

.close-btn {
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.5rem;
  transition: var(--transition-base);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
}

.close-btn:hover {
  background: var(--color-bg-overlay-light);
  color: var(--color-text-primary);
}

.modal-form {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 2rem 2rem;
}

.modal-body::-webkit-scrollbar {
  width: 10px;
}

.modal-body::-webkit-scrollbar-track {
  background: var(--color-bg-overlay-light);
}

.modal-body::-webkit-scrollbar-thumb {
  background: var(--color-primary);
  border-radius: var(--radius-sm);
}

/* Job Type Selector */
.job-type-selector {
  display: flex;
  gap: 0.5rem;
}

.job-type-btn {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  background: transparent;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: var(--transition-base);
  text-align: left;
}

.job-type-btn:hover {
  background: var(--color-bg-overlay-light);
  color: var(--color-text-primary);
}

.job-type-btn.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
}

.job-type-btn i {
  font-size: 1rem;
  width: 1.5rem;
  text-align: center;
}

.job-type-btn.active i {
  color: white;
}

.job-type-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.job-type-name {
  font-weight: var(--font-weight-medium);
  font-size: 0.85rem;
}

.job-type-desc {
  font-size: 0.7rem;
  color: var(--color-text-muted);
}

.job-type-btn.active .job-type-desc {
  color: rgba(255, 255, 255, 0.8);
}

/* Info Note */
.info-note {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--color-bg-overlay-light);
  border-radius: var(--radius-sm);
  margin-bottom: 1.5rem;
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.info-note.recommendation {
  background: var(--color-bg-overlay-light);
}

.info-note i {
  font-size: 0.9rem;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.settings-group {
  margin-bottom: 1.5rem;
  overflow: visible;
}

.settings-group:last-of-type {
  margin-bottom: 0;
}

/* Filters section needs room for dropdowns */
.settings-group.filters-section {
  overflow: visible;
  position: relative;
  z-index: 50;
}

/* Small spacer for visual breathing room */
.dropdown-spacer {
  height: 1rem;
  flex-shrink: 0;
}

.settings-group h4 {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 1rem 0;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  font-size: 0.8rem;
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: 0.4rem;
}

.form-control {
  width: 100%;
  padding: 0.65rem 0.875rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-primary);
  font-size: 0.9rem;
  transition: var(--transition-base);
}

.form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--shadow-glow);
}

.form-control::placeholder {
  color: var(--color-text-muted);
}

.form-help {
  display: block;
  font-size: 0.75rem;
  color: var(--color-text-muted);
  margin-top: 0.35rem;
}

.media-type-selector {
  display: flex;
  gap: 0.5rem;
}

.media-type-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.65rem 0.75rem;
  background: transparent;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: var(--transition-base);
  font-size: 0.85rem;
  font-weight: var(--font-weight-medium);
}

.media-type-btn:hover {
  background: var(--color-bg-overlay-light);
  color: var(--color-text-primary);
}

.media-type-btn.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
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

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.25rem 2rem;
  background: var(--color-bg-content);
  flex-shrink: 0;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--radius-sm);
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: var(--transition-base);
  font-size: 0.9rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}

.btn-secondary {
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-bg-active);
  border-color: var(--color-primary);
}

/* Advanced Toggle */
.advanced-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  background: transparent;
  border: 1px dashed var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  font-size: 0.85rem;
  cursor: pointer;
  transition: var(--transition-base);
}

.advanced-toggle:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-alpha-10);
}

.advanced-toggle i {
  font-size: 0.75rem;
  transition: transform 0.2s ease;
}

.advanced-section {
  border-top: 1px solid var(--color-border-light);
  padding-top: 1rem;
}

/* Slide Transition */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 2000px;
}

@media (max-width: 850px) {
  .modal-content {
    max-width: 95%;
  }
}

@media (max-width: 600px) {
  .modal-overlay {
    padding: 0;
  }

  .modal-content {
    max-width: 100%;
    max-height: 100vh;
    height: 100vh;
    border-radius: 0;
  }

  .modal-header {
    padding: 1rem 1.25rem;
  }

  .modal-body {
    padding: 0.5rem 1.25rem 1.5rem;
  }

  .modal-title {
    font-size: 1.1rem;
  }

  .media-type-selector {
    flex-direction: column;
  }

  .job-type-selector {
    flex-direction: column;
  }

  .modal-footer {
    padding: 1rem 1.25rem;
    gap: 0.5rem;
  }

  .btn {
    flex: 1;
    padding: 0.75rem 1rem;
  }

  .settings-group {
    padding: 1.25rem;
    margin-bottom: 1.25rem;
  }
}
</style>
