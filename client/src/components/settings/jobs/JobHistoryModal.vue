<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="history-modal">
      <div class="modal-header">
        <h2><i class="fas fa-history"></i> Execution History</h2>
        <button @click="$emit('close')" class="close-btn">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="modal-body">
        <!-- Filters -->
        <div class="history-filters">
          <div class="filter-group">
            <label>Status</label>
            <select v-model="filterStatus" class="form-control">
              <option value="">All</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="running">Running</option>
            </select>
          </div>
        </div>

        <!-- History Table -->
        <div class="history-table-container">
          <table class="history-table" v-if="filteredHistory.length > 0">
            <thead>
              <tr>
                <th>Status</th>
                <th>Job</th>
                <th>Started</th>
                <th>Duration</th>
                <th>Results</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="exec in paginatedHistory" :key="exec.id" :class="{ 'row-failed': exec.status === 'failed' }">
                <td>
                  <span class="status-badge" :class="exec.status">
                    <i :class="getStatusIcon(exec.status)"></i>
                    {{ exec.status }}
                  </span>
                </td>
                <td class="job-name">{{ exec.job_name }}</td>
                <td class="timestamp">{{ formatDate(exec.started_at) }}</td>
                <td class="duration">{{ formatDuration(exec) }}</td>
                <td class="results">
                  <span class="result-found">{{ exec.results_count }} found</span>
                  <span class="result-requested">{{ exec.requested_count }} requested</span>
                </td>
                <td class="details">
                  <button
                    v-if="exec.error_message"
                    @click="showError(exec)"
                    class="error-btn"
                    title="View error"
                  >
                    <i class="fas fa-exclamation-circle"></i>
                  </button>
                  <span v-else class="no-error">-</span>
                </td>
              </tr>
            </tbody>
          </table>

          <div v-else class="empty-history">
            <i class="fas fa-inbox"></i>
            <p>No execution history found</p>
          </div>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="pagination">
          <button
            @click="currentPage--"
            :disabled="currentPage === 1"
            class="page-btn"
          >
            <i class="fas fa-chevron-left"></i>
          </button>
          <span class="page-info">
            Page {{ currentPage }} of {{ totalPages }}
          </span>
          <button
            @click="currentPage++"
            :disabled="currentPage === totalPages"
            class="page-btn"
          >
            <i class="fas fa-chevron-right"></i>
          </button>
        </div>
      </div>

      <!-- Error Detail Modal -->
      <transition name="fade">
        <div v-if="selectedError" class="error-detail-overlay" @click.self="selectedError = null">
          <div class="error-detail-modal">
            <div class="error-header">
              <h3><i class="fas fa-exclamation-triangle"></i> Error Details</h3>
              <button @click="selectedError = null" class="close-btn">
                <i class="fas fa-times"></i>
              </button>
            </div>
            <div class="error-body">
              <div class="error-info">
                <span class="error-label">Job:</span>
                <span>{{ selectedError.job_name }}</span>
              </div>
              <div class="error-info">
                <span class="error-label">Time:</span>
                <span>{{ formatDate(selectedError.started_at) }}</span>
              </div>
              <div class="error-message-box">
                <pre>{{ selectedError.error_message }}</pre>
              </div>
            </div>
            <div class="error-actions">
              <button @click="copyError" class="btn btn-outline">
                <i class="fas fa-copy"></i> Copy Error
              </button>
              <button @click="selectedError = null" class="btn btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script>
export default {
  name: 'JobHistoryModal',
  props: {
    history: {
      type: Array,
      default: () => []
    }
  },
  emits: ['close'],
  data() {
    return {
      filterStatus: '',
      currentPage: 1,
      perPage: 15,
      selectedError: null
    };
  },
  computed: {
    filteredHistory() {
      if (!this.filterStatus) {
        return this.history;
      }
      return this.history.filter(exec => exec.status === this.filterStatus);
    },
    totalPages() {
      return Math.ceil(this.filteredHistory.length / this.perPage);
    },
    paginatedHistory() {
      const start = (this.currentPage - 1) * this.perPage;
      return this.filteredHistory.slice(start, start + this.perPage);
    }
  },
  watch: {
    filterStatus() {
      this.currentPage = 1;
    }
  },
  methods: {
    formatDate(dateStr) {
      if (!dateStr) return 'N/A';
      const date = new Date(dateStr);
      return date.toLocaleString();
    },

    formatDuration(exec) {
      if (!exec.started_at || !exec.finished_at) {
        return exec.status === 'running' ? 'Running...' : 'N/A';
      }

      const start = new Date(exec.started_at);
      const end = new Date(exec.finished_at);
      const durationMs = end - start;

      if (durationMs < 1000) {
        return `${durationMs}ms`;
      } else if (durationMs < 60000) {
        return `${Math.round(durationMs / 1000)}s`;
      } else {
        const mins = Math.floor(durationMs / 60000);
        const secs = Math.round((durationMs % 60000) / 1000);
        return `${mins}m ${secs}s`;
      }
    },

    getStatusIcon(status) {
      const icons = {
        running: 'fas fa-spinner fa-spin',
        completed: 'fas fa-check',
        failed: 'fas fa-times'
      };
      return icons[status] || 'fas fa-question';
    },

    showError(exec) {
      this.selectedError = exec;
    },

    copyError() {
      if (this.selectedError && this.selectedError.error_message) {
        navigator.clipboard.writeText(this.selectedError.error_message);
        this.$toast?.open({
          message: 'Error copied to clipboard',
          type: 'success'
        });
      }
    }
  }
};
</script>

