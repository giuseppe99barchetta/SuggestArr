<template>
  <!-- Not AppDialog: a native modal <dialog> would make the jobs tour, which highlights fields in here, inert. -->
  <Teleport to="body">
    <div class="fixed inset-0 z-[1050] flex bg-black/70 p-4 backdrop-blur-sm max-sm:p-2" @click.self="requestClose">
      <div role="dialog" aria-modal="true" aria-labelledby="job-modal-title" class="m-auto flex max-h-full w-full max-w-3xl flex-col overflow-hidden rounded-card border border-edge bg-panel text-ink shadow-2xl">
      <header class="flex shrink-0 items-start gap-3 border-b border-edge px-6 py-4 max-sm:px-4">
        <span aria-hidden="true" class="grid h-9 w-9 shrink-0 place-items-center rounded-ctl bg-brand-soft text-sm text-brand-ink"><i aria-hidden="true" :class="jobTypeInfoIcon"></i></span>
        <div class="min-w-0 flex-1 self-center">
          <h2 id="job-modal-title" class="m-0 text-base font-bold text-ink">{{ oneTime ? 'Import list once' : isEditing ? 'Edit job' : 'New job' }}</h2>
          <p class="m-0 mt-0.5 text-[13px] text-ink-3">{{ oneTime ? 'Import all matching titles without creating a scheduled job.' : isEditing ? form.name : 'Pick what to look for, when, and how it reaches Seer.' }}</p>
        </div>
        <button type="button" class="-mr-2 grid h-9 w-9 shrink-0 cursor-pointer place-items-center rounded-[8px] border-0 bg-transparent text-ink-3 hover:bg-raised hover:text-ink" aria-label="Close" @click="requestClose">
          <i aria-hidden="true" class="fas fa-times"></i>
        </button>
      </header>

      <form @submit.prevent="handleSubmit" class="flex min-h-0 flex-1 flex-col">
        <div class="min-h-0 flex-1 overflow-y-auto p-6 max-sm:p-4 [&_h4]:m-0 [&_h4]:mb-3 [&_h4]:text-[11px] [&_h4]:font-bold [&_h4]:uppercase [&_h4]:tracking-[0.08em] [&_h4]:text-ink-4">
          <!-- Job Type Selector -->
          <div v-if="!oneTime" class="mb-7" data-tour-id="job-modal-type-selector">
            <h4>Job type</h4>
            <div class="grid gap-2 md:grid-cols-2">
              <button
                v-for="type in jobTypes"
                :key="type.value"
                type="button"
                :class="choiceClass(form.job_type === type.value)"
                :disabled="type.value === 'trakt_recommendations' && !traktJobAvailable"
                :title="type.value === 'trakt_recommendations' ? traktJobUnavailableReason : null"
                @click="setJobType(type.value)"
              >
                <i aria-hidden="true" :class="type.icon" class="w-5 text-center"></i>
                <span class="flex min-w-0 flex-col gap-0.5">
                  <span>{{ type.label }}</span>
                  <span class="text-[0.72rem] font-normal text-ink-3">{{ type.description }}</span>
                </span>
              </button>
            </div>
            <div v-if="!traktJobAvailable" class="mt-3 flex items-start gap-2 rounded-ctl border border-dashed border-edge-strong p-3 text-[0.8rem] text-ink-3" role="status">
              <i aria-hidden="true" class="fas fa-circle-info mt-0.5 text-brand-ink"></i>
              <span>{{ traktJobUnavailableReason }}</span>
            </div>
          </div>

          <!-- Info Note based on job type -->
          <div class="mb-6 flex items-start gap-3 rounded-ctl border border-edge bg-panel-2 px-4 py-3 text-[0.8rem] leading-normal text-ink-3">
            <i aria-hidden="true" :class="jobTypeInfoIcon" class="mt-0.5 shrink-0 text-brand-ink"></i>
            <span>{{ jobTypeInfoText }}</span>
          </div>

          <!-- Basic Info -->
          <div class="mb-7 flex flex-col gap-4" data-tour-id="job-modal-basic-info">
            <h4 class="mb-0!">Basics</h4>

            <label v-if="!oneTime" class="ui-label" for="jobName">
              Name
              <input
                id="jobName"
                v-model="form.name"
                type="text"
                :placeholder="jobNamePlaceholder"
                class="ui-input"
                required
              />
            </label>

            <div class="ui-label">
              <span>Media Type</span>
              <div class="flex gap-2 max-[600px]:flex-col">
                <button
                  v-for="type in mediaTypes"
                  v-show="type.value !== 'both' || form.job_type !== 'discover'"
                  :key="type.value"
                  type="button"
                  :class="[choiceClass(form.media_type === type.value), 'flex-1 justify-center']"
                  @click="form.media_type = type.value"
                >
                  <i aria-hidden="true" :class="type.icon"></i>
                  {{ type.label }}
                </button>
              </div>
            </div>
          </div>

          <!-- User Selection (only for recommendation jobs) -->
          <div v-if="form.job_type === 'recommendation'" class="mb-7">
            <h4>Users to monitor</h4>
            <RecommendationFilters v-model="form" :show-advanced="showAdvanced" :llm-configured="llmConfigured" />
          </div>

          <div v-if="form.job_type === 'trakt_recommendations'" class="mb-7">
            <h4>Trakt user</h4>
            <TraktRecommendationFilters
              v-model="form"
              :show-advanced="showAdvanced"
              :trakt-configured="traktConfigured"
              :connected-users="connectedUsers"
              :is-loading="traktLoading"
            />
          </div>

          <!-- Seer delivery -->
          <div v-if="form.job_type === 'list_import'" class="mb-7 grid gap-3" data-testid="public-list-source">
            <h4>Public list</h4>
            <BaseDropdown v-model="form.filters.list_provider" :options="listProviders" label="Provider" placeholder="Select provider" @update:model-value="listCheckMessage = ''" />
            <label class="ui-label" for="listUrl">List URL
              <input id="listUrl" v-model="form.filters.list_url" type="url" required class="ui-input" placeholder="https://mdblist.com/lists/username/list-name" @input="listCheckMessage = ''" />
            </label>
            <p class="m-0 text-xs text-ink-3">{{ oneTime ? 'All matching titles are checked and queued in the background. Titles already in your library, requested or queued are skipped.' : 'Public lists only. Existing list entries are imported gradually; requests are credited to this job’s owner when using a mapped Seer user.' }}</p>
            <div class="flex flex-wrap items-center gap-3">
              <button type="button" class="ui-btn" :disabled="listChecking || !form.filters.list_provider || !form.filters.list_url" @click="verifyList">{{ listChecking ? 'Checking…' : 'Verify list' }}</button>
              <button type="button" class="ui-btn" :disabled="listPreviewLoading || !form.filters.list_provider || !form.filters.list_url" @click="previewList()"><i aria-hidden="true" :class="listPreviewLoading ? 'fas fa-spinner fa-spin' : 'fas fa-eye'"></i>{{ listPreviewLoading ? 'Loading…' : 'Preview list' }}</button>
              <span v-if="listCheckMessage" role="status" class="min-w-0 break-words text-sm" :class="listCheckSuccess ? 'text-good' : 'text-bad'">{{ listCheckMessage }}</span>
            </div>
          </div>

          <div class="mb-7">
            <h4>Seer delivery</h4>
            <div class="mb-4 grid gap-2 md:grid-cols-3">
              <button v-for="mode in deliveryModes" :key="mode.value" type="button" :class="choiceClass(form.delivery_mode === mode.value)" @click="form.delivery_mode = mode.value">
                <i aria-hidden="true" :class="mode.icon" class="w-4 shrink-0 text-center"></i><span class="grid flex-1 gap-0.5"><strong>{{ mode.label }}</strong><small class="text-[0.72rem] font-normal text-ink-3">{{ mode.hint }}</small></span>
              </button>
            </div>
            <BaseDropdown
              v-model="form.seer_identity_mode"
              :options="seerIdentityOptions"
              label="Request as"
              placeholder="Select Seer identity"
              help-text="Choose who Seer credits for these requests. Mapped users fall back to the technical user configured in Connections."
            />
            <div class="mt-4 grid gap-3 md:grid-cols-[repeat(auto-fit,minmax(0,1fr))]">
              <div v-for="type in visibleProfileTypes" :key="type" class="grid gap-2 rounded-ctl border border-edge bg-panel-2 p-4">
                <div class="flex items-center gap-2 text-[0.85rem] font-semibold text-ink"><i aria-hidden="true" :class="type === 'movie' ? 'fas fa-film' : 'fas fa-tv'" class="text-ink-4"></i><span>{{ type === 'movie' ? 'Radarr movie profile' : 'Sonarr TV profile' }}</span></div>
                <BaseDropdown :model-value="form.request_profiles[type].serverId || ''" :options="serverOptions(type)" label="Server" placeholder="Use Seer default" @update:model-value="setRequestServer(type, $event)" />
                <template v-if="form.request_profiles[type].serverId">
                  <BaseDropdown v-model="form.request_profiles[type].profileId" :options="profileOptions(type)" label="Quality profile" placeholder="Select quality profile" />
                  <BaseDropdown v-model="form.request_profiles[type].rootFolder" :options="rootFolderOptions(type)" label="Root folder" placeholder="Select root folder" />
                  <BaseDropdown v-if="type === 'tv' && languageProfileOptions(type).length" v-model="form.request_profiles[type].languageProfileId" :options="languageProfileOptions(type)" label="Language profile" placeholder="Use Sonarr default" />
                </template>
              </div>
            </div>
          </div>

          <div v-if="!oneTime" class="mb-7" data-tour-id="job-modal-schedule">
            <h4>Schedule</h4>
            <SchedulePicker v-model="schedule" />
            <div class="mt-4 grid gap-4">
              <BaseCheckbox
                v-model="form.pause_if_pending_requests"
                label="Pause while Seer requests are pending"
                description="Skip this job when Seer still has requests awaiting approval or denial."
              />
              <div class="ui-label">
                <span>Pause while this job has SuggestArr approvals pending</span>
                <div class="grid gap-2 md:grid-cols-3">
                  <button v-for="mode in approvalPauseModes" :key="mode.value" type="button" :class="choiceClass(form.approval_pause_mode === mode.value)" @click="form.approval_pause_mode = mode.value">
                    <i aria-hidden="true" :class="mode.icon" class="w-4 shrink-0 text-center"></i><span class="grid flex-1 gap-0.5"><strong>{{ mode.label }}</strong><small class="text-[0.72rem] font-normal text-ink-3">{{ mode.hint }}</small></span>
                  </button>
                </div>
              </div>
              <BaseCheckbox
                v-if="!['discover', 'list_import'].includes(form.job_type)"
                v-model="form.prevent_suggestions_if_unwatched"
                label="Pause if suggestions remain unwatched"
                description="Scheduled runs only. Manual Run now remains available."
              />
              <label v-if="!['discover', 'list_import'].includes(form.job_type) && form.prevent_suggestions_if_unwatched" class="ui-label" for="unwatchedDays">
                Days before pausing
                <input id="unwatchedDays" v-model.number="form.unwatched_suggestion_days"
                  class="ui-input" type="number" min="1" required />
              </label>
              <label class="ui-label" for="maxRequestsPerUser">
                Automatic requests per user
                <input id="maxRequestsPerUser" v-model.number="form.max_requests_per_user"
                  class="ui-input" type="number" min="0" max="1000" required />
                <small class="text-xs font-normal text-ink-4">Set 0 for no extra limit. Max Results still caps each run.</small>
              </label>
              <label v-if="form.max_requests_per_user > 0" class="ui-label" for="requestLimitWindowHours">
                Rolling window (hours)
                <input id="requestLimitWindowHours" v-model.number="form.request_limit_window_hours"
                  class="ui-input" type="number" min="1" max="8760" required />
              </label>
            </div>
          </div>

          <!-- Advanced Settings Toggle -->
          <button type="button" class="mt-7 mb-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-ctl border border-dashed border-edge-strong bg-transparent px-4 py-3 text-[0.85rem] font-semibold text-ink-3 hover:border-brand-ink hover:text-brand-ink" data-tour-id="job-modal-advanced-toggle" :aria-expanded="showAdvanced.toString()" @click="showAdvanced = !showAdvanced">
            <i aria-hidden="true" :class="showAdvanced ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" class="text-xs"></i>
            {{ showAdvanced ? 'Hide advanced settings' : 'Show advanced settings' }}
          </button>

          <!-- Advanced Settings (collapsible) -->
          <transition
            enter-active-class="transition-opacity duration-300"
            leave-active-class="transition-opacity duration-300"
            enter-from-class="opacity-0"
            leave-to-class="opacity-0"
          >
            <div v-if="showAdvanced" class="border-t border-edge pt-5 pb-4">
              <!-- Max Results -->
              <div v-if="!oneTime && form.job_type !== 'recommendation'" class="mb-7" data-tour-id="job-modal-max-results">
                <h4>Results</h4>
                <label class="ui-label" for="maxResults">
                  Max results: {{ form.max_results }}
                  <input
                    id="maxResults"
                    v-model.number="form.max_results"
                    type="range"
                    :min="form.job_type === 'list_import' ? 1 : 5"
                    :max="form.job_type === 'list_import' ? 1000 : 100"
                    :step="form.job_type === 'list_import' ? 1 : 5"
                    class="mt-2 w-full accent-brand"
                  />
                  <small class="text-xs font-normal text-ink-4">
                    {{ form.job_type === 'list_import' ? 'Maximum new requests per run' : 'Maximum content to discover per run' }}
                  </small>
                </label>
              </div>

              <!-- Filters: own stacking context so its dropdowns overlap what follows -->
              <div class="relative z-50" data-tour-id="job-modal-filters">
                <h4>{{ form.job_type === 'discover' ? 'Discovery filters' : 'Quality filters' }}</h4>
                <JobFilters
                  v-model="form.filters"
                  :media-type="form.media_type"
                  :job-type="form.job_type"
                />
              </div>
            </div>
          </transition>
        </div>

        <footer class="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-edge bg-panel-2/50 px-6 py-3 max-sm:px-4">
          <button type="button" class="ui-btn" @click="requestClose">Cancel</button>
          <button type="submit" class="ui-btn-primary" :disabled="!isValid || isSaving">
            <i v-if="isSaving" aria-hidden="true" class="fas fa-spinner fa-spin"></i>
            {{ oneTime ? 'Import entire list' : isEditing ? 'Save job' : 'Create job' }}
          </button>
        </footer>
      </form>
      </div>
    </div>
  </Teleport>
  <DryRunResultModal v-if="listPreview" :job="{ name: 'List preview' }" :items="listPreview.items" run-label="" :has-more="listPreview.has_more" :loading-more="listPreviewLoading" @more="previewList(true)" @close="listPreview = null" />
