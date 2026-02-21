<template>
  <div class="settings-jobs">
    <div class="section-header">
      <h2>Automation Jobs</h2>
      <p>Configure automated content discovery and recommendations</p>
    </div>

    <!-- Info Box explaining both job types -->
    <div class="info-box">
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
    </div>

    <div class="jobs-container">
      <!-- Actions Bar -->
      <div class="jobs-actions">
        <button @click="showCreateModal = true" class="btn btn-primary">
          <i class="fas fa-plus"></i>
          New Job
        </button>
        <button @click="loadJobs" class="btn btn-outline" :disabled="isLoading">
          <i :class="isLoading ? 'fas fa-spinner fa-spin' : 'fas fa-sync'"></i>
          Refresh
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
        <div v-for="job in jobs" :key="job.id" class="job-card" :class="{ disabled: !job.enabled }">
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

          <div class="job-details">
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

          <div class="job-actions">
            <button @click="toggleJob(job)" class="btn btn-sm" :class="job.enabled ? 'btn-outline' : 'btn-secondary'" :disabled="isToggling[job.id]">
              <i :class="isToggling[job.id] ? 'fas fa-spinner fa-spin' : (job.enabled ? 'fas fa-pause' : 'fas fa-play')"></i>
              {{ job.enabled ? 'Disable' : 'Enable' }}
            </button>
            <button @click="runJob(job)" class="btn btn-sm btn-outline" :disabled="isRunning[job.id]">
              <i :class="isRunning[job.id] ? 'fas fa-spinner fa-spin' : 'fas fa-bolt'"></i>
              Run
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
      <div v-if="recentHistory.length > 0" class="history-preview">
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
  </div>
</template>

<script>
import { jobsApi } from '@/api/jobsApi';
import JobModal from './jobs/JobModal.vue';
import JobHistoryModal from './jobs/JobHistoryModal.vue';

export default {
  name: 'SettingsJobs',
  components: {
    JobModal,
    JobHistoryModal
  },
  data() {
    return {
      jobs: [],
      recentHistory: [],
      allHistory: [],
      isLoading: false,
      isToggling: {},
      isRunning: {},
      isDeleting: false,
      showCreateModal: false,
      showHistoryModal: false,
      editingJob: null,
      jobToDelete: null
    };
  },
  async mounted() {
    await this.loadJobs();
    await this.loadHistory();
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
            message: `Job completed: ${response.results_count} found, ${response.requested_count} requested`,
            type: 'success',
            duration: 10000
          });
          await this.loadHistory();
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
}

.section-header {
  margin-bottom: 1.5rem;
}

.section-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 0.25rem;
}

.section-header p {
  color: var(--color-text-secondary);
  font-size: 0.9rem;
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
</style>
