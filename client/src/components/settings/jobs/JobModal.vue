<template>
  <!-- Not AppDialog: a native modal <dialog> would make the jobs tour, which highlights fields in here, inert. -->
  <Teleport to="body">
    <div class="fixed inset-0 z-[1050] flex bg-black/70 p-4 backdrop-blur-sm max-sm:p-2" @click.self="$emit('close')">
      <div role="dialog" aria-modal="true" aria-labelledby="job-modal-title" class="m-auto flex max-h-full w-full max-w-3xl flex-col overflow-hidden rounded-card border border-edge bg-panel text-ink shadow-2xl">
      <header class="flex shrink-0 items-start gap-3 border-b border-edge px-6 py-4 max-sm:px-4">
        <span aria-hidden="true" class="grid h-9 w-9 shrink-0 place-items-center rounded-ctl bg-brand-soft text-sm text-brand-ink"><i :class="jobTypeInfoIcon"></i></span>
        <div class="min-w-0 flex-1 self-center">
          <h2 id="job-modal-title" class="m-0 text-base font-bold text-ink">{{ isEditing ? 'Edit job' : 'New job' }}</h2>
          <p class="m-0 mt-0.5 text-[13px] text-ink-3">{{ isEditing ? form.name : 'Pick what to look for, when, and how it reaches Seer.' }}</p>
        </div>
        <button type="button" class="-mr-2 grid h-9 w-9 shrink-0 cursor-pointer place-items-center rounded-[8px] border-0 bg-transparent text-ink-3 hover:bg-raised hover:text-ink" aria-label="Close" @click="$emit('close')">
          <i aria-hidden="true" class="fas fa-times"></i>
        </button>
      </header>

      <form @submit.prevent="handleSubmit" class="flex min-h-0 flex-1 flex-col">
        <div class="min-h-0 flex-1 overflow-y-auto p-6 max-sm:p-4">
          <!-- Job Type Selector -->
          <div class="settings-group" data-tour-id="job-modal-type-selector">
            <h4>Job type</h4>
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
                <i class="icon-trakt"></i>
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
            <h4>Basics</h4>

            <div class="form-group">
              <label for="jobName">Name</label>
              <input
                id="jobName"
                v-model="form.name"
                type="text"
                :placeholder="jobNamePlaceholder"
                class="ui-input"
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
                  TV shows
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
            <h4>Users to monitor</h4>
            <RecommendationFilters v-model="form" :show-advanced="showAdvanced" :llm-configured="llmConfigured" />
          </div>

          <div v-if="form.job_type === 'trakt_recommendations'" class="settings-group">
            <h4>Trakt user</h4>
            <TraktRecommendationFilters
              v-model="form"
              :show-advanced="showAdvanced"
              :trakt-configured="traktConfigured"
              :connected-users="connectedUsers"
              :is-loading="traktLoading"
            />
          </div>

          <!-- Schedule -->
          <div class="settings-group">
            <h4>Seer delivery</h4>
            <div class="delivery-mode-selector">
              <button type="button" class="media-type-btn" :class="{ active: form.delivery_mode === 'inherit' }" @click="form.delivery_mode = 'inherit'">
                <i class="fas fa-sliders"></i><span><strong>Use global setting</strong><small>Follow Advanced settings</small></span>
              </button>
              <button type="button" class="media-type-btn" :class="{ active: form.delivery_mode === 'automatic' }" @click="form.delivery_mode = 'automatic'">
                <i class="fas fa-paper-plane"></i><span><strong>Send automatically</strong><small>Queue for Seer immediately</small></span>
              </button>
              <button type="button" class="media-type-btn" :class="{ active: form.delivery_mode === 'manual' }" @click="form.delivery_mode = 'manual'">
                <i class="fas fa-user-check"></i><span><strong>Approve first</strong><small>Review in Requests</small></span>
              </button>
            </div>
            <BaseDropdown
              v-model="form.seer_identity_mode"
              :options="seerIdentityOptions"
              label="Request as"
              placeholder="Select Seer identity"
              help-text="Choose who Seer credits for these requests. Mapped users fall back to the technical user configured in Connections."
            />
            <div class="request-profiles-grid">
              <div v-for="type in visibleProfileTypes" :key="type" class="request-profile-card">
                <div class="request-profile-heading"><i :class="type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i><span>{{ type === 'movie' ? 'Radarr movie profile' : 'Sonarr TV profile' }}</span></div>
                <BaseDropdown :model-value="form.request_profiles[type].serverId || ''" :options="serverOptions(type)" label="Server" placeholder="Use Seer default" @update:model-value="setRequestServer(type, $event)" />
                <template v-if="form.request_profiles[type].serverId">
                  <BaseDropdown v-model="form.request_profiles[type].profileId" :options="profileOptions(type)" label="Quality profile" placeholder="Select quality profile" />
                  <BaseDropdown v-model="form.request_profiles[type].rootFolder" :options="rootFolderOptions(type)" label="Root folder" placeholder="Select root folder" />
                  <BaseDropdown v-if="type === 'tv' && languageProfileOptions(type).length" v-model="form.request_profiles[type].languageProfileId" :options="languageProfileOptions(type)" label="Language profile" placeholder="Use Sonarr default" />
                </template>
              </div>
            </div>
          </div>

          <div class="settings-group" data-tour-id="job-modal-schedule">
            <h4>Schedule</h4>
            <SchedulePicker v-model="schedule" />
            <div class="schedule-options">
              <BaseCheckbox
                v-model="form.pause_if_pending_requests"
                label="Pause while Seer requests are pending"
                description="Skip this job when Seer still has requests awaiting approval or denial."
              />
              <div class="form-group">
                <label>Pause while this job has SuggestArr approvals pending</label>
                <div class="delivery-mode-selector">
                  <button type="button" class="media-type-btn" :class="{ active: form.approval_pause_mode === 'inherit' }" @click="form.approval_pause_mode = 'inherit'">
                    <i class="fas fa-sliders"></i><span><strong>Use global setting</strong><small>Follow Advanced settings</small></span>
                  </button>
                  <button type="button" class="media-type-btn" :class="{ active: form.approval_pause_mode === 'always' }" @click="form.approval_pause_mode = 'always'">
                    <i class="fas fa-pause"></i><span><strong>Always pause</strong><small>Wait for this job's approvals</small></span>
                  </button>
                  <button type="button" class="media-type-btn" :class="{ active: form.approval_pause_mode === 'never' }" @click="form.approval_pause_mode = 'never'">
                    <i class="fas fa-play"></i><span><strong>Never pause</strong><small>Ignore pending approvals</small></span>
                  </button>
                </div>
              </div>
              <BaseCheckbox
                v-if="form.job_type !== 'discover'"
                v-model="form.prevent_suggestions_if_unwatched"
                label="Pause if suggestions remain unwatched"
                description="Scheduled runs only. Manual Run now remains available."
              />
              <div v-if="form.job_type !== 'discover' && form.prevent_suggestions_if_unwatched" class="form-group">
                <label for="unwatchedDays">Days before pausing</label>
                <input id="unwatchedDays" v-model.number="form.unwatched_suggestion_days"
                  class="ui-input" type="number" min="1" required />
              </div>
              <div class="form-group">
                <label for="maxRequestsPerUser">Automatic requests per user</label>
                <input id="maxRequestsPerUser" v-model.number="form.max_requests_per_user"
                  class="ui-input" type="number" min="0" max="1000" required />
                <small class="form-help">Set 0 for no extra limit. Max Results still caps each run.</small>
              </div>
              <div v-if="form.max_requests_per_user > 0" class="form-group">
                <label for="requestLimitWindowHours">Rolling window (hours)</label>
                <input id="requestLimitWindowHours" v-model.number="form.request_limit_window_hours"
                  class="ui-input" type="number" min="1" max="8760" required />
              </div>
            </div>
          </div>

          <!-- Advanced Settings Toggle -->
          <button type="button" class="advanced-toggle" data-tour-id="job-modal-advanced-toggle" @click="showAdvanced = !showAdvanced">
            <i :class="showAdvanced ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
            {{ showAdvanced ? 'Hide advanced settings' : 'Show advanced settings' }}
          </button>

          <!-- Advanced Settings (collapsible) -->
          <transition name="slide">
            <div v-if="showAdvanced" class="advanced-section">
              <!-- Max Results -->
              <div v-if="form.job_type !== 'recommendation'" class="settings-group" data-tour-id="job-modal-max-results">
                <h4>Results</h4>
                <div class="form-group">
                  <label for="maxResults">Max results: {{ form.max_results }}</label>
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
                <h4>{{ form.job_type === 'discover' ? 'Discovery filters' : 'Quality filters' }}</h4>
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

        <footer class="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-edge bg-panel-2/50 px-6 py-3 max-sm:px-4">
          <button type="button" class="ui-btn" @click="$emit('close')">Cancel</button>
          <button type="submit" class="ui-btn-primary" :disabled="!isValid || isSaving">
            <i v-if="isSaving" aria-hidden="true" class="fas fa-spinner fa-spin"></i>
            {{ isEditing ? 'Save job' : 'Create job' }}
          </button>
        </footer>
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
import { listTraktJobUsers } from '@/api/api';
import { waitForAuthReady, useAuth } from '@/composables/useAuth';
import { getJobTypeIcon } from '@/utils/jobTypeVisuals.js';
import axios from 'axios';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import BaseDropdown from '@/components/common/BaseDropdown.vue';