<style scoped>
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
  padding: 1rem;
}

.history-modal {
  background: var(--color-bg-content, #1a1a1c);
  border-radius: var(--radius-lg, 12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  width: 100%;
  max-width: 900px;
  max-height: 85vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-text-primary, #fff);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.close-btn {
  background: transparent;
  border: none;
  color: var(--color-text-muted, #888);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: var(--radius-sm, 6px);
  transition: all 0.2s ease;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--color-text-primary, #fff);
}

.modal-body {
  padding: 1.5rem;
  overflow-y: auto;
  flex: 1;
}

.history-filters {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.filter-group label {
  font-size: 0.8rem;
  color: var(--color-text-secondary, #aaa);
}

.form-control {
  padding: 0.5rem 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-sm, 6px);
  color: var(--color-text-primary, #fff);
  font-size: 0.875rem;
  cursor: pointer;
}

.form-control:focus {
  outline: none;
  border-color: var(--color-primary, #636363);
}

.history-table-container {
  overflow-x: auto;
  border-radius: var(--radius-sm, 6px);
}

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.history-table th,
.history-table td {
  padding: 0.75rem;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.history-table th {
  color: var(--color-text-muted, #666);
  font-weight: 500;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: rgba(0, 0, 0, 0.2);
}

.history-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.03);
}

.row-failed {
  background: rgba(220, 38, 38, 0.05);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.5rem;
  border-radius: var(--radius-sm, 6px);
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: capitalize;
}

.status-badge.completed {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.status-badge.failed {
  background: rgba(220, 38, 38, 0.15);
  color: #f87171;
}

.status-badge.running {
  background: rgba(99, 99, 99, 0.15);
  color: var(--color-primary, #636363);
}

.job-name {
  font-weight: 500;
  color: var(--color-text-primary, #fff);
}

.timestamp {
  color: var(--color-text-secondary, #aaa);
  font-size: 0.8rem;
}

.duration {
  color: var(--color-text-secondary, #aaa);
  font-size: 0.8rem;
}

.results {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.result-found,
.result-requested {
  font-size: 0.8rem;
}

.result-found {
  color: var(--color-text-primary, #fff);
}

.result-requested {
  color: var(--color-primary, #636363);
}

.error-btn {
  background: transparent;
  border: none;
  color: #f87171;
  cursor: pointer;
  padding: 0.35rem;
  font-size: 0.9rem;
  border-radius: var(--radius-sm, 6px);
  transition: all 0.15s ease;
}

.error-btn:hover {
  color: #fca5a5;
  background: rgba(220, 38, 38, 0.1);
}

.no-error {
  color: var(--color-text-muted, #666);
}

.empty-history {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: var(--color-text-muted, #666);
}

.empty-history i {
  font-size: 2rem;
  margin-bottom: 0.75rem;
}

.empty-history p {
  font-size: 0.9rem;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.page-btn {
  padding: 0.5rem 0.75rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-sm, 6px);
  color: var(--color-text-primary, #fff);
  cursor: pointer;
  transition: all 0.15s ease;
}

.page-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.12);
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-info {
  font-size: 0.85rem;
  color: var(--color-text-secondary, #aaa);
}

/* Error Detail Modal */
.error-detail-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.error-detail-modal {
  background: var(--color-bg-content, #1a1a1c);
  border-radius: var(--radius-lg, 12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.error-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.error-header h3 {
  margin: 0;
  font-size: 1rem;
  color: #f87171;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.error-body {
  padding: 1.25rem;
  overflow-y: auto;
}

.error-info {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  color: var(--color-text-primary, #fff);
}

.error-label {
  color: var(--color-text-secondary, #aaa);
}

.error-message-box {
  margin-top: 1rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: var(--radius-sm, 6px);
  border: 1px solid rgba(220, 38, 38, 0.2);
}

.error-message-box pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  font-size: 0.8rem;
  color: #fca5a5;
  line-height: 1.5;
}

.error-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  padding: 1rem 1.25rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: var(--radius-sm, 6px);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.btn-outline {
  background: transparent;
  color: var(--color-text-primary, #fff);
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.btn-outline:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.25);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-text-primary, #fff);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.12);
}

/* Responsive */
@media (max-width: 768px) {
  .history-table th:nth-child(4),
  .history-table td:nth-child(4) {
    display: none;
  }

  .results {
    flex-direction: row;
    gap: 0.5rem;
  }
}

@media (max-width: 600px) {
  .history-modal {
    max-height: 100vh;
    border-radius: 0;
  }

  .modal-overlay {
    padding: 0;
  }

  .history-table th:nth-child(3),
  .history-table td:nth-child(3) {
    display: none;
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
