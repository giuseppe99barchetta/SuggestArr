<template>
  <div class="settings-jobs">
    <div class="section-header" data-tour-id="jobs-section-header">
      <h2>Automation Jobs</h2>
      <p>Configure automated content discovery and recommendations</p>
    </div>

    <!-- Seer delivery queue banner -->
    <transition name="queue-banner">
      <div v-if="queueStatus.total_pending > 0 && !queueBannerDismissed" class="queue-banner">
        <div class="queue-banner-icon">
          <i class="fas fa-circle-notch fa-spin"></i>
        </div>
        <div class="queue-banner-body">
          <strong>Delivering to Seer…</strong>
          <span>
            {{ queueStatus.total_pending }} item{{ queueStatus.total_pending !== 1 ? 's' : '' }} queued
            <template v-if="queueStatus.submitting > 0"> · {{ queueStatus.submitting }} sending</template>
            <template v-if="queueStatus.failed > 0"> · <span class="queue-failed">{{ queueStatus.failed }} failed</span></template>
          </span>
        </div>
        <div class="queue-banner-spinner">
          <i class="fas fa-circle-notch fa-spin"></i>
        </div>
        <button class="queue-banner-close" @click="dismissQueueBanner" title="Dismiss">
          <i class="fas fa-times"></i>
        </button>
      </div>
      <div v-else-if="queueStatus.submitted > 0 && queueStatus.total_pending === 0 && !queueBannerDismissed" class="queue-banner queue-banner--done">
        <div class="queue-banner-icon">
          <i class="fas fa-check-circle"></i>
        </div>
        <div class="queue-banner-body">
          <strong>All requests delivered</strong>
          <span>{{ queueStatus.submitted }} item{{ queueStatus.submitted !== 1 ? 's' : '' }} sent to Seer successfully</span>
        </div>
        <button class="queue-banner-close queue-banner-close--done" @click="dismissQueueBanner" title="Dismiss">
          <i class="fas fa-times"></i>
        </button>
      </div>
    </transition>

    <!-- Info Box explaining both job types -->
    <div v-if="showInfoBox" class="info-box" data-tour-id="jobs-info-box">
      <div class="info-icon">
        <i class="fas fa-info-circle"></i>
      </div>
      <div class="info-content">
        <h4>Two Types of Jobs</h4>
        <div class="job-types-explanation">
          <div class="job-type-item">
            <span class="job-type-badge discover"><i class="fas fa-search"></i> Discover</span>
            <span>Find content using TMDb filters (genre, rating, year) - independent from user watch history.</span>
          </div>
          <div class="job-type-item">
            <span class="job-type-badge recommendation"><i class="fas fa-users"></i> Recommendation</span>
            <span>Find similar content based on what your users have watched - like the original SuggestArr automation.</span>
          </div>
        </div>
      </div>
      <button class="info-box-close" @click="dismissInfoBox" title="Dismiss">
        <i class="fas fa-times"></i>
      </button>
    </div>

    <div class="jobs-container">
      <!-- Actions Bar -->
      <div class="jobs-actions">
        <button @click="showCreateModal = true" class="btn btn-primary" data-tour-id="jobs-new-btn">
          <i class="fas fa-plus"></i>
          New Job
        </button>
        <button @click="loadJobs" class="btn btn-outline" :disabled="isLoading">
          <i :class="isLoading ? 'fas fa-spinner fa-spin' : 'fas fa-sync'"></i>
          Refresh
        </button>
        <button @click="restartJobsTour" class="btn btn-outline btn-tour-hint" title="Replay the Jobs tour">
          <i class="fas fa-question-circle"></i>
        </button>
      </div>

      <!-- Jobs List -->
      <div v-if="isLoading && jobs.length === 0" class="loading-state">
        <i class="fas fa-spinner fa-spin"></i>
        <span>Loading jobs...</span>
      </div>

      <div v-else-if="jobs.length === 0" class="empty-state">
        <i class="fas fa-briefcase"></i>
        <h3>No Jobs Configured</h3>
        <p>Create your first job to automate content discovery or recommendations.</p>
        <button @click="showCreateModal = true" class="btn btn-primary">
          <i class="fas fa-plus"></i>
          Create First Job
        </button>
      </div>

      <div v-else class="jobs-grid">
        <div
          v-for="(job, index) in jobs"
          :key="job.id"
          class="job-card"
          :class="{ disabled: !job.enabled }"
          :data-tour-id="index === 0 ? 'jobs-first-card' : null"
        >
          <div class="job-header">
            <div class="job-info">
              <h3>{{ job.name }}</h3>
              <div class="job-badges">
                <span class="job-type-badge" :class="job.job_type || 'discover'">
                  <i :class="job.job_type === 'recommendation' ? 'fas fa-users' : 'fas fa-search'"></i>
                  {{ job.job_type === 'recommendation' ? 'Recommendation' : 'Discover' }}
                </span>
                <span class="media-type-badge" :class="job.media_type">
                  <i :class="getMediaTypeIcon(job.media_type)"></i>
                  {{ getMediaTypeLabel(job.media_type) }}
                </span>
              </div>
            </div>
            <div class="job-status">
              <span class="status-indicator" :class="{ active: job.enabled }"></span>
              <span>{{ job.enabled ? 'Active' : 'Disabled' }}</span>
            </div>
          </div>

          <div class="job-details" :data-tour-id="index === 0 ? 'jobs-first-card-details' : null">
            <div class="detail-row">
              <span class="detail-label"><i class="fas fa-clock"></i> Schedule</span>
              <span class="detail-value">{{ formatSchedule(job) }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label"><i class="fas fa-list-ol"></i> Max Results</span>
              <span class="detail-value">{{ job.max_results }}</span>
            </div>
            <div class="detail-row" v-if="job.next_run">
              <span class="detail-label"><i class="fas fa-calendar"></i> Next Run</span>
              <span class="detail-value">{{ formatDate(job.next_run) }}</span>
            </div>
          </div>

          <!-- Filters Summary -->
          <div class="job-filters" v-if="hasFilters(job)">
            <span class="filters-label">Filters:</span>
            <div class="filter-tags">
              <span v-if="job.filters.vote_average_gte" class="filter-tag">
                Rating &ge; {{ job.filters.vote_average_gte }}
              </span>
              <span v-if="job.filters.vote_count_gte" class="filter-tag">
                Votes &ge; {{ job.filters.vote_count_gte }}
              </span>
              <span v-if="job.filters.with_original_language" class="filter-tag">
                Lang: {{ job.filters.with_original_language }}
              </span>
              <span v-if="job.filters.without_genres && job.filters.without_genres.length" class="filter-tag exclude">
                -{{ job.filters.without_genres.length }} genres excluded
              </span>
            </div>
          </div>

          <div class="job-actions" :data-tour-id="index === 0 ? 'jobs-first-card-actions' : null">
            <button @click="toggleJob(job)" class="btn btn-sm" :class="job.enabled ? 'btn-outline' : 'btn-secondary'" :disabled="isToggling[job.id]">
              <i :class="isToggling[job.id] ? 'fas fa-spinner fa-spin' : (job.enabled ? 'fas fa-pause' : 'fas fa-play')"></i>
              {{ job.enabled ? 'Disable' : 'Enable' }}
            </button>
            <button @click="runJob(job)" class="btn btn-sm btn-outline" :disabled="isRunning[job.id] || isDryRunning[job.id]">
              <i :class="isRunning[job.id] ? 'fas fa-spinner fa-spin' : 'fas fa-bolt'"></i>
              Run
            </button>
            <button @click="dryRunJob(job)" class="btn btn-sm btn-outline btn-preview" :disabled="isDryRunning[job.id] || isRunning[job.id]" title="Preview what this job would request">
              <i :class="isDryRunning[job.id] ? 'fas fa-spinner fa-spin' : 'fas fa-eye'"></i>
              Preview
            </button>
            <button
              v-if="lastDryRunCache[job.id]"
              @click="reopenDryRun(job)"
              class="btn btn-sm btn-outline btn-reopen"
              title="Re-open last preview result"
            >
              <i class="fas fa-history"></i>
            </button>
            <button @click="editJob(job)" class="btn btn-sm btn-outline" title="Edit job">
              <i class="fas fa-edit"></i>
              Edit
            </button>
            <button @click="confirmDeleteJob(job)" class="btn btn-sm btn-danger" title="Delete job">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </div>
      </div>

      <!-- Recent History Preview -->
      <div v-if="recentHistory.length > 0" class="history-preview" data-tour-id="jobs-history">
        <div class="history-header">
          <h3><i class="fas fa-history"></i> Recent Executions</h3>
          <button @click="showHistoryModal = true" class="text-btn">View All</button>
        </div>
        <div class="history-list">
          <div v-for="exec in recentHistory.slice(0, 5)" :key="exec.id" class="history-item">
            <span class="history-status" :class="exec.status">
              <i :class="getStatusIcon(exec.status)"></i>
            </span>
            <span class="history-job">{{ exec.job_name }}</span>
            <span class="history-time">{{ formatDate(exec.started_at) }}</span>
            <span class="history-result">
              {{ exec.results_count }} found, {{ exec.requested_count }} requested
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Create/Edit Job Modal -->
    <JobModal
      v-if="showCreateModal || editingJob"
      ref="jobModal"
      :job="editingJob"
      @close="closeModal"
      @save="saveJob"
    />

    <!-- Delete Confirmation Modal -->
    <transition name="fade">
      <div v-if="jobToDelete" class="modal-overlay" @click.self="jobToDelete = null">
        <div class="modal-content">
          <div class="modal-header">
            <i class="fas fa-exclamation-triangle warning-icon"></i>
            <h3>Delete Job</h3>
          </div>
          <p class="modal-body">
            Are you sure you want to delete <strong>{{ jobToDelete.name }}</strong>?
            This will also delete all execution history for this job.
          </p>
          <div class="modal-actions">
            <button @click="jobToDelete = null" class="btn btn-secondary">
              <i class="fas fa-times"></i> Cancel
            </button>
            <button @click="deleteJob" class="btn btn-danger" :disabled="isDeleting">
              <i :class="isDeleting ? 'fas fa-spinner fa-spin' : 'fas fa-trash'"></i>
              Delete
            </button>
          </div>
        </div>
      </div>
    </transition>

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

const JOBS_TOUR_KEY = 'suggestarr_jobs_tour_done';
// Index of the first step that targets elements inside the job modal
const MODAL_STEP_START = 7;
// Index of the first step that requires the advanced section to be expanded
const ADVANCED_STEP_START = 11;

export default {
  name: 'SettingsJobs',
  components: {
    JobModal,
    JobHistoryModal,
    DryRunResultModal,
    OnboardingTour
  },
  data() {
    return {
      jobs: [],
      recentHistory: [],
      allHistory: [],
      isLoading: false,
      isToggling: {},
      isRunning: {},
      isDryRunning: {},
      isDeleting: false,
      showCreateModal: false,
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
      jobsTourSteps: [
        {
          targetId: 'jobs-section-header',
          title: 'Automation Jobs',
          description: 'This is where you control when and how SuggestArr automatically finds new content for your library.',
          position: 'bottom'
        },
        {
          targetId: 'jobs-info-box',
          title: 'Two Types of Jobs',
          description: 'Discover Jobs search TMDb catalogs using filters (genre, rating, year) — completely independent from your users. Recommendation Jobs analyse watch history to suggest similar content.',
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
          description: 'Each card summarises a job: its type badge (Discover or Recommendation), media target, and whether it is currently active.',
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
          description: 'Enable or disable a job without deleting it, trigger an immediate run, open the editor, or remove the job entirely.',
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
          description: 'Choose Discover to find new content via TMDb filters, or Recommendation to suggest titles based on what your users have already watched.',
          position: 'bottom'
        },
        {
          targetId: 'job-modal-basic-info',
          title: 'Name & Media Type',
          description: 'Give your job a descriptive name and pick whether it should target Movies, TV Shows, or both.',
          position: 'bottom'
        },
        {
          targetId: 'job-modal-schedule',
          title: 'Schedule',
          description: 'Pick a preset interval (hourly, daily, weekly…) or enter a custom cron expression for full control over when the job fires.',
          position: 'top'
        },
        {
          targetId: 'job-modal-advanced-toggle',
          title: 'Advanced Settings',
          description: 'Expand this section to configure quality filters, rating thresholds, language restrictions, and the maximum number of results per run.',
          position: 'top'
        },
        {
          targetId: 'job-modal-max-results',
          title: 'Max Results',
          description: 'Controls how many items the job processes per run. For Discover jobs this is the total titles found; for Recommendation jobs it is the limit per watched item.',
          position: 'bottom'
        },
        {
          targetId: 'job-modal-filters',
          title: 'Filters',
          description: 'Narrow down what gets requested: minimum TMDb rating, minimum vote count, original language, year range, and genre exclusions. Only content matching all active filters will be sent to Jellyseer/Overseer.',
          position: 'top'
        },
      ]
    };
  },
  async mounted() {
    await this.loadJobs();
    await this.loadHistory();
    await this.pollQueueStatus();

    if (!localStorage.getItem(JOBS_TOUR_KEY)) {
      setTimeout(() => this.startJobsTour(), 600);
    }
  },
  beforeUnmount() {
    if (this.queuePollInterval) {
      clearInterval(this.queuePollInterval);
    }
  },
  methods: {
    async loadJobs() {
      this.isLoading = true;
      try {
        const response = await jobsApi.getJobs();
        if (response.status === 'success') {
          this.jobs = response.jobs;
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
        // Expand the advanced section one step early (at the toggle button, step 10)
        // so that the advanced-section DOM elements are rendered before scrollAndUpdate()
        // fires for the first advanced step (step 11). Calling this synchronously ensures
        // Vue batches the DOM update together with the currentIndex change.
        if (index >= ADVANCED_STEP_START - 1) {
          this.$refs.jobModal?.openAdvanced();
        }
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

    formatSchedule(job) {
      if (job.schedule_type === 'preset') {
        const presets = {
          daily: 'Daily at midnight',
          weekly: 'Weekly on Monday',
          every_12h: 'Every 12 hours',
          every_6h: 'Every 6 hours',
          every_hour: 'Every hour'
        };
        return presets[job.schedule_value] || job.schedule_value;
      }
      return `Cron: ${job.schedule_value}`;
    },

    formatDate(dateStr) {
      if (!dateStr) return 'N/A';
      const date = new Date(dateStr);
      return date.toLocaleString();
    },

    hasFilters(job) {
      const filters = job.filters || {};
      return Object.keys(filters).some(k => filters[k] !== null && filters[k] !== undefined && filters[k] !== '');
    },

    getStatusIcon(status) {
      const icons = {
        running: 'fas fa-spinner fa-spin',
        completed: 'fas fa-check',
        failed: 'fas fa-times'
      };
      return icons[status] || 'fas fa-question';
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

<style scoped>
.settings-jobs {
  padding: 0;
  padding: var(--spacing-lg);
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

/* Info Box */
.info-box {
  display: flex;
  gap: 1rem;
  padding: 1.25rem;
  background: rgba(6, 182, 212, 0.08);
  border: 1px solid rgba(6, 182, 212, 0.2);
  border-radius: var(--radius-md, 8px);
  margin-bottom: 1.5rem;
  align-items: flex-start;
}

.info-box-close {
  flex-shrink: 0;
  background: none;
  border: none;
  color: #22d3ee;
  cursor: pointer;
  padding: 0.15rem;
  font-size: 0.8rem;
  opacity: 0.5;
  transition: opacity 0.15s ease;
  margin-left: auto;
}

.info-box-close:hover {
  opacity: 1;
}

.info-icon {
  flex-shrink: 0;
  color: #22d3ee;
  font-size: 1.25rem;
}

.info-content h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text-primary, #fff);
}

.info-content p {
  margin: 0 0 0.5rem 0;
  font-size: 0.85rem;
  color: var(--color-text-secondary, #aaa);
  line-height: 1.5;
}

.info-content p:last-child {
  margin-bottom: 0;
}

.info-content strong {
  color: var(--color-text-primary, #fff);
}

.info-example {
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--radius-sm, 6px);
  margin-top: 0.75rem;
}

/* Job Types Explanation */
.job-types-explanation {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.job-type-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.85rem;
  color: var(--color-text-secondary, #aaa);
}

.job-type-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.5rem;
  border-radius: var(--radius-sm, 6px);
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.job-type-badge.discover {
  background: rgba(6, 182, 212, 0.15);
  color: #22d3ee;
}

.job-type-badge.recommendation {
  background: rgba(168, 85, 247, 0.15);
  color: #c084fc;
}

/* Job Badges Container */
.job-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.35rem;
}

/* Media Type Badge */
.media-type-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.5rem;
  border-radius: var(--radius-sm, 6px);
  font-size: 0.7rem;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-text-secondary, #aaa);
}

.media-type-badge.movie {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.media-type-badge.tv {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.media-type-badge.both {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.jobs-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.jobs-actions {
  display: flex;
  gap: 0.75rem;
}

.btn-tour-hint {
  flex-shrink: 0;
  padding: 0.625rem 0.75rem;
  color: var(--color-text-muted, #888);
}

.btn-tour-hint:hover:not(:disabled) {
  color: var(--color-text-primary, #fff);
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  text-align: center;
  background: rgba(255, 255, 255, 0.03);
  border-radius: var(--radius-md);
  border: 1px dashed rgba(255, 255, 255, 0.1);
}

.empty-state i,
.loading-state i {
  font-size: 3rem;
  color: var(--color-text-secondary);
  margin-bottom: 1rem;
}

.empty-state h3 {
  margin-bottom: 0.5rem;
  color: var(--color-text-primary);
}

.empty-state p {
  color: var(--color-text-secondary);
  margin-bottom: 1.5rem;
  max-width: 400px;
}

.jobs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 1rem;
}

.job-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-md);
  padding: 1.25rem;
  transition: all 0.2s ease;
}

.job-card:hover {
  border-color: rgba(255, 255, 255, 0.2);
}

.job-card.disabled {
  opacity: 0.6;
}

.job-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
}

.job-info h3 {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 0.5rem 0;
}

.job-type-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.1);
  color: var(--color-text-secondary);
}

.job-type-badge.movie {
  background: rgba(var(--color-primary-rgb), 0.2);
  color: var(--color-primary);
}

.job-type-badge.tv {
  background: rgba(0, 200, 150, 0.2);
  color: #00c896;
}

.job-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--color-text-secondary);
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #666;
}

.status-indicator.active {
  background: #00c896;
  box-shadow: 0 0 6px #00c896;
}

.job-details {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--radius-sm);
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
}

.detail-label {
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.detail-label i {
  width: 1rem;
  text-align: center;
}

.detail-value {
  color: var(--color-text-primary);
}

.job-filters {
  margin-bottom: 1rem;
}

.filters-label {
  font-size: 0.8rem;
  color: var(--color-text-secondary);
  display: block;
  margin-bottom: 0.5rem;
}

.filter-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.filter-tag {
  font-size: 0.7rem;
  padding: 0.2rem 0.5rem;
  background: rgba(var(--color-primary-rgb), 0.2);
  color: var(--color-primary);
  border-radius: 0.25rem;
}

.filter-tag.exclude {
  background: rgba(255, 100, 100, 0.2);
  color: #ff6464;
}

.job-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.job-actions .btn {
  flex: 1;
  min-width: auto;
}

.job-actions .btn-danger {
  flex: 0 0 auto;
  padding: 0.5rem 0.75rem;
}

.btn-preview {
  color: #22d3ee;
  border-color: rgba(6, 182, 212, 0.25);
}

.btn-preview:hover:not(:disabled) {
  background: rgba(6, 182, 212, 0.08);
  border-color: rgba(6, 182, 212, 0.45);
}

.btn-reopen {
  color: rgba(34, 211, 238, 0.6);
  border-color: rgba(6, 182, 212, 0.15);
  padding-left: 0.55rem;
  padding-right: 0.55rem;
}

.btn-reopen:hover {
  color: #22d3ee;
  background: rgba(6, 182, 212, 0.08);
  border-color: rgba(6, 182, 212, 0.35);
}

/* History Preview */
.history-preview {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  padding: 1rem;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.history-header h3 {
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.text-btn {
  background: none;
  border: none;
  color: var(--color-primary);
  cursor: pointer;
  font-size: 0.85rem;
}

.text-btn:hover {
  text-decoration: underline;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 0.85rem;
}

.history-item:last-child {
  border-bottom: none;
}

.history-status {
  width: 1.5rem;
  text-align: center;
}

.history-status.completed {
  color: #00c896;
}

.history-status.failed {
  color: #ff6464;
}

.history-status.running {
  color: var(--color-primary);
}

.history-job {
  flex: 1;
  color: var(--color-text-primary);
  font-weight: 500;
}

.history-time {
  color: var(--color-text-secondary);
  font-size: 0.8rem;
}

.history-result {
  color: var(--color-text-secondary);
  font-size: 0.8rem;
}

/* Button Styles */
.btn {
  padding: 0.625rem 1rem;
  border-radius: var(--radius-sm, 6px);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-primary, #636363);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover, #4a4a4a);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-text-primary, #fff);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.15);
}

.btn-outline {
  background: transparent;
  color: var(--color-text-primary, #fff);
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.btn-outline:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.25);
}

.btn-danger {
  background: rgba(220, 38, 38, 0.15);
  color: #f87171;
  border: 1px solid rgba(220, 38, 38, 0.3);
}

.btn-danger:hover:not(:disabled) {
  background: rgba(220, 38, 38, 0.25);
  border-color: rgba(220, 38, 38, 0.5);
}

.btn-sm {
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--color-bg-content, #1a1a1c);
  border-radius: var(--radius-lg, 12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 1.5rem;
  max-width: 420px;
  width: 90%;
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--color-text-primary, #fff);
}

.warning-icon {
  color: #fbbf24;
  font-size: 1.25rem;
}

.modal-body {
  color: var(--color-text-secondary, #aaa);
  margin-bottom: 1.5rem;
  font-size: 0.9rem;
  line-height: 1.5;
}

.modal-body strong {
  color: var(--color-text-primary, #fff);
}

.modal-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

/* Responsive */
@media (max-width: 768px) {
  .jobs-grid {
    grid-template-columns: 1fr;
  }

  .job-actions {
    flex-direction: column;
  }

  .job-actions .btn {
    flex: none;
    width: 100%;
  }

  .history-item {
    flex-wrap: wrap;
  }

  .history-result {
    width: 100%;
    margin-top: 0.25rem;
    padding-left: 2.25rem;
  }
}

/* Transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
/* Queue delivery banner */
.queue-banner {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  padding: 0.875rem 1.25rem;
  background: rgba(234, 179, 8, 0.1);
  border: 1px solid rgba(234, 179, 8, 0.35);
  border-radius: var(--radius-md, 8px);
  margin-bottom: 1.25rem;
}

.queue-banner--done {
  background: rgba(34, 197, 94, 0.08);
  border-color: rgba(34, 197, 94, 0.3);
}

.queue-banner-icon {
  flex-shrink: 0;
  font-size: 1.1rem;
  color: #eab308;
}

.queue-banner--done .queue-banner-icon {
  color: #22c55e;
}

.queue-banner-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  font-size: 0.875rem;
}

.queue-banner-body strong {
  color: var(--color-text-primary, #fff);
  font-weight: 600;
}

.queue-banner-body span {
  color: var(--color-text-secondary);
}

.queue-failed {
  color: #f87171;
  font-weight: 600;
}

.queue-banner-spinner {
  flex-shrink: 0;
  color: #eab308;
  font-size: 1rem;
}

.queue-banner-close {
  flex-shrink: 0;
  background: none;
  border: none;
  color: #eab308;
  cursor: pointer;
  padding: 0.25rem;
  font-size: 0.85rem;
  opacity: 0.6;
  transition: opacity 0.15s ease;
  margin-left: 0.25rem;
}

.queue-banner-close:hover {
  opacity: 1;
}

.queue-banner-close--done {
  color: #22c55e;
}

/* Slide-down transition for the queue banner */
.queue-banner-enter-active,
.queue-banner-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.queue-banner-enter-from,
.queue-banner-leave-to {
  opacity: 0;
  max-height: 0;
  margin-bottom: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.queue-banner-enter-to,
.queue-banner-leave-from {
  opacity: 1;
  max-height: 80px;
}
</style>
