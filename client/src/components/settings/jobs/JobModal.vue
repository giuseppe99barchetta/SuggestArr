<template>
  <!-- Not AppDialog: a native modal <dialog> would make the jobs tour, which highlights fields in here, inert. -->
  <Teleport to="body">
    <div class="fixed inset-0 z-[1050] flex bg-black/70 p-4 backdrop-blur-sm max-sm:p-2" @click.self="requestClose">
      <div role="dialog" aria-modal="true" aria-labelledby="job-modal-title" class="m-auto flex max-h-full sm:max-h-[min(80dvh,52rem)] w-full max-w-4xl flex-col overflow-hidden rounded-card border border-edge bg-panel text-ink shadow-2xl">
      <header class="flex shrink-0 items-start gap-3 border-b border-edge px-6 py-4 max-sm:px-4">
        <span aria-hidden="true" class="grid h-9 w-9 shrink-0 place-items-center rounded-ctl bg-brand-soft text-sm text-brand-ink"><i aria-hidden="true" :class="jobTypeInfoIcon"></i></span>
        <div class="min-w-0 flex-1 self-center">
          <h2 id="job-modal-title" class="m-0 text-base font-bold text-ink">{{ oneTime ? 'Import list once' : isEditing ? 'Edit job' : 'New job' }}</h2>
          <p class="m-0 mt-0.5 truncate text-[13px] text-ink-3">{{ oneTime ? 'Import all matching titles without creating a scheduled job.' : isEditing ? form.name : 'Pick what to look for, when, and how it reaches Seer.' }}</p>
        </div>
        <button type="button" class="-mr-2 grid h-9 w-9 shrink-0 cursor-pointer place-items-center rounded-[8px] border-0 bg-transparent text-ink-3 hover:bg-raised hover:text-ink" aria-label="Close" @click="requestClose">
          <i aria-hidden="true" class="fas fa-times"></i>
        </button>
      </header>

      <form @submit.prevent="handleSubmit" class="flex min-h-0 flex-1 flex-col">
        <div class="flex min-h-0 flex-1">
          <!-- Section index with a one-line summary of each step (desktop only). -->
          <nav aria-label="Job sections" class="hidden w-56 shrink-0 flex-col gap-1 border-r border-edge bg-panel-2/40 p-3 md:flex">
            <button
              v-for="(section, index) in sections"
              :key="section.id"
              type="button"
              class="flex cursor-pointer items-start gap-3 rounded-ctl border-0 px-3 py-2.5 text-left transition-colors"
              :class="activeSection === section.id ? 'bg-brand-soft' : 'bg-transparent hover:bg-raised'"
              :aria-current="activeSection === section.id ? 'step' : null"
              @click="scrollToSection(section.id)"
            >
              <span class="mt-px grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px] font-bold" :class="activeSection === section.id ? 'bg-brand text-white' : 'bg-raised text-ink-3'">{{ index + 1 }}</span>
              <span class="flex min-w-0 flex-col">
                <span class="text-[13px] font-semibold" :class="activeSection === section.id ? 'text-ink' : 'text-ink-2'">{{ section.title }}</span>
                <span class="truncate text-xs text-ink-4">{{ section.summary }}</span>
              </span>
            </button>
          </nav>

          <div ref="body" class="min-h-0 flex-1 overflow-y-auto px-6 pb-8 max-sm:px-4" @scroll="updateActiveSection">
            <!-- 1. Source -->
            <section data-section="source" :class="sectionClass">
              <h3 :class="sectionTitleClass"><span :class="sectionNumberClass">1</span>{{ oneTime ? 'List' : 'What to look for' }}</h3>

              <div v-if="!oneTime" class="mb-6" data-tour-id="job-modal-type-selector">
                <div :class="fieldLabelClass">
                  <span>Job type</span>
                  <InfoTip v-if="isEditing" text="The type sets how the job finds titles, so it can't be changed later. Create a new job to use a different type." />
                </div>
                <div v-if="isEditing" class="flex items-center gap-3 rounded-ctl border border-edge-strong bg-panel-2 px-3.5 py-3">
                  <i aria-hidden="true" :class="jobTypeInfoIcon" class="w-5 text-center text-brand-ink"></i>
                  <span class="flex min-w-0 flex-col gap-0.5">
                    <span class="text-[0.85rem] font-semibold text-ink">{{ currentJobType.label }}</span>
                    <span class="text-xs text-ink-3">{{ jobTypeInfoText }}</span>
                  </span>
                </div>
                <template v-else>
                  <div class="grid gap-2 sm:grid-cols-2">
                    <button
                      v-for="type in jobTypes"
                      :key="type.value"
                      type="button"
                      :class="choiceClass(form.job_type === type.value)"
                      :disabled="type.value === 'trakt_recommendations' && !traktJobAvailable"
                      :title="type.value === 'trakt_recommendations' ? traktJobUnavailableReason : null"
                      :aria-pressed="form.job_type === type.value ? 'true' : 'false'"
                      @click="setJobType(type.value)"
                    >
                      <i aria-hidden="true" :class="type.icon" class="w-5 text-center"></i>
                      <span class="flex min-w-0 flex-col gap-0.5">
                        <span>{{ type.label }}</span>
                        <span class="text-[0.72rem] font-normal text-ink-3">{{ type.description }}</span>
                      </span>
                    </button>
                  </div>
                  <p class="m-0 mt-2 text-xs text-ink-4">{{ jobTypeInfoText }}</p>
                  <p v-if="!traktJobAvailable" class="m-0 mt-1 flex items-start gap-1.5 text-xs text-ink-4" role="status">
                    <i aria-hidden="true" class="fas fa-circle-info mt-0.5 text-brand-ink"></i>
                    <span>{{ traktJobUnavailableReason }}</span>
                  </p>
                </template>
              </div>

              <!-- Where titles come from, per job type -->
              <div v-if="form.job_type === 'list_import'" class="mb-6 grid gap-3" data-testid="public-list-source">
                <div class="grid gap-3 sm:grid-cols-[12rem_minmax(0,1fr)]">
                  <label class="ui-label">Provider
                    <select v-model="form.filters.list_provider" class="ui-input" @change="listCheckMessage = ''">
                      <option :value="undefined" disabled>Select provider</option>
                      <option v-for="option in listProviders" :key="option.value" :value="option.value">{{ option.label }}</option>
                    </select>
                  </label>
                  <label class="ui-label" for="listUrl">List URL
                    <input id="listUrl" v-model="form.filters.list_url" type="url" required class="ui-input" placeholder="https://mdblist.com/lists/username/list-name" @input="listCheckMessage = ''" />
                  </label>
                </div>
                <p class="m-0 text-xs text-ink-4">{{ oneTime ? 'All matching titles are checked and queued in the background. Titles already in your library, requested or queued are skipped.' : 'Public lists only. Titles are imported gradually, in list order, skipping what you already have or requested.' }}</p>
                <div class="flex flex-wrap items-center gap-3">
                  <button type="button" class="ui-btn" :disabled="listChecking || !form.filters.list_provider || !form.filters.list_url" @click="verifyList">{{ listChecking ? 'Checking…' : 'Verify list' }}</button>
                  <button type="button" class="ui-btn" :disabled="listPreviewLoading || !form.filters.list_provider || !form.filters.list_url" @click="previewList()"><i aria-hidden="true" :class="listPreviewLoading ? 'fas fa-spinner fa-spin' : 'fas fa-eye'"></i>{{ listPreviewLoading ? 'Loading…' : 'Preview list' }}</button>
                  <span v-if="listCheckMessage" role="status" class="min-w-0 break-words text-sm" :class="listCheckSuccess ? 'text-good' : 'text-bad'">{{ listCheckMessage }}</span>
                </div>
              </div>

              <div v-if="form.job_type === 'recommendation'" class="mb-6">
                <div :class="fieldLabelClass">
                  <span>Users to monitor</span>
                  <InfoTip text="Suggestions are based on what these users watched on your media server." />
                </div>
                <RecommendationUsers v-model="form" />
              </div>

              <div v-if="form.job_type === 'trakt_recommendations'" class="mb-6">
                <div :class="fieldLabelClass">
                  <span>Trakt account</span>
                  <InfoTip text="The media user whose linked Trakt recommendations this job fetches." />
                </div>
                <TraktRecommendationFilters
                  v-model="form"
                  :trakt-configured="traktConfigured"
                  :connected-users="connectedUsers"
                  :is-loading="traktLoading"
                />
              </div>

              <div class="grid gap-4 sm:grid-cols-2" data-tour-id="job-modal-basic-info">
                <div class="ui-label">
                  <span>Media type</span>
                  <div role="group" aria-label="Media type" class="flex rounded-ctl border border-edge-strong bg-canvas p-1">
                    <button
                      v-for="type in visibleMediaTypes"
                      :key="type.value"
                      type="button"
                      class="flex h-[32px] flex-1 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-[8px] border-0 px-2 text-[13px] font-semibold transition-colors"
                      :class="form.media_type === type.value ? 'bg-brand text-white' : 'bg-transparent text-ink-3 hover:text-ink'"
                      :aria-pressed="form.media_type === type.value ? 'true' : 'false'"
                      @click="form.media_type = type.value"
                    >
                      <i aria-hidden="true" :class="type.icon"></i>
                      {{ type.label }}
                    </button>
                  </div>
                </div>

                <div v-if="!oneTime" class="flex flex-col gap-1.5">
                  <div class="flex items-center gap-1.5 text-[13px] font-semibold text-ink-2">
                    <label for="jobName">Name</label>
                    <InfoTip text="Shown in the job list and history. Leave it empty to use the suggested name." />
                  </div>
                  <input
                    id="jobName"
                    v-model="form.name"
                    type="text"
                    :placeholder="autoName"
                    class="ui-input"
                  />
                </div>
              </div>
            </section>

            <!-- 2. Filters -->
            <section data-section="filters" :class="sectionClass" data-tour-id="job-modal-filters">
              <h3 :class="sectionTitleClass"><span :class="sectionNumberClass">2</span>Filters</h3>

              <div v-if="usesExclusions" class="mb-6">
                <div :class="fieldLabelClass">
                  <span>Skip titles that are</span>
                </div>
                <div class="flex flex-wrap gap-x-6 gap-y-2">
                  <div class="flex items-center gap-1.5">
                    <BaseCheckbox v-model="excludeDownloaded" label="Already in your library" />
                    <InfoTip text="Titles your media server already has are never requested again." />
                  </div>
                  <div class="flex items-center gap-1.5">
                    <BaseCheckbox v-model="excludeRequested" label="Already requested in Seer" />
                    <InfoTip text="Titles with an existing Seer request, from anyone, are skipped." />
                  </div>
                </div>
              </div>

              <div v-if="form.job_type === 'recommendation'" class="mb-6">
                <div :class="fieldLabelClass"><span>Recommendation tuning</span></div>
                <RecommendationFilters v-model="form" :llm-configured="llmConfigured" />
              </div>

              <!-- Filters: own stacking context so its dropdowns overlap what follows -->
              <div v-if="form.job_type === 'discover'" class="relative z-50">
                <JobFilters v-model="form.filters" :media-type="form.media_type" :job-type="form.job_type" />
              </div>
              <template v-else>
                <button type="button" :class="disclosureClass" :aria-expanded="qualityOpen.toString()" aria-controls="job-quality-filters" @click="qualityOpen = !qualityOpen">
                  <span class="flex min-w-0 flex-col items-start gap-0.5">
                    <span class="text-[13px] font-semibold text-ink">Quality filters</span>
                    <span class="text-xs font-normal text-ink-4">Rating, votes, runtime, release date, language, genres and streaming services.</span>
                  </span>
                  <i aria-hidden="true" class="fas fa-chevron-down ml-auto text-xs text-ink-4 transition-transform" :class="{ 'rotate-180': qualityOpen }"></i>
                </button>
                <div v-if="qualityOpen" id="job-quality-filters" class="relative z-50 mt-4">
                  <JobFilters v-model="form.filters" :media-type="form.media_type" :job-type="form.job_type" />
                </div>
              </template>
            </section>

            <!-- 3. Schedule -->
            <section v-if="!oneTime" data-section="schedule" :class="sectionClass" data-tour-id="job-modal-schedule">
              <h3 :class="sectionTitleClass"><span :class="sectionNumberClass">3</span>Schedule</h3>
              <SchedulePicker v-model="schedule" />

              <div class="mt-6">
                <div :class="fieldLabelClass">
                  <span>Skip a scheduled run when…</span>
                  <InfoTip text="Pause rules only affect scheduled runs. “Run now” always works." />
                </div>
                <div class="flex flex-col divide-y divide-edge rounded-ctl border border-edge">
                  <div class="flex items-center gap-1.5 px-4 py-3">
                    <BaseCheckbox v-model="form.pause_if_pending_requests" label="Seer still has requests waiting for approval" />
                    <InfoTip text="Avoids piling up new requests while Seer admins haven't reviewed the previous ones." />
                  </div>

                  <div class="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
                    <div class="flex min-w-0 flex-1 items-center gap-1.5 text-sm text-ink">
                      <span id="approval-pause-label">This job has suggestions waiting in Requests</span>
                      <InfoTip text="Suggestions held for your approval in SuggestArr's Requests page (when delivery is “Approve first”)." />
                    </div>
                    <div role="radiogroup" aria-labelledby="approval-pause-label" class="flex rounded-ctl border border-edge-strong bg-canvas p-1">
                      <button
                        v-for="mode in approvalPauseModes"
                        :key="mode.value"
                        type="button"
                        role="radio"
                        :aria-checked="form.approval_pause_mode === mode.value"
                        :title="mode.hint"
                        class="cursor-pointer rounded-[8px] border-0 px-3 py-1.5 text-xs font-semibold transition-colors"
                        :class="form.approval_pause_mode === mode.value ? 'bg-brand text-white' : 'bg-transparent text-ink-3 hover:text-ink'"
                        @click="form.approval_pause_mode = mode.value"
                      >{{ mode.label }}</button>
                    </div>
                  </div>

                  <div v-if="!['discover', 'list_import'].includes(form.job_type)" class="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
                    <div class="flex min-w-0 flex-1 items-center gap-1.5">
                      <BaseCheckbox v-model="form.prevent_suggestions_if_unwatched" label="Pause if suggestions remain unwatched" />
                      <InfoTip text="Waits until people actually watch what was suggested before adding more." />
                    </div>
                    <label v-if="form.prevent_suggestions_if_unwatched" class="flex items-center gap-2 text-[13px] text-ink-3" for="unwatchedDays">
                      for
                      <input id="unwatchedDays" v-model.number="form.unwatched_suggestion_days" class="ui-input h-9! w-20" type="number" min="1" required />
                      days
                    </label>
                  </div>
                </div>
              </div>
            </section>

            <!-- 4. Requests -->
            <section data-section="requests" :class="sectionClass" data-tour-id="job-modal-requests">
              <h3 :class="sectionTitleClass"><span :class="sectionNumberClass">{{ oneTime ? 3 : 4 }}</span>Requests</h3>

              <div class="mb-6">
                <div :class="fieldLabelClass">
                  <span>Delivery</span>
                  <InfoTip text="“Approve first” holds suggestions in the Requests page until you accept them. “Send automatically” requests them in Seer straight away." />
                </div>
                <div class="grid gap-2 sm:grid-cols-3">
                  <button v-for="mode in deliveryModes" :key="mode.value" type="button" :class="choiceClass(form.delivery_mode === mode.value)" :aria-pressed="form.delivery_mode === mode.value ? 'true' : 'false'" @click="form.delivery_mode = mode.value">
                    <i aria-hidden="true" :class="mode.icon" class="w-4 shrink-0 text-center"></i><span class="grid flex-1 gap-0.5"><strong>{{ mode.label }}</strong><small class="text-[0.72rem] font-normal text-ink-3">{{ mode.hint }}</small></span>
                  </button>
                </div>
              </div>

              <div class="mb-6">
                <label class="ui-label">Request as
                  <select v-model="form.seer_identity_mode" class="ui-input">
                    <option v-for="option in seerIdentityOptions" :key="option.value" :value="option.value" :disabled="option.disabled">{{ option.label }}</option>
                  </select>
                  <span v-if="seerIdentityHelp" class="text-xs font-normal text-ink-4">{{ seerIdentityHelp }}</span>
                </label>
              </div>

              <div v-if="!oneTime" class="mb-6" data-tour-id="job-modal-max-results">
                <div :class="fieldLabelClass"><span>Limits</span></div>
                <div class="grid gap-4 sm:grid-cols-3">
                  <div class="flex flex-col gap-1.5">
                    <div class="flex items-center gap-1.5 text-[13px] font-semibold text-ink-2">
                      <label for="maxResults">Per run</label>
                      <InfoTip :text="maxResultsHelp" />
                    </div>
                    <input id="maxResults" v-model.number="form.max_results" class="ui-input" type="number" min="1" :max="maxResultsLimit" required />
                  </div>
                  <div class="flex flex-col gap-1.5">
                    <div class="flex items-center gap-1.5 text-[13px] font-semibold text-ink-2">
                      <label for="maxRequestsPerUser">Per user</label>
                      <InfoTip text="Most automatic requests credited to one Seer user within the window. 0 means no extra limit; the per-run limit still applies." />
                    </div>
                    <input id="maxRequestsPerUser" v-model.number="form.max_requests_per_user" class="ui-input" type="number" min="0" max="1000" required />
                  </div>
                  <div v-if="form.max_requests_per_user > 0" class="flex flex-col gap-1.5">
                    <div class="flex items-center gap-1.5 text-[13px] font-semibold text-ink-2">
                      <label for="requestLimitWindowHours">Window (hours)</label>
                      <InfoTip text="The per-user limit counts requests made in this many past hours, e.g. 24 for a daily cap or 168 for a weekly one." />
                    </div>
                    <input id="requestLimitWindowHours" v-model.number="form.request_limit_window_hours" class="ui-input" type="number" min="1" max="8760" required />
                  </div>
                </div>
              </div>

              <button type="button" :class="disclosureClass" :aria-expanded="profilesOpen.toString()" aria-controls="job-request-profiles" @click="profilesOpen = !profilesOpen">
                <span class="flex min-w-0 flex-col items-start gap-0.5">
                  <span class="text-[13px] font-semibold text-ink">Radarr / Sonarr overrides</span>
                  <span class="text-xs font-normal text-ink-4">{{ profilesSummary }}</span>
                </span>
                <i aria-hidden="true" class="fas fa-chevron-down ml-auto text-xs text-ink-4 transition-transform" :class="{ 'rotate-180': profilesOpen }"></i>
              </button>
              <div v-if="profilesOpen" id="job-request-profiles" class="mt-4 grid gap-3 md:grid-cols-[repeat(auto-fit,minmax(0,1fr))]">
                <div v-for="type in visibleProfileTypes" :key="type" class="grid gap-2 rounded-ctl border border-edge bg-panel-2 p-4">
                  <div class="flex items-center gap-2 text-[0.85rem] font-semibold text-ink"><i aria-hidden="true" :class="type === 'movie' ? 'fas fa-film' : 'fas fa-tv'" class="text-ink-4"></i><span>{{ type === 'movie' ? 'Radarr movie profile' : 'Sonarr TV profile' }}</span></div>
                  <label class="ui-label">Server
                    <select :value="form.request_profiles[type].serverId ?? ''" class="ui-input" @change="setRequestServer(type, $event.target.value)">
                      <option value="">Use Seer default</option>
                      <option v-for="option in serverOptions(type)" :key="option.value" :value="option.value">{{ option.label }}</option>
                    </select>
                  </label>
                  <template v-if="form.request_profiles[type].serverId">
                    <label class="ui-label">Quality profile
                      <select v-model="form.request_profiles[type].profileId" class="ui-input">
                        <option value="" disabled>Select quality profile</option>
                        <option v-for="option in profileOptions(type)" :key="option.value" :value="option.value">{{ option.label }}</option>
                      </select>
                    </label>
                    <label class="ui-label">Root folder
                      <select v-model="form.request_profiles[type].rootFolder" class="ui-input">
                        <option value="" disabled>Select root folder</option>
                        <option v-for="option in rootFolderOptions(type)" :key="option.value" :value="option.value">{{ option.label }}</option>
                      </select>
                    </label>
                    <label v-if="type === 'tv' && languageProfileOptions(type).length" class="ui-label">Language profile
                      <select v-model="form.request_profiles[type].languageProfileId" class="ui-input">
                        <option value="">Use Sonarr default</option>
                        <option v-for="option in languageProfileOptions(type)" :key="option.value" :value="option.value">{{ option.label }}</option>
                      </select>
                    </label>
                  </template>
                </div>
              </div>
            </section>
          </div>
        </div>

        <footer class="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-edge bg-panel-2/50 px-6 py-3 max-sm:px-4">
          <p v-if="validationMessage" class="m-0 mr-auto flex min-w-0 items-center gap-1.5 text-xs text-caution" role="status">
            <i aria-hidden="true" class="fas fa-circle-exclamation"></i>{{ validationMessage }}
          </p>
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
import RecommendationUsers from './RecommendationUsers.vue';
import TraktRecommendationFilters from './TraktRecommendationFilters.vue';
import SchedulePicker from './SchedulePicker.vue';
import DryRunResultModal from './DryRunResultModal.vue';
import { jobsApi } from '@/api/jobsApi';
import { listTraktJobUsers } from '@/api/api';
import { waitForAuthReady, useAuth } from '@/composables/useAuth';
import { getJobTypeIcon, formatJobSchedule } from '@/utils/jobTypeVisuals.js';
import { jobRequiresApproval } from '@/utils/requestApproval.js';
import axios from 'axios';
import { confirmDialog } from '@/utils/confirmDialog';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import InfoTip from '@/components/ui/InfoTip.vue';