</template>

<script>
import JobFilters from './JobFilters.vue';
import RecommendationFilters from './RecommendationFilters.vue';
import TraktRecommendationFilters from './TraktRecommendationFilters.vue';
import SchedulePicker from './SchedulePicker.vue';
import DryRunResultModal from './DryRunResultModal.vue';
import { jobsApi } from '@/api/jobsApi';
import { listTraktJobUsers } from '@/api/api';
import { waitForAuthReady, useAuth } from '@/composables/useAuth';
import { getJobTypeIcon } from '@/utils/jobTypeVisuals.js';
import axios from 'axios';
import { confirmDialog } from '@/utils/confirmDialog';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import BaseDropdown from '@/components/common/BaseDropdown.vue';

export default {
  name: 'JobModal',
  components: {
    JobFilters,
    RecommendationFilters,
    TraktRecommendationFilters,
    SchedulePicker,
    DryRunResultModal,
    BaseCheckbox,
    BaseDropdown
  },
  props: {
    oneTime: { type: Boolean, default: false },
    job: {
      type: Object,
      default: null
    }
  },
  emits: ['close', 'save'],
  setup() { const { currentUser } = useAuth(); return { currentUser }; },
  data() {
    return {
      // JSON of form + schedule once loading settles; edits are compared against it.
      pristine: null,
      connectedUsers: [],
      form: {
        name: this.oneTime ? 'One-time list import' : '',
        job_type: this.oneTime ? 'list_import' : 'discover',
        media_type: this.oneTime ? 'both' : 'movie',
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
      jobTypes: [
        { value: 'list_import', label: 'Import list', description: 'Public MDBList or Trakt list', icon: 'fas fa-list' },
        { value: 'discover', label: 'Discover', description: 'Find content using TMDb filters', icon: 'fas fa-search' },
        { value: 'recommendation', label: 'Recommendation', description: 'Based on user watch history', icon: 'fas fa-users' },
        { value: 'trakt_recommendations', label: 'Trakt Recommendations', description: 'Personalized lists from Trakt.tv', icon: 'icon-trakt' },
      ],
      mediaTypes: [
        { value: 'movie', label: 'Movies', icon: 'fas fa-film' },
        { value: 'tv', label: 'TV shows', icon: 'fas fa-tv' },
        { value: 'both', label: 'Both', icon: 'fas fa-layer-group' },
      ],
      deliveryModes: [
        { value: 'inherit', label: 'Use global setting', hint: 'Follow Advanced settings', icon: 'fas fa-sliders' },
        { value: 'automatic', label: 'Send automatically', hint: 'Queue for Seer immediately', icon: 'fas fa-paper-plane' },
        { value: 'manual', label: 'Approve first', hint: 'Review in Requests', icon: 'fas fa-user-check' },
      ],
      approvalPauseModes: [
        { value: 'inherit', label: 'Use global setting', hint: 'Follow Advanced settings', icon: 'fas fa-sliders' },
        { value: 'always', label: 'Always pause', hint: "Wait for this job's approvals", icon: 'fas fa-pause' },
        { value: 'never', label: 'Never pause', hint: 'Ignore pending approvals', icon: 'fas fa-play' },
      ],
      llmConfigured: false,
      listProviders: [{ value: 'mdblist', label: 'MDBList' }, { value: 'trakt', label: 'Trakt' }],
      listChecking: false,
      listPreview: null,
      listPreviewLoading: false,
      listCheckMessage: '',
      listCheckSuccess: false,
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
      if (this.form.job_type === 'list_import') {
        return 'Import missing titles from a public list, in list order, using your quality filters and delivery settings.';
      }
      if (this.form.job_type === 'discover') {
        return 'Discover Jobs find content using TMDb filters, independent from user watch history.';
      }
      if (this.form.job_type === 'trakt_recommendations') {
        return 'Trakt Recommendations Jobs fetch personalized movie and show lists only from a linked Trakt account.';
      }
      return 'Recommendation Jobs find similar content based on what your users have watched on your media server or Trakt.tv.';
    },
    jobNamePlaceholder() {
      if (this.form.job_type === 'list_import') return 'e.g., Weekly MDBList Movies';
      if (this.form.job_type === 'discover') return 'e.g., Popular Movies 2024';
      if (this.form.job_type === 'trakt_recommendations') return 'e.g., Weekly Trakt Picks';
      return 'e.g., Weekly Recommendations';
    },
    isValid() {
      if (this.form.job_type === 'list_import' && (!this.form.filters.list_provider || !this.form.filters.list_url?.trim())) return false;
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
    this.pristine = this.snapshot();
    document.addEventListener('keydown', this.onKeydown);
  },
  beforeUnmount() {
    document.removeEventListener('keydown', this.onKeydown);
  },
  methods: {
    snapshot() {
      return JSON.stringify({ form: this.form, schedule: this.schedule });
    },

    // Backdrop, Escape, the close button and Cancel all ask before throwing away edits.
    async requestClose() {
      const dirty = this.pristine !== null && this.snapshot() !== this.pristine;
      if (dirty && !(await confirmDialog({
        title: 'Discard your changes?',
        message: 'This job has unsaved changes.',
        confirmLabel: 'Discard',
        cancelLabel: 'Keep editing',
        danger: true,
      }))) return;
      this.$emit('close');
    },

    onKeydown(event) {
      // A native dialog on top (list preview, confirmation) handles its own Escape.
      if (event.key !== 'Escape' || document.querySelector('dialog[open]')) return;
      event.preventDefault();
      this.requestClose();
    },

    listConfig() {
      return {
        filters: this.form.filters,
        media_type: this.form.media_type,
        delivery_mode: this.form.delivery_mode,
        seer_identity_mode: this.form.seer_identity_mode,
        request_profiles: Object.fromEntries(Object.entries(this.form.request_profiles).map(([type, profile]) => [type,
          profile.serverId !== '' && profile.serverId != null && profile.profileId !== '' && profile.profileId != null && profile.rootFolder ? {
            serverId: Number(profile.serverId), profileId: Number(profile.profileId), rootFolder: profile.rootFolder,
            is4k: profile.is4k === true,
            ...(profile.languageProfileId !== '' && profile.languageProfileId != null ? { languageProfileId: Number(profile.languageProfileId) } : {})
          } : {}
        ]))
      };
    },
    async previewList(more = false) {
      this.listPreviewLoading = true;
      this.listCheckMessage = '';
      const config = JSON.parse(JSON.stringify(this.listConfig()));
      try {
        const response = await jobsApi.previewList(config, more ? this.listPreview.next_offset : 0);
        if (JSON.stringify(config) !== JSON.stringify(this.listConfig())) return;
        const previous = more && this.listPreview ? this.listPreview.items : [];
        const items = [...new Map([...previous, ...(response.items || [])].map(item => [`${item.media_type}:${item.tmdb_id}`, item])).values()];
        this.listPreview = { ...response, items };
      } catch (error) {
        this.listCheckSuccess = false;
        this.listCheckMessage = error.response?.data?.message || 'Could not preview the list.';
        this.listPreview = null;
      } finally {
        this.listPreviewLoading = false;
      }
    },
    async verifyList() {
      const source = { list_provider: this.form.filters.list_provider, list_url: this.form.filters.list_url };
      this.listChecking = true;
      this.listCheckMessage = '';
      try {
        const response = await jobsApi.verifyList(source);
        if (source.list_url !== this.form.filters.list_url || source.list_provider !== this.form.filters.list_provider) return;
        this.listCheckSuccess = true;
        this.listCheckMessage = `Public list: ${response.data.name}`;
      } catch (error) {
        if (source.list_url !== this.form.filters.list_url || source.list_provider !== this.form.filters.list_provider) return;
        this.listCheckSuccess = false;
        this.listCheckMessage = error.response?.data?.message || 'Could not verify the list.';
      } finally {
        this.listChecking = false;
      }
    },
    // Selectable option tile used by every choice group in this modal.
    choiceClass(active) {
      return [
        'flex cursor-pointer items-center gap-3 rounded-ctl border px-3.5 py-3 text-left text-[0.85rem] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-45',
        active
          ? 'border-brand bg-brand-soft text-ink [&>i]:text-brand-ink'
          : 'border-edge-strong bg-panel-2 text-ink-2 hover:enabled:border-ink-4 hover:enabled:text-ink [&>i]:text-ink-4',
      ];
    },
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
      this.listCheckMessage = '';
      if (['discover', 'list_import'].includes(jobType)) {
        this.form.user_ids = [];
        this.form.prevent_suggestions_if_unwatched = false;
      }
    },
    async handleSubmit() {
      if (!this.isValid) return;

      if (this.oneTime) {
        this.$emit('save', this.listConfig());
        return;
      }

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