export default {
  name: 'JobModal',
  components: {
    JobFilters,
    RecommendationFilters,
    TraktRecommendationFilters,
    SchedulePicker,
    BaseCheckbox,
    BaseDropdown
  },
  props: {
    job: {
      type: Object,
      default: null
    }
  },
  emits: ['close', 'save'],
  setup() { const { currentUser } = useAuth(); return { currentUser }; },
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
        pause_if_pending_requests: false,
        prevent_suggestions_if_unwatched: false,
        unwatched_suggestion_days: 7
        , max_requests_per_user: 0, request_limit_window_hours: 24
        , delivery_mode: 'inherit', approval_pause_mode: 'inherit', seer_identity_mode: 'technical_user',
        request_profiles: { movie: {}, tv: {} }
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
      , radarrServers: [], sonarrServers: []
    };
  },
  computed: {
    seerIdentityOptions() {
      const options = [
        { value: 'technical_user', label: 'Technical user configured in Connections' },
        { value: 'matching_user', label: 'Mapped Seer user (fallback to technical)' }
      ];
      if (this.currentUser?.role === 'admin') options.push({ value: 'admin_user', label: 'Mapped Seer admin' });
      return options;
    },
    visibleProfileTypes() {
      return this.form.media_type === 'both' ? ['movie', 'tv'] : [this.form.media_type];
    },
    isEditing() {
      return this.job && this.job.id;
    },
    traktJobAvailable() {
      return this.traktConfigured && this.connectedUsers.length > 0;
    },
    traktJobUnavailableReason() {
      if (!this.traktConfigured) {
        return 'Configure Trakt app credentials in Connections before creating a Trakt recommendations job.';
      }
      if (this.connectedUsers.length === 0) {
        return 'Link at least one media user to Trakt in Connections before creating a Trakt recommendations job.';
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
        return 'Trakt Recommendations Jobs fetch personalized movie and show lists only from a linked Trakt account.';
      }
      return 'Recommendation Jobs find similar content based on what your users have watched on your media server or Trakt.tv.';
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
      if (this.form.prevent_suggestions_if_unwatched && this.form.unwatched_suggestion_days < 1) {
        return false;
      }
      if (this.form.max_requests_per_user < 0 || this.form.max_requests_per_user > 1000 || this.form.request_limit_window_hours < 1 || this.form.request_limit_window_hours > 8760) {
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
        pause_if_pending_requests: this.job.pause_if_pending_requests === true,
        prevent_suggestions_if_unwatched: this.job.prevent_suggestions_if_unwatched === true,
        unwatched_suggestion_days: this.job.unwatched_suggestion_days || 7
        , max_requests_per_user: this.job.max_requests_per_user || 0,
        request_limit_window_hours: this.job.request_limit_window_hours || 24
        , delivery_mode: this.job.delivery_mode || 'automatic',
        approval_pause_mode: this.job.approval_pause_mode || 'inherit',
        seer_identity_mode: this.job.seer_identity_mode || 'technical_user',
        request_profiles: {
          movie: { ...(this.job.request_profiles?.movie || {}) },
          tv: { ...(this.job.request_profiles?.tv || {}) }
        }
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
    try {
      const [radarr, sonarr] = await Promise.all([axios.get('/api/seer/radarr-servers'), axios.get('/api/seer/sonarr-servers')]);
      this.radarrServers = radarr.data.servers || [];
      this.sonarrServers = sonarr.data.servers || [];
    } catch { /* Seer defaults remain available. */ }
  },
  methods: {
    serversFor(type) { return type === 'movie' ? this.radarrServers : this.sonarrServers; },
    selectedServer(type) { return this.serversFor(type).find(server => String(server.id) === String(this.form.request_profiles[type].serverId)); },
    serverOptions(type) { return this.serversFor(type).map(server => ({ value: server.id, label: `${server.name}${server.is4k ? ' (4K)' : ''}` })); },
    profileOptions(type) { return (this.selectedServer(type)?.profiles || []).map(profile => ({ value: profile.id, label: profile.name })); },
    rootFolderOptions(type) { return (this.selectedServer(type)?.rootFolders || []).map(folder => ({ value: folder.path, label: folder.path })); },
    languageProfileOptions(type) { return (this.selectedServer(type)?.languageProfiles || []).map(profile => ({ value: profile.id, label: profile.name })); },
    setRequestServer(type, serverId) {
      const server = this.serversFor(type).find(item => String(item.id) === String(serverId));
      this.form.request_profiles[type] = { serverId, profileId: '', rootFolder: '', is4k: server?.is4k === true, languageProfileId: server?.activeLanguageProfileId ?? '' };
    },
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
        const traktUsers = await listTraktJobUsers(this.currentUser?.role);
        this.connectedUsers = traktUsers
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
          request_profiles: Object.fromEntries(Object.entries(this.form.request_profiles).map(([type, profile]) => [
            type,
            profile.serverId && profile.profileId && profile.rootFolder ? {
              serverId: Number(profile.serverId),
              profileId: Number(profile.profileId),
              rootFolder: profile.rootFolder,
              is4k: profile.is4k === true,
              ...(profile.languageProfileId !== '' && profile.languageProfileId != null ? { languageProfileId: Number(profile.languageProfileId) } : {})
            } : {}
          ])),
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
/* Job type selector */
.job-type-selector {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
}

.job-type-btn,
.media-type-btn {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 0.875rem;
  background: var(--color-panel-2);
  border: 1px solid var(--color-edge-strong);
  border-radius: var(--radius-ctl);
  color: var(--color-ink-2);
  cursor: pointer;
  text-align: left;
  font-size: 0.85rem;
  font-weight: 600;
  transition: border-color 0.15s, background-color 0.15s;
}

.job-type-btn:hover:not(:disabled),
.media-type-btn:hover {
  border-color: var(--color-ink-4);
  color: var(--color-ink);
}

.job-type-btn.active,
.media-type-btn.active {
  background: var(--color-brand-soft);
  border-color: var(--color-brand);
  color: var(--color-ink);
}

.job-type-btn i {
  width: 1.25rem;
  text-align: center;
  color: var(--color-ink-4);
}

.job-type-btn.active i,
.media-type-btn.active > i {
  color: var(--color-brand-ink);
}

.job-type-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}

.job-type-desc {
  font-size: 0.72rem;
  font-weight: 400;
  color: var(--color-ink-3);
}

.job-type-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.trakt-setup-alert {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-top: 0.75rem;
  padding: 0.75rem;
  border: 1px dashed var(--color-edge-strong);
  border-radius: var(--radius-ctl);
  color: var(--color-ink-3);
  font-size: 0.8rem;
}

.trakt-setup-alert i {
  color: var(--color-brand-ink);
  margin-top: 0.1rem;
}

.info-note {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--color-panel-2);
  border: 1px solid var(--color-edge);
  border-radius: var(--radius-ctl);
  margin-bottom: 1.5rem;
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--color-ink-3);
}