export default {
  name: 'JobModal',
  components: {
    JobFilters,
    RecommendationFilters,
    RecommendationUsers,
    TraktRecommendationFilters,
    SchedulePicker,
    DryRunResultModal,
    BaseCheckbox,
    InfoTip
  },
  props: {
    oneTime: { type: Boolean, default: false },
    job: {
      type: Object,
      default: null
    },
    /** Global REQUIRE_REQUEST_APPROVAL, shown on the "Use global setting" delivery option; null when unknown. */
    requestApprovalDefault: { type: [Boolean, String], default: null },
    /** Global PAUSE_JOBS_WITH_PENDING_APPROVALS, shown on the "Global" pause option; null when unknown. */
    approvalPauseDefault: { type: Boolean, default: null }
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
        unwatched_suggestion_days: 7,
        max_requests_per_user: 0,
        request_limit_window_hours: 24,
        delivery_mode: 'inherit',
        approval_pause_mode: 'inherit',
        seer_identity_mode: 'technical_user',
        request_profiles: { movie: {}, tv: {} }
      },
      schedule: {
        type: 'preset',
        value: 'daily'
      },
      isSaving: false,
      qualityOpen: false,
      profilesOpen: false,
      activeSection: 'source',
      sectionClass: 'scroll-mt-2 border-b border-edge py-7 last:border-b-0',
      sectionTitleClass: 'm-0 mb-5 flex items-center gap-2.5 text-[15px] font-bold text-ink',
      sectionNumberClass: 'grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand-soft text-xs font-bold text-brand-ink',
      fieldLabelClass: 'mb-2 flex items-center gap-1.5 text-[13px] font-semibold text-ink-2',
      disclosureClass: 'flex w-full cursor-pointer items-center gap-3 rounded-ctl border border-edge-strong bg-panel-2 px-4 py-3 text-left hover:border-ink-4',
      jobTypes: [
        { value: 'list_import', label: 'Import list', description: 'Public MDBList or Trakt list', icon: 'fas fa-list' },
        { value: 'discover', label: 'Discover', description: 'Find content using TMDb filters', icon: 'fas fa-search' },
        { value: 'recommendation', label: 'Recommendation', description: 'Based on user watch history', icon: 'fas fa-users' },
        { value: 'trakt_recommendations', label: 'Trakt Recommendations', description: 'Personalized lists from Trakt.tv', icon: 'icon-trakt' },
      ],
      mediaTypes: [
        { value: 'movie', label: 'Movies', icon: 'fas fa-film' },
        { value: 'tv', label: 'TV', icon: 'fas fa-tv' },
        { value: 'both', label: 'Both', icon: 'fas fa-layer-group' },
      ],
      llmConfigured: false,
      listProviders: [{ value: 'mdblist', label: 'MDBList' }, { value: 'trakt', label: 'Trakt' }],
      listChecking: false,
      listPreview: null,
      listPreviewLoading: false,
      listCheckMessage: '',
      listCheckSuccess: false,
      traktConfigured: false,
      traktLoading: false,
      radarrServers: [],
      sonarrServers: []
    };
  },
  computed: {
    seerIdentityOptions() {
      const options = [
        { value: 'technical_user', label: 'Technical user' },
        { value: 'matching_user', label: 'Matching Seer user' }
      ];
      if (this.currentUser?.role === 'admin') options.push({ value: 'admin_user', label: 'Seer admin' });
      return options;
    },
    seerIdentityHelp() {
      if (this.form.seer_identity_mode === 'matching_user') {
        return 'Each request is credited to the Seer account linked to the user it is for. Users without one fall back to the technical user.';
      }
      if (this.form.seer_identity_mode === 'admin_user') {
        return 'Requests are made as your linked Seer admin account.';
      }
      return 'Requests are made as the Seer user configured in Connections.';
    },
    deliveryModes() {
      const global = this.requestApprovalDefault === null ? null : jobRequiresApproval({ delivery_mode: 'inherit' }, this.requestApprovalDefault);
      return [
        { value: 'inherit', label: 'Use global setting', hint: global === null ? 'Follow Advanced settings' : global ? 'Currently: approval required' : 'Currently: sent automatically', icon: 'fas fa-sliders' },
        { value: 'automatic', label: 'Send automatically', hint: 'Request in Seer right away', icon: 'fas fa-paper-plane' },
        { value: 'manual', label: 'Approve first', hint: 'Review in Requests', icon: 'fas fa-user-check' },
      ];
    },
    approvalPauseModes() {
      const global = this.approvalPauseDefault === null ? '' : ` (${this.approvalPauseDefault ? 'on' : 'off'})`;
      return [
        { value: 'inherit', label: `Global${global}`, hint: 'Follow the setting in Advanced' },
        { value: 'always', label: 'Always', hint: "Wait until this job's suggestions are reviewed" },
        { value: 'never', label: 'Never', hint: 'Ignore pending approvals' },
      ];
    },
    currentJobType() {
      return this.jobTypes.find(type => type.value === this.form.job_type) || this.jobTypes[0];
    },
    visibleMediaTypes() {
      return this.mediaTypes.filter(type => type.value !== 'both' || this.form.job_type !== 'discover');
    },
    mediaLabel() {
      return this.mediaTypes.find(type => type.value === this.form.media_type)?.label || '';
    },
    autoName() {
      return `${this.currentJobType.label} · ${this.mediaLabel}`;
    },
    usesExclusions() {
      return ['recommendation', 'trakt_recommendations'].includes(this.form.job_type);
    },
    // Unset means the job follows the global EXCLUDE_* settings, which default to on.
    excludeDownloaded: {
      get() { return this.form.filters.exclude_downloaded ?? true; },
      set(value) { this.form.filters = { ...this.form.filters, exclude_downloaded: value }; }
    },
    excludeRequested: {
      get() { return this.form.filters.exclude_requested ?? true; },
      set(value) { this.form.filters = { ...this.form.filters, exclude_requested: value }; }
    },
    maxResultsLimit() {
      return this.form.job_type === 'list_import' ? 1000 : 100;
    },
    maxResultsHelp() {
      if (this.form.job_type === 'list_import') return 'Most new titles requested from the list each run (1–1000).';
      if (this.form.job_type === 'discover') return 'Most titles discovered and requested each run (1–100).';
      return 'Most suggestions requested each run, across all monitored users (1–100).';
    },
    profilesSummary() {
      const set = this.visibleProfileTypes.filter(type => this.form.request_profiles[type]?.serverId);
      if (!set.length) return "Using Seer's default server, quality profile and root folder.";
      return `Custom ${set.map(type => (type === 'movie' ? 'Radarr' : 'Sonarr')).join(' and ')} profile.`;
    },
    sections() {
      const delivery = { inherit: 'Global delivery', automatic: 'Automatic', manual: 'Approve first' }[this.form.delivery_mode] || '';
      const sections = [
        { id: 'source', title: this.oneTime ? 'List' : 'What to look for', summary: this.oneTime ? this.mediaLabel : this.autoName },
        { id: 'filters', title: 'Filters', summary: this.form.job_type === 'discover' ? 'TMDb discovery filters' : this.form.job_type === 'recommendation' ? 'Tuning and quality' : 'Quality filters' },
      ];
      if (!this.oneTime) {
        sections.push({ id: 'schedule', title: 'Schedule', summary: formatJobSchedule({ schedule_type: this.schedule.type, schedule_value: this.schedule.value }) });
      }
      sections.push({ id: 'requests', title: 'Requests', summary: this.oneTime ? delivery : `${delivery} · ${this.form.max_results || 0} per run` });
      return sections;
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
    validationMessage() {
      if (this.form.job_type === 'list_import' && !this.form.filters.list_provider) return 'Choose a list provider.';
      if (this.form.job_type === 'list_import' && !this.form.filters.list_url?.trim()) return 'Enter the URL of the public list.';
      if (this.form.job_type === 'trakt_recommendations' && (this.form.user_ids || []).length !== 1) return 'Choose the Trakt account to use.';
      if (!this.form.media_type) return 'Choose a media type.';
      if (!this.oneTime && !(this.form.max_results >= 1 && this.form.max_results <= this.maxResultsLimit)) return `Requests per run must be between 1 and ${this.maxResultsLimit}.`;
      if (this.form.prevent_suggestions_if_unwatched && !(this.form.unwatched_suggestion_days >= 1)) return 'Days before pausing must be at least 1.';
      if (!(this.form.max_requests_per_user >= 0 && this.form.max_requests_per_user <= 1000)) return 'Per-user limit must be between 0 and 1000.';
      if (!(this.form.request_limit_window_hours >= 1 && this.form.request_limit_window_hours <= 8760)) return 'Limit window must be between 1 and 8760 hours.';
      return '';
    },
    isValid() {
      return !this.validationMessage;
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
        unwatched_suggestion_days: this.job.unwatched_suggestion_days || 7,
        max_requests_per_user: this.job.max_requests_per_user || 0,
        request_limit_window_hours: this.job.request_limit_window_hours || 24,
        delivery_mode: this.job.delivery_mode || 'automatic',
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
      this.profilesOpen = Object.values(this.form.request_profiles).some(profile => profile.serverId);
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
    scrollToSection(id) {
      this.$refs.body?.querySelector(`[data-section="${id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },

    // Highlights the last section whose heading has scrolled past the top of the body.
    updateActiveSection() {
      const body = this.$refs.body;
      if (!body) return;
      const nodes = [...body.querySelectorAll('[data-section]')];
      const atBottom = body.scrollTop + body.clientHeight >= body.scrollHeight - 4;
      const top = body.getBoundingClientRect().top + 80;
      const current = atBottom ? nodes[nodes.length - 1] : nodes.filter(node => node.getBoundingClientRect().top <= top).pop();
      this.activeSection = (current || nodes[0])?.dataset.section || 'source';
    },

    // Used by the jobs tour so its steps can point at collapsed parts.
    expandAll() {
      this.qualityOpen = true;
      this.profilesOpen = true;
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
      if (!this.form.name.trim()) this.form.name = this.autoName;

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
