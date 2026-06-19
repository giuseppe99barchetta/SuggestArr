<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
      <!-- Minimal Header -->
      <div class="modal-header">
        <h3 class="modal-title">{{ isEditing ? 'Edit Job' : 'Create New Job' }}</h3>
        <button @click="$emit('close')" class="modal-close" aria-label="Close">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <form @submit.prevent="handleSubmit" class="modal-form">
        <div class="modal-body">
          <!-- Job Type Selector -->
          <div class="settings-group" data-tour-id="job-modal-type-selector">
            <h4>Job Type</h4>
            <div class="job-type-selector">
              <button
                type="button"
                class="job-type-btn discover"
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
                class="job-type-btn recommendation"
                :class="{ active: form.job_type === 'recommendation' }"
                @click="setJobType('recommendation')"
              >
                <i class="fas fa-users"></i>
                <div class="job-type-info">
                  <span class="job-type-name">Recommendation</span>
                  <span class="job-type-desc">Based on user watch history</span>
                </div>
              </button>
              <button
                type="button"
                class="job-type-btn trakt_recommendations"
                :class="{
                  active: form.job_type === 'trakt_recommendations',
                  disabled: !traktJobAvailable
                }"
                :disabled="!traktJobAvailable"
                :title="traktJobUnavailableReason"
                @click="setJobType('trakt_recommendations')"
              >
                <i class="fab fa-trakt"></i>
                <div class="job-type-info">
                  <span class="job-type-name">Trakt Recommendations</span>
                  <span class="job-type-desc">Personalized lists from Trakt.tv</span>
                </div>
              </button>
            </div>
            <div v-if="!traktJobAvailable" class="trakt-setup-alert" role="status">
              <i class="fas fa-circle-info"></i>
              <span>{{ traktJobUnavailableReason }}</span>
            </div>
          </div>

          <!-- Info Note based on job type -->
          <div class="info-note" :class="form.job_type">
            <i :class="jobTypeInfoIcon"></i>
            <span>{{ jobTypeInfoText }}</span>
          </div>

          <!-- Basic Info -->
          <div class="settings-group" data-tour-id="job-modal-basic-info">
            <h4>Basic Information</h4>

            <div class="form-group">
              <label for="jobName">Job Name</label>
              <input
                id="jobName"
                v-model="form.name"
                type="text"
                :placeholder="jobNamePlaceholder"
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
                  v-if="form.job_type !== 'discover'"
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

          <div v-if="form.job_type === 'trakt_recommendations'" class="settings-group">
            <h4>Trakt User</h4>
            <TraktRecommendationFilters
              v-model="form"
              :show-advanced="showAdvanced"
              :trakt-configured="traktConfigured"
              :connected-users="connectedUsers"
              :is-loading="traktLoading"
            />
          </div>

          <!-- Schedule -->
          <div class="settings-group" data-tour-id="job-modal-schedule">
            <h4>Schedule</h4>
            <SchedulePicker v-model="schedule" />
            <label class="pause-pending-toggle">
              <input
                v-model="form.pause_if_pending_requests"
                type="checkbox"
              />
              <span>
                <strong>Pause while Seer requests are pending</strong>
                <small>Skip this job when Seer still has requests awaiting approval or denial.</small>
              </span>
            </label>
          </div>

          <!-- Advanced Settings Toggle -->
          <button type="button" class="advanced-toggle" data-tour-id="job-modal-advanced-toggle" @click="showAdvanced = !showAdvanced">
            <i :class="showAdvanced ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
            {{ showAdvanced ? 'Hide Advanced Settings' : 'Show Advanced Settings' }}
          </button>

          <!-- Advanced Settings (collapsible) -->
          <transition name="slide">
            <div v-if="showAdvanced" class="advanced-section">
              <!-- Max Results -->
              <div v-if="form.job_type !== 'recommendation'" class="settings-group" data-tour-id="job-modal-max-results">
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
                    Maximum content to discover per run
                  </small>
                </div>
              </div>

              <!-- Filters -->
              <div class="settings-group filters-section" data-tour-id="job-modal-filters">
                <h4>{{ form.job_type === 'discover' ? 'Discovery Filters' : 'Quality Filters' }}</h4>
                <JobFilters
                  v-model="form.filters"
                  :media-type="form.media_type"
                  :job-type="form.job_type"
                />
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
  </Teleport>
</template>

<script>
import JobFilters from './JobFilters.vue';
import RecommendationFilters from './RecommendationFilters.vue';
import TraktRecommendationFilters from './TraktRecommendationFilters.vue';
import SchedulePicker from './SchedulePicker.vue';
import { jobsApi } from '@/api/jobsApi';
import { listTraktMediaUsers } from '@/api/api';
import { waitForAuthReady } from '@/composables/useAuth';
import { getJobTypeIcon } from '@/utils/jobTypeVisuals.js';
import axios from 'axios';