.info-note i {
  flex-shrink: 0;
  margin-top: 0.15rem;
  color: var(--color-brand-ink);
}

.settings-group {
  margin-bottom: 1.75rem;
}

.settings-group:last-of-type {
  margin-bottom: 0;
}

/* Filters section needs room for dropdowns */
.settings-group.filters-section {
  position: relative;
  z-index: 50;
}

.dropdown-spacer {
  height: 1rem;
}

.settings-group h4 {
  font-size: 11px;
  font-weight: 700;
  color: var(--color-ink-4);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 0 0 0.75rem;
}

.delivery-mode-selector {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.delivery-mode-selector .media-type-btn span {
  display: grid;
  flex: 1;
  gap: 0.15rem;
}

.delivery-mode-selector .media-type-btn > i {
  flex: 0 0 1rem;
  text-align: center;
  color: var(--color-ink-4);
}

.delivery-mode-selector small {
  color: var(--color-ink-3);
  font-size: 0.72rem;
  font-weight: 400;
}

.request-profiles-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(0, 1fr));
  gap: 0.75rem;
  margin-top: 1rem;
}

.request-profile-card {
  display: grid;
  gap: 0.5rem;
  padding: 1rem;
  background: var(--color-panel-2);
  border: 1px solid var(--color-edge);
  border-radius: var(--radius-ctl);
}

