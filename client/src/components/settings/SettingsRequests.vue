<template>
  <div class="requests-wrapper">
    <!-- Quick Stats Header -->
    <div class="requests-stats-header" :class="{ 'has-approval': approvalEnabled }">
      <div class="stat-card-mini">
        <div class="stat-icon">
          <i class="fas fa-paper-plane"></i>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total || 0 }}</div>
          <div class="stat-label">Total Requests</div>
        </div>
      </div>

      <div class="stat-card-mini">
        <div class="stat-icon today">
          <i class="fas fa-calendar-day"></i>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.today || 0 }}</div>
          <div class="stat-label">Today</div>
        </div>
      </div>

      <div class="stat-card-mini">
        <div class="stat-icon week">
          <i class="fas fa-calendar-week"></i>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.this_week || 0 }}</div>
          <div class="stat-label">This Week</div>
        </div>
      </div>

      <div class="stat-card-mini">
        <div class="stat-icon month">
          <i class="fas fa-calendar-alt"></i>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.this_month || 0 }}</div>
          <div class="stat-label">This Month</div>
        </div>
      </div>

      <div v-if="approvalEnabled" class="stat-card-mini">
        <div class="stat-icon pending"><i class="fas fa-hourglass-half"></i></div>
        <div class="stat-info">
          <div class="stat-value">{{ pendingTotal }}</div>
          <div class="stat-label">Awaiting Approval</div>
        </div>
      </div>
    </div>

    <!-- Recent Requests Preview -->
    <div class="recent-requests-preview">
      <div class="preview-header">
        <h3 class="preview-title">
          <i class="fas fa-history"></i>
          Recent Requests
        </h3>
      </div>

      <!-- Skeleton Loading State -->
      <div v-if="loading" class="requests-skeleton">
        <div 
          v-for="i in 5" 
          :key="i" 
          class="skeleton-card">
          <div class="skeleton-poster"></div>
          <div class="skeleton-content">
            <div class="skeleton-title"></div>
            <div class="skeleton-meta">
              <div class="skeleton-badge"></div>
              <div class="skeleton-date"></div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="filteredRequests.length === 0" class="empty-state">
        <i class="fas fa-inbox"></i>
        <p>{{ activeFilter === 'all' ? 'No requests yet' : `No ${activeFilter}s found` }}</p>
      </div>

      <div v-else class="requests-container">
        <div class="requests-grid-preview">
          <div
            v-for="request in filteredRequests"
            :key="request._key"
            class="request-card-compact"
            @click="openDetails(request)">

            <div class="request-poster-compact">
              <img
                v-if="request.poster_path"
                :src="request.poster_path"
                :alt="request.title"
                loading="lazy" />
              <div v-else class="poster-placeholder">
                <i class="fas fa-image"></i>
              </div>

              <!-- Media Type Badge -->
              <span class="badge-media-compact">
                <i :class="request.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
              </span>
              <div v-if="request._pending" class="pending-card-actions" @click.stop>
                <template v-if="confirmRejectId === request.id"><button type="button" class="poster-action pending-cancel" aria-label="Cancel rejection" @click="confirmRejectId = null"><i class="fas fa-undo"></i></button><button type="button" class="poster-action pending-reject" :disabled="actionLoadingId === request.id" aria-label="Confirm rejection" @click="decidePending('reject', request.id)"><i class="fas fa-check"></i></button></template>
                <template v-else><button type="button" class="poster-action pending-approve" :disabled="actionLoadingId === request.id" aria-label="Approve request" @click="decidePending('approve', request.id)"><i class="fas fa-check"></i></button><button type="button" class="poster-action pending-reject" :disabled="actionLoadingId === request.id" aria-label="Reject request" @click="confirmRejectId = request.id"><i class="fas fa-times"></i></button></template>
              </div>
            </div>

            <div class="request-info-compact">
              <h4 class="request-title-compact">{{ request.title }}</h4>
              <span class="request-date-compact">
                <i class="fas fa-clock"></i>
                {{ request._pending ? 'Awaiting approval' : formatDate(request.requested_at) }}
              </span>
              <span v-if="request.user_name || request.user_id" class="request-date-compact">
                <i class="fas fa-user"></i>
                For {{ request.user_name || request.user_id }}
              </span>
            </div>
          </div>
        </div>

        <!-- Fade Overlay & View All Button -->
        <div v-if="recentRequests.length > 0" class="fade-overlay">
          <button
            @click="goToRequestsPage"
            class="btn-view-all-overlay">
            <span>View All {{ totalRequests }} Requests</span>
            <i class="fas fa-arrow-right"></i>
          </button>
        </div>
      </div>
    </div>
    <Teleport to="body">
      <div v-if="selectedRequest" class="modal-overlay" @click.self="selectedRequest = null">
        <div class="modal-content request-details-modal">
          <button type="button" class="modal-close" aria-label="Close details" @click="selectedRequest = null"><i class="fas fa-times"></i></button>
          <div class="modal-layout">
            <div class="modal-poster-section"><img v-if="selectedRequest.poster_path" :src="selectedRequest.poster_path" :alt="selectedRequest.title" class="modal-poster" /><div v-else class="modal-poster-placeholder"><i class="fas fa-image"></i></div></div>
            <div class="modal-details-section">
              <h2 class="modal-title">{{ selectedRequest.title }}</h2>
              <div class="badge-container"><span class="badge badge-media"><i :class="selectedRequest.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i> {{ selectedRequest.media_type?.toUpperCase() }}</span><span class="badge badge-rating"><i class="fas fa-star"></i> {{ selectedRequest.rating || 'N/A' }}</span><span v-if="selectedRequest.release_date" class="badge badge-date"><i class="fas fa-calendar"></i> {{ selectedRequest.release_date }}</span></div>
              <div v-if="selectedRequest.source_title" class="source-link-modal"><i class="fas fa-link"></i><span>Requested from: <strong>{{ selectedRequest.source_title }}</strong></span></div>
              <div v-if="selectedRequest.user_name || selectedRequest.user_id" class="source-link-modal"><i class="fas fa-user"></i><span>Requested for: <strong>{{ selectedRequest.user_name || selectedRequest.user_id }}</strong></span></div>
              <div class="modal-separator"></div>
              <div class="modal-section"><h3 class="modal-section-title"><i class="fas fa-align-left"></i> Overview</h3><p class="modal-overview">{{ selectedRequest.overview || 'No overview available.' }}</p></div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script>
