<template>
  <div class="flex flex-col gap-7">
    <header class="flex flex-wrap items-end justify-between gap-4" data-tour-id="jobs-section-header">
      <div>
        <h1 class="m-0 text-3xl font-extrabold tracking-tight text-ink">Jobs</h1>
        <p class="m-0 mt-1.5 max-w-2xl text-[15px] text-ink-3">Discover titles, find recommendations or import a public list. Each job runs on its own schedule and sends requests to Seer.</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button type="button" class="h-[42px] w-[42px] cursor-pointer rounded-ctl border border-edge-strong bg-panel-2 text-ink-3 hover:text-ink" title="Replay the Jobs tour" aria-label="Replay the Jobs tour" @click="restartJobsTour"><i aria-hidden="true" class="fas fa-question-circle"></i></button>
        <button type="button" class="h-[42px] w-[42px] cursor-pointer rounded-ctl border border-edge-strong bg-panel-2 text-ink-3 hover:text-ink disabled:opacity-50" :disabled="isLoading" title="Refresh" aria-label="Refresh" @click="loadJobs"><i aria-hidden="true" :class="isLoading ? 'fas fa-spinner fa-spin' : 'fas fa-sync'"></i></button>
        <button type="button" class="ui-btn h-[42px]" :disabled="importStarting || ['queued', 'running'].includes(listImport?.status)" @click="showImportModal = true"><i aria-hidden="true" class="fas fa-list"></i>Import list once</button>
        <button type="button" class="ui-btn-primary h-[42px] px-[18px]" data-tour-id="jobs-new-btn" @click="showCreateModal = true"><i aria-hidden="true" class="fas fa-plus"></i>New job</button>
      </div>
    </header>

    <section v-if="listImport" class="flex flex-wrap items-center gap-3 rounded-card border border-edge bg-panel px-4 py-3" aria-label="One-time list import" role="status">
      <i aria-hidden="true" :class="['queued', 'running'].includes(listImport.status) ? 'fas fa-spinner fa-spin text-notice' : listImport.status === 'completed' ? 'fas fa-check-circle text-good' : 'fas fa-circle-exclamation text-caution'"></i>
      <div class="min-w-0 flex-1">
        <strong class="text-sm text-ink">{{ listImport.status === 'completed' ? 'List import complete' : ['failed', 'interrupted'].includes(listImport.status) ? 'List import paused' : 'Importing list…' }}</strong>
        <p class="m-0 mt-1 truncate text-xs text-ink-3">{{ listImport.list_url }}</p>
        <p class="m-0 mt-1 text-xs text-ink-2">{{ listImport.scanned_count }} titles checked · {{ listImport.requested_count }} queued for delivery or approval</p>
        <p v-if="listImport.last_error" class="m-0 mt-1 text-xs text-caution">{{ listImport.last_error }}</p>
      </div>
      <button v-if="['failed', 'interrupted'].includes(listImport.status)" type="button" class="ui-btn" :disabled="importStarting" @click="resumeListImport">Resume import</button>
    </section>

    <!-- Seer delivery queue -->
    <div v-if="queueStatus.total_pending > 0 && !queueBannerDismissed" role="status" class="flex items-center gap-3 rounded-card border border-notice/40 bg-notice/10 px-4 py-3">
      <i aria-hidden="true" class="fas fa-circle-notch fa-spin text-notice"></i>
      <div class="flex flex-1 flex-col text-sm">
        <strong class="text-ink">Delivering to Seer…</strong>
        <span class="text-ink-3">
          {{ queueStatus.total_pending }} item{{ queueStatus.total_pending !== 1 ? 's' : '' }} queued
          <template v-if="queueStatus.submitting > 0"> · {{ queueStatus.submitting }} sending</template>
          <template v-if="queueStatus.failed > 0"> · <span class="text-bad">{{ queueStatus.failed }} failed</span></template>
        </span>
      </div>
      <button type="button" class="h-8 w-8 cursor-pointer rounded-[8px] border-0 bg-transparent text-ink-4 hover:text-ink" aria-label="Dismiss" @click="dismissQueueBanner"><i aria-hidden="true" class="fas fa-times"></i></button>
    </div>
    <div v-else-if="queueStatus.submitted > 0 && queueStatus.total_pending === 0 && !queueBannerDismissed" role="status" class="flex items-center gap-3 rounded-card border border-good/30 bg-good/10 px-4 py-3">
      <i aria-hidden="true" class="fas fa-check-circle text-good"></i>
      <div class="flex flex-1 flex-col text-sm">
        <strong class="text-ink">All requests delivered</strong>
        <span class="text-ink-3">{{ queueStatus.submitted }} item{{ queueStatus.submitted !== 1 ? 's' : '' }} sent to Seer successfully</span>
      </div>
      <button type="button" class="h-8 w-8 cursor-pointer rounded-[8px] border-0 bg-transparent text-ink-4 hover:text-ink" aria-label="Dismiss" @click="dismissQueueBanner"><i aria-hidden="true" class="fas fa-times"></i></button>
    </div>

    <!-- Job types explained -->
    <aside v-if="showInfoBox" class="@container relative rounded-card border border-edge bg-panel p-4 sm:p-5" data-tour-id="jobs-info-box">
      <h2 class="m-0 mb-4 pr-10 text-sm font-bold uppercase tracking-wider text-ink-4">Job types</h2>
      <dl class="m-0 grid grid-cols-1 gap-3 @xl:grid-cols-2 @5xl:grid-cols-4">
        <div v-for="type in jobTypes" :key="type.id" class="flex min-w-0 flex-col gap-2 rounded-ctl border border-edge bg-canvas/40 p-3.5">
          <dt class="flex items-center gap-2.5 text-sm font-bold" :class="type.text"><span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-ctl" :class="type.bg"><i aria-hidden="true" :class="type.icon"></i></span>{{ type.label }}</dt>
          <dd class="m-0 text-[13px] leading-relaxed text-ink-3">{{ type.description }}</dd>
        </div>
      </dl>
      <button type="button" class="absolute right-3 top-3 h-8 w-8 cursor-pointer rounded-[8px] border-0 bg-transparent text-ink-4 hover:text-ink" aria-label="Hide job types" @click="dismissInfoBox"><i aria-hidden="true" class="fas fa-times"></i></button>
    </aside>

    <div v-if="isLoading && jobs.length === 0" class="py-14 text-center text-sm text-ink-3"><i aria-hidden="true" class="fas fa-spinner fa-spin mr-2"></i>Loading jobs…</div>

    <div v-else-if="jobs.length === 0" class="flex flex-col items-center gap-3 rounded-card border border-dashed border-edge-strong px-6 py-14 text-center">
      <i aria-hidden="true" class="fas fa-clock text-4xl text-ink-4"></i>
      <h2 class="m-0 text-lg font-bold text-ink">No jobs yet</h2>
      <p class="m-0 text-sm text-ink-3">Create your first job to start getting suggestions.</p>
      <button type="button" class="mt-2 h-10 cursor-pointer rounded-ctl border-0 bg-brand px-4 text-sm font-bold text-white" @click="showCreateModal = true">Create a job</button>
    </div>

    <div v-else class="flex flex-col gap-3">
      <!-- Which kind of job sends titles people actually watch. -->
      <section v-if="sourceHitRates.length > 1" aria-labelledby="hit-rate-title" class="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-card border border-edge bg-panel px-5 py-4">
        <h2 id="hit-rate-title" class="m-0 text-sm font-bold text-ink">Watched after request</h2>
        <dl class="m-0 flex flex-wrap gap-x-6 gap-y-2">
          <div v-for="source in sourceHitRates" :key="source.label" class="flex items-baseline gap-2" :title="`${source.watched} of ${source.requested} requested titles watched`">
            <dt class="text-[13px] text-ink-3">{{ source.label }}</dt>
            <dd class="m-0 text-sm font-bold text-ink">{{ source.rate }}%</dd>
          </div>
        </dl>
      </section>
      <article
        v-for="(job, index) in jobs"
        :key="job.id"
        class="flex flex-wrap items-center gap-x-6 gap-y-4 rounded-card border border-edge bg-panel px-5 py-[18px] transition-colors hover:border-edge-strong"
        :class="{ 'opacity-70': !job.enabled }"
        :data-tour-id="index === 0 ? 'jobs-first-card' : null"
      >
        <div class="flex min-w-0 flex-[1_1_260px] items-start gap-3.5">
          <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl" :class="[jobTypeStyle(job.job_type).bg, jobTypeStyle(job.job_type).text]"><i aria-hidden="true" :class="getJobTypeIcon(job.job_type)"></i></span>
          <div class="flex min-w-0 flex-col gap-1.5">
            <div class="flex flex-wrap items-center gap-2">
              <h2 class="m-0 text-base font-bold text-ink">{{ job.name }}</h2>
              <span class="rounded-md bg-raised px-2 py-0.5 text-[11px] font-bold text-ink-2">{{ getJobTypeLabel(job.job_type) }}</span>
              <span class="rounded-md bg-raised px-2 py-0.5 text-[11px] font-bold text-ink-2"><i aria-hidden="true" :class="getMediaTypeIcon(job.media_type)" class="mr-1"></i>{{ getMediaTypeLabel(job.media_type) }}</span>
            </div>
            <div v-if="hasFilters(job)" class="flex flex-wrap gap-1.5 text-xs text-ink-3">
              <span>Up to {{ job.max_results }} per run</span>
              <span v-if="job.filters.rating_source !== 'imdb' && job.filters.vote_average_gte">· TMDB Rating &ge; {{ job.filters.vote_average_gte }}</span>
              <span v-if="job.filters.rating_source !== 'imdb' && job.filters.vote_count_gte">· TMDB Votes &ge; {{ job.filters.vote_count_gte }}</span>
              <span v-if="job.filters.rating_source !== 'tmdb' && job.filters.imdb_rating_gte">· IMDB Rating &ge; {{ job.filters.imdb_rating_gte }}</span>
              <span v-if="job.filters.rating_source !== 'tmdb' && job.filters.imdb_min_votes">· IMDB Votes &ge; {{ job.filters.imdb_min_votes }}</span>
              <span v-if="job.filters.with_original_language">· Lang: {{ job.filters.with_original_language }}</span>
              <span v-if="job.filters.with_genres && job.filters.with_genres.length">· +{{ job.filters.with_genres.length }} genres included</span>
              <span v-if="job.filters.without_genres && job.filters.without_genres.length">· -{{ job.filters.without_genres.length }} genres excluded</span>
              <span v-if="job.filters.without_keywords && job.filters.without_keywords.length">· -{{ job.filters.without_keywords.length }} TMDb keywords</span>
            </div>
            <span v-else class="text-xs text-ink-3">Up to {{ job.max_results }} per run</span>
          </div>
        </div>

        <div class="flex flex-[1_1_130px] flex-col gap-0.5" :data-tour-id="index === 0 ? 'jobs-first-card-details' : null">
          <span class="text-xs font-semibold text-ink-4">Schedule</span>
          <span class="text-sm font-semibold text-ink">{{ formatSchedule(job) }}</span>
          <span class="text-xs text-ink-4">{{ job.enabled && job.next_run ? `Next run ${timeFromNow(job.next_run)}` : 'Paused' }}</span>
        </div>

        <div class="flex flex-[1_1_130px] flex-col gap-0.5">
          <span class="text-xs font-semibold text-ink-4">Last run</span>
          <template v-if="lastRunByJob[job.id]">
            <span class="text-sm font-semibold" :class="runStatus(lastRunByJob[job.id].status).text">{{ runStatus(lastRunByJob[job.id].status).label }}</span>
            <span class="truncate text-xs text-ink-4">{{ timeFromNow(lastRunByJob[job.id].started_at) }} · {{ lastRunByJob[job.id].status === 'failed' ? (lastRunByJob[job.id].error_message || 'see logs') : `${lastRunByJob[job.id].results_count} found` }}</span>
          </template>
          <span v-else class="text-sm text-ink-3">Never</span>
        </div>

        <div v-if="job.stats" class="flex flex-[1_1_110px] flex-col gap-0.5">
          <span class="text-xs font-semibold text-ink-4">Watched</span>
          <template v-if="hitRate(job.stats) !== null">
            <span class="text-sm font-semibold text-ink">{{ hitRate(job.stats) }}%</span>
            <span class="text-xs text-ink-4">{{ job.stats.watched }} of {{ job.stats.requested }} requested</span>
          </template>
          <span v-else class="text-sm text-ink-3">Nothing sent yet</span>
        </div>

        <div class="ml-auto flex flex-wrap items-center gap-2" :data-tour-id="index === 0 ? 'jobs-first-card-actions' : null">
          <button
            type="button"
            role="switch"
            :aria-checked="job.enabled ? 'true' : 'false'"
            :aria-label="`${job.name} enabled`"
            class="flex min-h-[44px] cursor-pointer items-center gap-2.5 border-0 bg-transparent px-1 text-[13px] text-ink-2 disabled:opacity-50"
            :disabled="isToggling[job.id]"
            @click="toggleJob(job)"
          >
            <span class="relative inline-block h-[22px] w-10 rounded-full transition-colors" :class="job.enabled ? 'bg-brand' : 'bg-edge-strong'"><span class="absolute top-[3px] h-4 w-4 rounded-full bg-white transition-all" :class="job.enabled ? 'left-[21px]' : 'left-[3px]'"></span></span>
            {{ job.enabled ? 'On' : 'Paused' }}
          </button>
          <button type="button" class="ui-btn" :disabled="isDryRunning[job.id] || isRunning[job.id]" title="Preview what this job would request" @click="dryRunJob(job)">
            <i aria-hidden="true" :class="isDryRunning[job.id] ? 'fas fa-spinner fa-spin' : 'fas fa-eye'"></i>Preview
          </button>
          <button type="button" class="ui-btn" :disabled="isRunning[job.id] || isDryRunning[job.id]" @click="runJob(job)">
            <i aria-hidden="true" :class="isRunning[job.id] ? 'fas fa-spinner fa-spin' : 'fas fa-play'"></i>Run now
          </button>
          <ActionMenu :label="`More actions for ${job.name}`" :items="jobMenuItems(job)" />
        </div>
      </article>
    </div>

    <section v-if="recentHistory.length > 0" class="flex flex-col gap-3.5" data-tour-id="jobs-history">
      <div class="flex items-baseline justify-between gap-3">
        <h2 class="m-0 text-[19px] font-bold text-ink">Recent runs</h2>
        <button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-sm font-semibold text-brand-ink hover:text-white" @click="showHistoryModal = true">Full history →</button>
      </div>
      <div class="overflow-x-auto rounded-card border border-edge bg-panel">
        <table class="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr class="text-left text-xs text-ink-4">
              <th class="px-[18px] py-3 font-semibold">Job</th>
              <th class="px-[18px] py-3 font-semibold">Started</th>
              <th class="px-[18px] py-3 font-semibold">Result</th>
              <th class="px-[18px] py-3 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="exec in recentHistory.slice(0, 5)" :key="exec.id" class="border-t border-edge">
              <td class="px-[18px] py-3.5 font-semibold text-ink">{{ exec.job_name }}</td>
              <td class="px-[18px] py-3.5 text-ink-2">{{ formatDate(exec.started_at) }}</td>
              <td class="px-[18px] py-3.5 text-ink-2">{{ exec.status === 'failed' && exec.error_message ? exec.error_message : `${exec.results_count} found · ${exec.requested_count} requested` }}</td>
              <td class="px-[18px] py-3.5"><span class="inline-flex items-center gap-1.5 text-[13px] font-semibold" :class="runStatus(exec.status).text"><span class="h-2 w-2 rounded-full" :class="runStatus(exec.status).dot"></span>{{ runStatus(exec.status).label }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Create/Edit Job Modal -->
    <JobModal
      v-if="showCreateModal || editingJob"
      ref="jobModal"
      :job="editingJob"
      :request-approval-default="jobDefaults.requestApproval"
      :approval-pause-default="jobDefaults.approvalPause"
      @close="closeModal"
      @save="saveJob"
    />
    <JobModal v-if="showImportModal" one-time :request-approval-default="jobDefaults.requestApproval" @close="showImportModal = false" @save="importListOnce" />

    <AppDialog v-if="jobToDelete" labelledby="delete-job-title" @close="jobToDelete = null">
      <div class="flex flex-col gap-4 p-6">
        <h3 id="delete-job-title" class="m-0 text-lg font-bold text-bad"><i aria-hidden="true" class="fas fa-trash mr-2"></i>Delete job</h3>
        <p class="m-0 text-sm leading-relaxed text-ink-2">Delete <strong class="text-ink">{{ jobToDelete.name }}</strong>? Its execution history is deleted too.</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="h-10 cursor-pointer rounded-ctl border border-edge-strong bg-panel-2 px-4 text-sm font-semibold text-ink" @click="jobToDelete = null">Cancel</button>
          <button type="button" class="ui-btn-danger" :disabled="isDeleting" @click="deleteJob"><i aria-hidden="true" v-if="isDeleting" class="fas fa-spinner fa-spin mr-1"></i>Delete</button>
        </div>
      </div>
    </AppDialog>

    <!-- History Modal -->
    <JobHistoryModal
      v-if="showHistoryModal"
      :history="allHistory"
      @close="showHistoryModal = false"
    />

    <!-- Dry Run Result Modal -->
    <DryRunResultModal
      v-if="dryRunResult"
      :job="dryRunResult.job"
      :items="dryRunResult.items"
      :cached-at="dryRunResult.cachedAt"
      @close="dryRunResult = null"
      @run="onDryRunConfirm"
    />

    <!-- Jobs Onboarding Tour -->
    <OnboardingTour
      :active="showJobsTour"
      :steps="jobsTourSteps"
      @done="onJobsTourDone"
      @step-changed="onJobsTourStep"
    />
  </div>
</template>

<script>
import { jobsApi } from '@/api/jobsApi';
import JobModal from './jobs/JobModal.vue';
import JobHistoryModal from './jobs/JobHistoryModal.vue';
import DryRunResultModal from './jobs/DryRunResultModal.vue';
import OnboardingTour from '@/components/OnboardingTour.vue';
import AppDialog from '@/components/ui/AppDialog.vue';
import ActionMenu from '@/components/ui/ActionMenu.vue';
import { timeFromNow } from '@/utils/dateUtils.js';
import { hitRate, hitRatesBySource } from '@/utils/jobHitRates.js';
import { getJobTypeIcon as resolveJobTypeIcon, getJobTypeLabel as resolveJobTypeLabel, formatJobSchedule } from '@/utils/jobTypeVisuals.js';

const JOBS_TOUR_KEY = 'suggestarr_jobs_tour_done';
// Index of the first step that targets elements inside the job modal
const MODAL_STEP_START = 7;

export default {
  name: 'SettingsJobs',
  components: {
    JobModal,
    JobHistoryModal,
    DryRunResultModal,
    OnboardingTour,
    AppDialog,
    ActionMenu
  },
  // The dashboard shell passes settings props to every tab; this page does not use them.
  inheritAttrs: false,
  data() {
    return {
      jobs: [],
      // Global settings that jobs set to "inherit" follow, shown inside the job modal.
      jobDefaults: { requestApproval: null, approvalPause: null },
      recentHistory: [],
      allHistory: [],
      isLoading: false,
      isToggling: {},
      isRunning: {},
      isDryRunning: {},
      isDeleting: false,
      showCreateModal: false,
      showImportModal: false,
      listImport: null,
      importStarting: false,
      importPollInterval: null,
      showHistoryModal: false,
      dryRunResult: null,
      lastDryRunCache: {},
      editingJob: null,
      jobToDelete: null,
      queueStatus: { queued: 0, submitting: 0, submitted: 0, failed: 0, total_pending: 0 },
      queuePollInterval: null,
      queueBannerDismissed: localStorage.getItem('sj_queue_banner_dismissed') === '1',
      showInfoBox: localStorage.getItem('sj_info_box_hidden') !== '1',
      showJobsTour: false,
      jobTypes: [
        { id: 'discover', label: 'Discover', icon: 'fas fa-search', bg: 'bg-notice/15', text: 'text-notice', description: 'Finds titles with TMDb filters (genre, rating, year), independent of what anyone watched.' },
        { id: 'recommendation', label: 'Recommendation', icon: 'fas fa-users', bg: 'bg-caution/15', text: 'text-caution', description: 'Finds titles similar to what your users watched on the media server or Trakt.' },
        { id: 'trakt_recommendations', label: 'Trakt', icon: 'icon-trakt', bg: 'bg-bad/15', text: 'text-bad', description: 'Uses the personal recommendations of a linked Trakt account.' },
        { id: 'list_import', label: 'Import list', icon: 'fas fa-list', bg: 'bg-notice/15', text: 'text-notice', description: 'Imports missing movies and shows from a public MDBList or Trakt list.' },
      ],
      jobsTourSteps: [
        {
          targetId: 'jobs-section-header',
          title: 'Automation Jobs',
          description: 'This is where you control when and how SuggestArr automatically finds new content for your library.',
          position: 'bottom'
        },
        {
          targetId: 'jobs-info-box',
          title: 'Job Types',
          description: 'Discover jobs search TMDb catalogs using filters. Recommendation jobs analyse media-user watch history. Trakt jobs fetch personalized recommendations from linked Trakt.tv accounts.',
          position: 'bottom'
        },
        {
          targetId: 'jobs-new-btn',
          title: 'Create a Job',
          description: 'Click here to create a new automation job. You can have as many jobs as you like, each on its own schedule and with its own filters.',
          position: 'bottom'
        },
        {
          targetId: 'jobs-first-card',
          title: 'Job Card',
          description: 'Each card summarises a job: its type badge, media target, and whether it is currently active.',
          position: 'bottom'
        },
        {
          targetId: 'jobs-first-card-details',
          title: 'Schedule & Details',
          description: 'At a glance you can see the schedule, the maximum number of results per run, and when the job will run next.',
          position: 'right'
        },
        {
          targetId: 'jobs-first-card-actions',
          title: 'Job Controls',
          description: 'Pause a job without deleting it, preview what it would request, or run it now. Edit, duplicate and delete are under the ⋯ menu.',
          position: 'top'
        },
        {
          targetId: 'jobs-history',
          title: 'Execution History',
          description: 'Every run is logged here with the number of titles found and requested. Click "View All" to explore the full history.',
          position: 'top'
        },
        {
          targetId: 'job-modal-type-selector',
          title: 'Job Type',
          description: 'Import a public list, Discover titles with TMDb filters, get Recommendations from watch history, or use a linked Trakt account. The type is fixed once the job exists.',
          position: 'bottom'
        },
        {
          targetId: 'job-modal-basic-info',
          title: 'Media Type & Name',
          description: 'Pick Movies, TV shows or both. The name is optional: leave it empty to use the suggested one.',
          position: 'bottom'
        },
        {
          targetId: 'job-modal-filters',
          title: 'Filters',
          description: 'Narrow down what gets requested: rating, votes, language, release dates, genres and more. Discover jobs show them right away; other jobs keep them under Quality filters.',
          position: 'top'
        },
        {
          targetId: 'job-modal-schedule',
          title: 'Schedule',
          description: 'Pick how often the job runs, or a custom cron expression, plus the rules that skip a scheduled run.',
          position: 'top'
        },
        {
          targetId: 'job-modal-requests',
          title: 'Requests',
          description: 'Choose whether suggestions go straight to Seer or wait for your approval, and which Seer user they are credited to.',
          position: 'top'
        },
        {
          targetId: 'job-modal-max-results',
          title: 'Limits',
          description: 'Cap how many titles each run requests, and optionally how many one user can receive within a time window.',
          position: 'top'
        },
      ]
    };
  },
  computed: {
    sourceHitRates() {
      return hitRatesBySource(this.jobs);
    },
    // Most recent execution of each job; history arrives newest first.
    lastRunByJob() {
      const latest = {};
      for (const run of this.allHistory) {
        if (!latest[run.job_id]) latest[run.job_id] = run;
      }
      return latest;
    },
  },
  async mounted() {
    await this.loadJobs();
    await this.loadHistory();
    await this.pollQueueStatus();
    await this.pollListImport();

    if (!localStorage.getItem(JOBS_TOUR_KEY)) {
      setTimeout(() => this.startJobsTour(), 600);
    }
  },
  beforeUnmount() {
    if (this.importPollInterval) clearInterval(this.importPollInterval);
    if (this.queuePollInterval) {
      clearInterval(this.queuePollInterval);
    }
  },
  methods: {
    async pollListImport() {
      try {
        const response = await jobsApi.getListImport();
        this.listImport = response.data || null;
      } catch { /* Keep the last progress visible until the next poll. */ }
      if (['queued', 'running'].includes(this.listImport?.status)) {
        if (!this.importPollInterval) this.importPollInterval = setInterval(() => this.pollListImport(), 3000);
      } else if (this.importPollInterval) {
        clearInterval(this.importPollInterval);
        this.importPollInterval = null;
        await this.pollQueueStatus();
      }
    },
    async importListOnce(config) {
      if (this.importStarting) return;
      this.importStarting = true;
      try {
        const response = await jobsApi.importListOnce(config);
        this.listImport = response.data;
        this.showImportModal = false;
        await this.pollListImport();
      } catch (error) {
        this.$toast.open({ type: 'error', message: error.response?.data?.message || 'Could not start list import.' });
      } finally {
        this.importStarting = false;
      }
    },
    async resumeListImport() {
      this.importStarting = true;
      try {
        await jobsApi.resumeListImport(this.listImport.id);
        await this.pollListImport();
      } catch (error) {
        this.$toast.open({ type: 'error', message: error.response?.data?.message || 'Could not resume list import.' });
      } finally {
        this.importStarting = false;
      }
    },
    async loadJobs() {
      this.isLoading = true;
      try {
        const response = await jobsApi.getJobs();
        if (response.status === 'success') {
          this.jobs = response.jobs;
          this.jobDefaults = {
            requestApproval: response.request_approval_default ?? null,
            approvalPause: typeof response.approval_pause_default === 'boolean' ? response.approval_pause_default : null,
          };
        }
      } catch (error) {
        console.error('Failed to load jobs:', error);
        this.$toast.open({
          message: 'Failed to load discover jobs',
          type: 'error'
        });
      } finally {
        this.isLoading = false;
      }
    },

    async loadHistory() {
      try {
        const response = await jobsApi.getAllHistory(100);
        if (response.status === 'success') {
          this.allHistory = response.history;
          this.recentHistory = response.history.slice(0, 5);
        }
      } catch (error) {
        console.error('Failed to load history:', error);
      }
    },

    async toggleJob(job) {
      this.isToggling[job.id] = true;
      try {
        const response = await jobsApi.toggleJob(job.id);
        if (response.status === 'success') {
          job.enabled = response.enabled;
          this.$toast.open({
            message: `Job ${response.enabled ? 'enabled' : 'disabled'}`,
            type: 'success'
          });
        }
      } catch (error) {
        console.error('Failed to toggle job:', error);
        this.$toast.open({
          message: 'Failed to toggle job',
          type: 'error'
        });
      } finally {
        this.isToggling[job.id] = false;
      }
    },

    async pollQueueStatus() {
      try {
        const response = await jobsApi.getQueueStatus();
        if (response.status === 'success') {
          this.queueStatus = response;
          if (response.total_pending > 0 && !this.queuePollInterval) {
            this.queueBannerDismissed = false;
            localStorage.removeItem('sj_queue_banner_dismissed');
            this.queuePollInterval = setInterval(this.pollQueueStatus, 5000);
          } else if (response.total_pending === 0 && this.queuePollInterval) {
            clearInterval(this.queuePollInterval);
            this.queuePollInterval = null;
          }
        }
      } catch {
        // Non-fatal: queue status is informational only
      }
    },

    async runJob(job) {
      this.isRunning[job.id] = true;
      try {
        this.$toast.open({
          message: `Running job: ${job.name}...`,
          type: 'info'
        });
        const response = await jobsApi.runJobNow(job.id);
        if (response.status === 'success') {
          this.$toast.open({
            message: `Job completed: ${response.results_count} found, ${response.requested_count} enqueued for Seer`,
            type: 'success',
            duration: 10000
          });
          await this.loadHistory();
          // Start polling so the queue banner appears immediately
          await this.pollQueueStatus();
        } else {
          this.$toast.open({
            message: response.message || 'Job failed',
            type: 'error'
          });
        }
      } catch (error) {
        console.error('Failed to run job:', error);
        this.$toast.open({
          message: error.response?.data?.message || 'Failed to run job',
          type: 'error'
        });
      } finally {
        this.isRunning[job.id] = false;
      }
    },

    async dryRunJob(job) {
      this.isDryRunning[job.id] = true;
      try {
        this.$toast.open({
          message: `Previewing job: ${job.name}…`,
          type: 'info',
          duration: 3000
        });
        const response = await jobsApi.dryRunJob(job.id);
        if (response.status === 'success') {
          const result = { job, items: response.items || [], cachedAt: Date.now() };
          this.lastDryRunCache[job.id] = result;
          this.dryRunResult = result;
        } else {
          this.$toast.open({
            message: response.message || 'Dry run failed',
            type: 'error'
          });
        }
      } catch (error) {
        console.error('Dry run failed:', error);
        this.$toast.open({
          message: error.response?.data?.message || 'Dry run failed',
          type: 'error'
        });
      } finally {
        this.isDryRunning[job.id] = false;
      }
    },

    reopenDryRun(job) {
      this.dryRunResult = this.lastDryRunCache[job.id];
    },

    async onDryRunConfirm() {
      const job = this.dryRunResult?.job;
      this.dryRunResult = null;
      if (job) {
        await this.runJob(job);
      }
    },

    editJob(job) {
      this.editingJob = { ...job, filters: { ...job.filters } };
    },

    // Secondary actions live in the card's "more" menu, so the card shows only the two everyday ones.
    jobMenuItems(job) {
      return [
        { label: 'Edit', icon: 'fas fa-pen', onSelect: () => this.editJob(job) },
        { label: 'Duplicate', icon: 'fas fa-clone', onSelect: () => this.duplicateJob(job) },
        ...(this.lastDryRunCache[job.id] ? [{ label: 'Last preview', icon: 'fas fa-history', onSelect: () => this.reopenDryRun(job) }] : []),
        { label: 'Delete', icon: 'fas fa-trash', danger: true, onSelect: () => this.confirmDeleteJob(job) },
      ];
    },

    // Opens the create form prefilled; without an id it saves as a new job. Paused so the
    // copy does not send the same titles as the original before it is changed.
    duplicateJob(job) {
      this.editingJob = {
        ...job,
        id: undefined,
        name: `${job.name} (copy)`,
        filters: JSON.parse(JSON.stringify(job.filters || {})),
        enabled: false,
      };
    },

    confirmDeleteJob(job) {
      this.jobToDelete = job;
    },

    async deleteJob() {
      if (!this.jobToDelete) return;

      this.isDeleting = true;
      try {
        const response = await jobsApi.deleteJob(this.jobToDelete.id);
        if (response.status === 'success') {
          this.$toast.open({
            message: 'Job deleted',
            type: 'success'
          });
          this.jobs = this.jobs.filter(j => j.id !== this.jobToDelete.id);
        }
      } catch (error) {
        console.error('Failed to delete job:', error);
        const errorMsg = error.response?.data?.message || 'Failed to delete job';
        this.$toast.open({
          message: errorMsg,
          type: 'error'
        });
      } finally {
        this.isDeleting = false;
        this.jobToDelete = null;
      }
    },

    async saveJob(jobData) {
      try {
        if (this.editingJob && this.editingJob.id) {
          const response = await jobsApi.updateJob(this.editingJob.id, jobData);
          if (response.status === 'success') {
            this.$toast.open({
              message: 'Job updated',
              type: 'success'
            });
          }
        } else {
          const response = await jobsApi.createJob(jobData);
          if (response.status === 'success') {
            this.$toast.open({
              message: 'Job created',
              type: 'success'
            });
          }
        }
        this.closeModal();
        await this.loadJobs();
      } catch (error) {
        console.error('Failed to save job:', error);
        this.$toast.open({
          message: error.response?.data?.message || 'Failed to save job',
          type: 'error'
        });
      }
    },

    dismissQueueBanner() {
      this.queueBannerDismissed = true;
      localStorage.setItem('sj_queue_banner_dismissed', '1');
    },

    dismissInfoBox() {
      this.showInfoBox = false;
      localStorage.setItem('sj_info_box_hidden', '1');
    },

    startJobsTour() {
      // Make sure the info box is visible so its tour step has a target
      this.showInfoBox = true;
      this.showJobsTour = true;
    },

    restartJobsTour() {
      localStorage.removeItem(JOBS_TOUR_KEY);
      this.showJobsTour = false;
      this.$nextTick(() => this.startJobsTour());
    },

    onJobsTourStep(index) {
      if (index >= MODAL_STEP_START) {
        // Open a job for the modal-step portion of the tour
        if (!this.editingJob && !this.showCreateModal) {
          if (this.jobs.length > 0) {
            this.editJob(this.jobs[0]);
          } else {
            this.showCreateModal = true;
          }
        }
        // Expand the collapsed parts so every highlighted element is rendered.
        this.$refs.jobModal?.expandAll();
      } else {
        // Going back to main-page steps — close the modal if the tour opened it
        if (this.editingJob || this.showCreateModal) {
          this.closeModal();
        }
      }
    },

    onJobsTourDone() {
      this.showJobsTour = false;
      localStorage.setItem(JOBS_TOUR_KEY, '1');
      // Close the modal if it was opened by the tour
      if (this.editingJob || this.showCreateModal) {
        this.closeModal();
      }
    },

    closeModal() {
      this.showCreateModal = false;
      this.editingJob = null;
    },

    formatSchedule: formatJobSchedule,
    hitRate,

    formatDate(dateStr) {
      if (!dateStr) return 'N/A';
      const date = new Date(dateStr);
      return date.toLocaleString();
    },

    hasFilters(job) {
      const filters = job.filters || {};
      return Object.keys(filters).some(k => filters[k] !== null && filters[k] !== undefined && filters[k] !== '');
    },

    timeFromNow,

    runStatus(status) {
      const statuses = {
        completed: { label: 'Succeeded', text: 'text-good', dot: 'bg-good' },
        failed: { label: 'Failed', text: 'text-bad', dot: 'bg-bad' },
        running: { label: 'Running', text: 'text-notice', dot: 'bg-notice' },
      };
      return statuses[status] || { label: status, text: 'text-ink-3', dot: 'bg-ink-4' };
    },

    jobTypeStyle(jobType) {
      const styles = {
        recommendation: { bg: 'bg-caution/15', text: 'text-caution' },
        trakt_recommendations: { bg: 'bg-bad/15', text: 'text-bad' },
        list_import: { bg: 'bg-notice/15', text: 'text-notice' },
        llm_recommendation: { bg: 'bg-brand-soft', text: 'text-brand-ink' },
      };
      return styles[jobType] || { bg: 'bg-notice/15', text: 'text-notice' };
    },

    getJobTypeIcon(jobType) {
      return resolveJobTypeIcon(jobType);
    },

    getJobTypeLabel(jobType) {
      return resolveJobTypeLabel(jobType);
    },

    getMediaTypeIcon(mediaType) {
      const icons = {
        movie: 'fas fa-film',
        tv: 'fas fa-tv',
        both: 'fas fa-layer-group'
      };
      return icons[mediaType] || 'fas fa-question';
    },

    getMediaTypeLabel(mediaType) {
      const labels = {
        movie: 'Movies',
        tv: 'TV Shows',
        both: 'Both'
      };
      return labels[mediaType] || mediaType;
    }
  }
};
</script>