.request-profile-heading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--color-ink);
  font-size: 0.85rem;
  font-weight: 600;
}

.request-profile-heading i {
  color: var(--color-ink-4);
}

.form-group {
  margin-bottom: 1rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink-2);
  margin-bottom: 0.4rem;
}

.form-help {
  display: block;
  font-size: 0.75rem;
  color: var(--color-ink-4);
  margin-top: 0.35rem;
}

.schedule-options {
  display: grid;
  gap: 1rem;
  margin-top: 1rem;
}

.schedule-options > .form-group,
.schedule-options .delivery-mode-selector {
  margin-bottom: 0;
}

.media-type-selector {
  display: flex;
  gap: 0.5rem;
}

.media-type-selector .media-type-btn {
  flex: 1;
  justify-content: center;
}

.form-range {
  width: 100%;
  margin-top: 0.5rem;
  accent-color: var(--color-brand);
}

.advanced-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  width: 100%;
  margin: 1.75rem 0 1rem;
  padding: 0.7rem 1rem;
  background: transparent;
  border: 1px dashed var(--color-edge-strong);
  border-radius: var(--radius-ctl);
  color: var(--color-ink-3);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}

.advanced-toggle:hover {
  border-color: var(--color-brand-ink);
  color: var(--color-brand-ink);
}

.advanced-toggle i {
  font-size: 0.75rem;
}

.advanced-section {
  border-top: 1px solid var(--color-edge);
  padding-top: 1.25rem;
}

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

@media (max-width: 768px) {
  .job-type-selector,
  .delivery-mode-selector,
  .request-profiles-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .media-type-selector {
    flex-direction: column;
  }
}
</style>