import axios from 'axios';
import { formatDate } from '@/utils/dateUtils.js';
import '@/assets/styles/requestsPage.css';

export default {
  name: 'SettingsRequests',
  data() {
    return {
      stats: {
        total: 0,
        today: 0,
        this_week: 0,
        this_month: 0
      },
      recentRequests: [],
      pendingRequests: [],
      pendingTotal: 0,
      confirmRejectId: null,
      actionLoadingId: null,
      approvalEnabled: false,
      selectedRequest: null,
      totalRequests: 0,
      loading: false,
      activeFilter: 'all',
      filters: [
        { value: 'all', label: 'All', icon: 'fas fa-list' },
        { value: 'movie', label: 'Movies', icon: 'fas fa-film' },
        { value: 'tv', label: 'TV Shows', icon: 'fas fa-tv' }
      ]
    };
  },
  computed: {
    filteredRequests() {
      const requests = [...this.pendingRequests, ...this.recentRequests];
      if (this.activeFilter === 'all') {
        return requests.slice(0, 20);
      }
      return requests.filter(req => req.media_type === this.activeFilter).slice(0, 20);
    }
  },
  mounted() {
    this.loadStats();
    this.loadRecentRequests();
    this.loadApprovalState();
  },
  methods: {
    formatDate,

    async loadStats() {
      try {
        const response = await axios.get('/api/automation/requests/stats');
        this.stats = response.data;
        this.totalRequests = response.data.total || 0;
      } catch (error) {
        console.error('Error loading request stats:', error);
      }
    },

    async loadRecentRequests() {
      this.loading = true;
      try {
        const response = await axios.get('/api/automation/requests', {
          params: {
            page: 1,
            sort_by: 'date-desc'
          }
        });

        const allRequests = response.data.data.flatMap(source =>
          source.requests.map(req => ({
            ...req,
            source_title: source.source_title
          }))
        );

        // Sort by date (newest first)
        allRequests.sort((a, b) => {
          const dateA = new Date(a.requested_at);
          const dateB = new Date(b.requested_at);
          return dateB - dateA;
        });

        this.recentRequests = allRequests.slice(0, 20).map(request => ({ ...request, _key: `sent-${request.request_id}` }));
      } catch (error) {
        console.error('Error loading recent requests:', error);
      } finally {
        this.loading = false;
      }
    },

    async loadPendingRequests() {
      try {
        const { data } = await axios.get('/api/automation/requests/workflow', { params: { status: 'awaiting_approval', page: 1, per_page: 20 } });
        this.pendingRequests = (data.items || []).map(item => ({ ...item, _pending: true, _key: `pending-${item.id}`, requested_at: item.created_at, source_title: item.name, poster_path: item.poster_path ? `https://image.tmdb.org/t/p/w500${item.poster_path}` : null }));
        this.pendingTotal = data.total || 0;
      } catch (error) {
        console.error('Error loading pending requests:', error);
      }
    },

    async loadApprovalState() {
      try {
        const { data } = await axios.get('/api/jobs');
        await this.loadPendingRequests();
        this.approvalEnabled = this.pendingTotal > 0 || (data.jobs || []).some(job =>
          job.delivery_mode === 'manual' ||
          ((job.delivery_mode || 'inherit') === 'inherit' && data.request_approval_default !== false)
        );
      } catch (error) {
        console.error('Error loading approval jobs:', error);
      }
    },

    async decidePending(action, id) {
      this.actionLoadingId = id;
      try {
        await axios.post(`/api/automation/requests/workflow/${action}`, { ids: [id] });
        this.confirmRejectId = null;
        await this.loadPendingRequests();
        this.$toast.open({ message: action === 'approve' ? 'Request queued for Seer' : 'Request rejected', type: 'success' });
      } finally {
        this.actionLoadingId = null;
      }
    },



    getStatusClass(status) {
      return status || 'pending';
    },

    goToRequestsPage() {
      this.$router.push('/requests');
    },

    openDetails(request) {
      this.selectedRequest = request;
    }
  }
};
</script>