export default {
  name: 'JobModal',
  components: {
    JobFilters,
    RecommendationFilters,
    TraktRecommendationFilters,
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
      connectedUsers: [],
      form: {
        name: '',
        job_type: 'discover',
        media_type: 'movie',
        max_results: 20,
        filters: {},
        user_ids: [],
        enabled: true,
        pause_if_pending_requests: false
      },
      schedule: {
        type: 'preset',
        value: 'daily'
      },
      isSaving: false,
      showAdvanced: false,
      llmConfigured: false,
      traktConfigured: false,
      traktLoading: false
    };
  },
  computed: {
    isEditing() {
      return this.job && this.job.id;
    },
    traktJobAvailable() {
      return this.traktConfigured && this.connectedUsers.length > 0;
    },
    traktJobUnavailableReason() {
      if (!this.traktConfigured) {
        return 'Configure Trakt app credentials in Services before creating a Trakt recommendations job.';
      }
      if (this.connectedUsers.length === 0) {
        return 'Link at least one media user to Trakt in Services before creating a Trakt recommendations job.';
      }
      return '';
    },
    jobTypeInfoIcon() {
      return getJobTypeIcon(this.form.job_type);
    },
    jobTypeInfoText() {
      if (this.form.job_type === 'discover') {
        return 'Discover Jobs find content using TMDb filters, independent from user watch history.';
      }
      if (this.form.job_type === 'trakt_recommendations') {
        return 'Trakt Recommendations Jobs fetch personalized movie and show lists from a linked Trakt account.';
      }
      return 'Recommendation Jobs find similar content based on what your users have watched.';
    },
    jobNamePlaceholder() {
      if (this.form.job_type === 'discover') return 'e.g., Popular Movies 2024';
      if (this.form.job_type === 'trakt_recommendations') return 'e.g., Weekly Trakt Picks';
      return 'e.g., Weekly Recommendations';
    },
    isValid() {
      if (!this.form.name.trim().length || !this.form.media_type) {
        return false;
      }
      if (this.form.job_type === 'trakt_recommendations') {
        return (this.form.user_ids || []).length === 1;
      }
      return true;
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
        enabled: this.job.enabled !== false,
        pause_if_pending_requests: this.job.pause_if_pending_requests === true
      };
      this.schedule = {
        type: this.job.schedule_type || 'preset',
        value: this.job.schedule_value || 'daily'
      };
    }
    // For new jobs, pre-populate filters with global config defaults
    if (!this.isEditing) {
      try {
        const defaultsResponse = await jobsApi.getDefaultFilters();
        if (defaultsResponse.status === 'success') {
          const d = defaultsResponse.defaults;
          this.form.filters = {
            vote_average_gte: d.vote_average_gte,
            ...(d.vote_count_gte != null ? { vote_count_gte: d.vote_count_gte } : {}),
            request_first_season_only: d.request_first_season_only === true,
            ...this.form.filters
          };
        }
      } catch {
        // fallback: leave filters as-is
      }
    }
    try {
      const llmStatus = await jobsApi.getLlmStatus();
      this.llmConfigured = llmStatus.configured === true;
      // For new jobs, auto-enable AI recommendations if ENABLE_ADVANCED_ALGORITHM is on
      if (!this.isEditing && this.llmConfigured && llmStatus.advanced_algorithm_enabled === true) {
        this.form.filters = { ...this.form.filters, use_llm: true };
      }
    } catch {
      this.llmConfigured = false;
    }
    await this.refreshTraktSetup();
  },
  methods: {
    openAdvanced() {
      this.showAdvanced = true;
    },

    async refreshTraktSetup() {
      this.traktLoading = true;
      try {
        await waitForAuthReady();
        const statusResponse = await axios.get('/api/config/status');
        this.traktConfigured = statusResponse.data?.trakt_app_configured === true;
        if (!this.traktConfigured) {
          this.connectedUsers = [];
          return;
        }
        const traktRes = await listTraktMediaUsers();
        this.connectedUsers = (traktRes.data?.media_users || [])
          .filter((user) => user.trakt?.connected);
      } catch {
        this.traktConfigured = false;
        this.connectedUsers = [];
      } finally {
        this.traktLoading = false;
      }
    },

    setJobType(jobType) {
      if (jobType === 'trakt_recommendations' && !this.traktJobAvailable) {
        return;
      }
      this.form.job_type = jobType;
      if (jobType === 'discover' && this.form.media_type === 'both') {
        this.form.media_type = 'movie';
      }
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
/* Component-specific styles only */

.modal {
  position: relative;
  z-index: 2001;
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

.job-type-btn.discover > i {
  color: var(--color-primary-light);
}

.job-type-btn.recommendation > i {
  color: var(--color-warning-light);
}

.job-type-btn.trakt_recommendations > i {
  color: var(--color-error-light);
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

.job-type-btn.disabled,
.job-type-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.job-type-btn.disabled:hover,
.job-type-btn:disabled:hover {
  background: transparent;
  color: var(--color-text-secondary);
  border-color: var(--color-border-light);
}

.trakt-setup-alert {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-top: 0.75rem;
  padding: 0.75rem;
  border: 1px dashed var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.trakt-setup-alert i {
  color: var(--color-primary);
  margin-top: 0.1rem;
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

.info-note.discover i {
  color: var(--color-primary-light);
}

.info-note.recommendation i {
  color: var(--color-warning-light);
}

.info-note.trakt_recommendations i {
  color: var(--color-error-light);
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

.pause-pending-toggle {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  margin-top: 1rem;
  padding: 0.75rem;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
}

.pause-pending-toggle input {
  margin-top: 0.2rem;
}

.pause-pending-toggle span {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.pause-pending-toggle strong {
  font-size: 0.85rem;
  color: var(--color-text-primary);
}

.pause-pending-toggle small {
  color: var(--color-text-muted);
  font-size: 0.75rem;
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



@media (max-width: 600px) {
  .media-type-selector {
    flex-direction: column;
  }

  .job-type-selector {
    flex-direction: column;
  }

  .settings-group {
    padding: 1.25rem;
    margin-bottom: 1.25rem;
  }
}
</style>