<style scoped>
/* Gli stili rimangono identici alla versione precedente */
.requests-wrapper {
  width: 100%;
}

/* Stats Header */
.requests-stats-header {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1.25rem;
  margin-bottom: 2rem;
}

.requests-stats-header.has-approval { grid-template-columns: repeat(5, 1fr); }

.pending-card-actions { position: absolute; right: var(--spacing-sm); bottom: var(--spacing-sm); display: flex; gap: var(--spacing-sm); z-index: 3; }
.poster-action { display: grid; place-items: center; width: var(--btn-height-md); height: var(--btn-height-md); padding: 0; border: 1px solid var(--color-border-medium); border-radius: var(--radius-full); color: var(--color-text-primary); cursor: pointer; box-shadow: var(--shadow-md); }
.pending-approve { color: var(--color-text-primary); background: var(--color-success); }
.pending-reject { color: var(--color-text-primary); background: var(--color-error); }
.pending-cancel { background: var(--surface-elevated-solid); }

@media (max-width: 992px) {
  .requests-stats-header {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stat-card-mini {
  background: var(--surface-glass-light);
  border: 1px solid var(--surface-glass-medium);
  border-radius: 14px;
  padding: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1.25rem;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: var(--elevation-1);
}

.stat-card-mini:hover {
  background: var(--surface-glass-medium);
  transform: translateY(-4px);
  box-shadow: var(--elevation-3);
  border-color: rgba(255, 255, 255, 0.18);
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(148, 163, 184, 0.25) 0%, rgba(100, 116, 139, 0.2) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 0.3s ease;
}

.stat-card-mini:hover .stat-icon {
  transform: scale(1.05);
}

.stat-icon.today {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.3) 0%, rgba(37, 99, 235, 0.2) 100%);
}

.stat-icon.week {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.3) 0%, rgba(5, 150, 105, 0.2) 100%);
}

.stat-icon.month {
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.3) 0%, rgba(109, 40, 217, 0.2) 100%);
}

.stat-icon i {
  font-size: 1.375rem;
  color: #e5e7eb;
}

.stat-icon.today i {
  color: #93c5fd;
}

.stat-icon.week i {
  color: #6ee7b7;
}

.stat-icon.month i {
  color: #c4b5fd;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: #f3f4f6;
  line-height: 1;
  margin-bottom: 0.375rem;
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 0.875rem;
  color: #9ca3af;
  font-weight: 500;
}

/* Recent Requests Preview */
.recent-requests-preview {
  background: var(--surface-glass-subtle);
  border: 1px solid var(--surface-glass-medium);
  border-radius: 14px;
  padding: 1.75rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.preview-header {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  margin-bottom: 1.75rem;
}

.preview-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.25rem;
  color: #f3f4f6;
  margin: 0;
}

/* Skeleton Loading */
.requests-skeleton {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
  margin-bottom: 1.5rem;
}

.skeleton-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: var(--surface-glass-subtle);
  border: 1px solid var(--surface-glass-light);
  border-radius: 10px;
}

.skeleton-poster {
  width: 48px;
  height: 72px;
  border-radius: 6px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.05) 25%, rgba(255, 255, 255, 0.1) 50%, rgba(255, 255, 255, 0.05) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

.skeleton-content {
  flex: 1;
}

.skeleton-title {
  height: 16px;
  width: 60%;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.05) 25%, rgba(255, 255, 255, 0.1) 50%, rgba(255, 255, 255, 0.05) 75%);
  background-size: 200% 100%;
  border-radius: 4px;
  margin-bottom: 0.75rem;
  animation: shimmer 1.5s infinite;
}

.skeleton-meta {
  display: flex;
  gap: 0.75rem;
}

.skeleton-badge,
.skeleton-date {
  height: 12px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.05) 25%, rgba(255, 255, 255, 0.1) 50%, rgba(255, 255, 255, 0.05) 75%);
  background-size: 200% 100%;
  border-radius: 4px;
  animation: shimmer 1.5s infinite;
}

.skeleton-badge {
  width: 60px;
}

.skeleton-date {
  width: 80px;
}

@keyframes shimmer {
  0% {
    background-position: -200% 0;
  }
  100% {
    background-position: 200% 0;
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3.5rem 2rem;
  color: #9ca3af;
}

.empty-state i {
  font-size: 2.5rem;
  margin-bottom: 1rem;
  opacity: 0.4;
}

/* Requests Container with Overlay */
.requests-container {
  position: relative;
  margin-bottom: 1.5rem;
}

/* Requests Grid Preview - Compact Layout */
.requests-grid-preview {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.75rem;
}

.request-card-compact {
  background: var(--surface-glass-subtle);
  border: 1px solid var(--surface-interactive);
  border-radius: 10px;
  transition: all 0.25s ease;
  overflow: hidden;
  box-shadow: var(--elevation-1);
}

.request-card-compact:hover {
  background: var(--surface-glass-light);
  border-color: rgba(148, 163, 184, 0.2);
  box-shadow: var(--elevation-2);
}

.request-poster-compact {
  width: 100%;
  aspect-ratio: 2/3;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, rgba(0, 0, 0, 0.7) 0%, rgba(0, 0, 0, 0.5) 100%);
}

.request-poster-compact img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.request-card-compact:hover .request-poster-compact img {
  transform: scale(1.03);
}

.poster-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 1.5rem;
}

.badge-media-compact {
  position: absolute;
  top: 0.375rem;
  right: 0.375rem;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(8px);
  padding: 0.25rem 0.375rem;
  border-radius: 5px;
  font-size: 0.65rem;
  color: #f3f4f6;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  z-index: 2;
}

.badge-media-compact i {
  font-size: 0.7rem;
}

.request-info-compact {
  padding: 0.625rem 0.625rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.request-title-compact {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--color-text-primary);
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}
.request-card-compact:hover .request-title-compact {
  color: #fff;
}

.request-date-compact {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.65rem;
  color: #9ca3af;
  font-weight: 500;
  transition: color 0.2s ease;
}

.request-card-compact:hover .request-date-compact {
  color: #cbd5e1;
}

.request-date-compact i {
  font-size: 0.625rem;
  opacity: 0.8;
}

/* Fade Overlay & View All Button */
.fade-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 50%;
  background: linear-gradient(to bottom, transparent 0%, rgba(10, 10, 10, 0.95) 100%);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 2rem;
  pointer-events: none;
  z-index: 10;
}

.btn-view-all-overlay {
  pointer-events: all;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 0.875rem 2rem;
  background-color: hsl(0, 0%, 24%);
  color: white;
  font-weight: 600;
  font-size: 0.9375rem;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 16px rgba(51, 52, 53, 0.4), 0 0 0 1px rgba(54, 50, 50, 0.1);
}

.btn-view-all-overlay:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4), 0 0 30px rgba(255, 255, 255, 0.3);
}

.btn-view-all-overlay i {
  transition: transform 0.3s ease;
}

.btn-view-all-overlay:hover i {
  transform: translateX(4px);
}

@media (max-width: 1400px) {
  .requests-grid-preview {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (max-width: 1100px) {
  .requests-grid-preview {
    grid-template-columns: repeat(3, 1fr);
  }

  .fade-overlay {
    height: 45%;
  }
}

@media (max-width: 768px) {
  .fade-overlay {
    height: 40%;
    padding-bottom: 1.5rem;
  }

  .btn-view-all-overlay {
    padding: 0.75rem 1.5rem;
    font-size: 0.875rem;
  }
}

/* Responsive */
@media (max-width: 768px) {
  .stat-card-mini {
    padding: 1.25rem;
  }

  .stat-icon {
    width: 44px;
    height: 44px;
  }

  .stat-value {
    font-size: 1.75rem;
  }

  .preview-header {
    gap: 1rem;
  }

  .requests-grid-preview {
    grid-template-columns: repeat(3, 1fr);
    gap: 0.625rem;
  }

  .request-title-compact {
    font-size: 0.7rem;
  }

  .request-date-compact {
    font-size: 0.625rem;
  }
}

@media (max-width: 480px) {
  .requests-stats-header {
    grid-template-columns: 1fr;
    gap: 0.875rem;
  }

  .stat-card-mini {
    padding: 1rem;
  }

  .recent-requests-preview {
    padding: 1.25rem;
  }

  .requests-grid-preview {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.5rem;
  }

  .request-info-compact {
    padding: 0.5rem;
  }

  .request-title-compact {
    font-size: 0.6875rem;
    min-height: 1.8em;
  }

  .badge-media-compact {
    padding: 0.2rem 0.3rem;
    font-size: 0.6rem;
  }

  .fade-overlay {
    height: 35%;
    padding-bottom: 1rem;
  }

  .btn-view-all-overlay {
    padding: 0.625rem 1.25rem;
    font-size: 0.8125rem;
    gap: 0.5rem;
  }
}
</style>
