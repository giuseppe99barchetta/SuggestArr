<template>
  <div class="requests-wrapper">
    <!-- Quick Stats Header -->
    <div class="requests-stats-header">
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
        <div class="stat-icon success">
          <i class="fas fa-check-circle"></i>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.approved || 0 }}</div>
          <div class="stat-label">Approved</div>
        </div>
      </div>

      <div class="stat-card-mini">
        <div class="stat-icon pending">
          <i class="fas fa-clock"></i>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.pending || 0 }}</div>
          <div class="stat-label">Pending</div>
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
    </div>

    <!-- View Full Page Button -->
    <div class="full-page-action">
      <router-link to="/requests" class="btn-view-full">
        <i class="fas fa-external-link-alt"></i>
        <span>Open Full Request Page</span>
      </router-link>
    </div>

    <!-- Quick Preview: Recent Requests -->
    <div class="recent-requests-preview">
      <h3 class="preview-title">
        <i class="fas fa-history"></i>
        Recent Requests
      </h3>

      <div v-if="loading" class="loading-state">
        <div class="spinner-small"></div>
        <p>Loading requests...</p>
      </div>

      <div v-else-if="recentRequests.length === 0" class="empty-state">
        <i class="fas fa-inbox"></i>
        <p>No requests yet</p>
      </div>

      <div v-else class="requests-grid-preview">
        <div 
          v-for="request in recentRequests" 
          :key="request.request_id"
          class="request-card-preview"
          @click="goToRequestsPage">
          
          <div class="request-poster-mini">
            <img 
              v-if="request.poster_path" 
              :src="request.poster_path" 
              :alt="request.title" />
            <div v-else class="poster-placeholder">
              <i class="fas fa-image"></i>
            </div>
          </div>

          <div class="request-info-mini">
            <h4 class="request-title-mini">{{ request.title }}</h4>
            
            <div class="request-meta">
              <span class="badge badge-media-mini">
                <i :class="request.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
                {{ request.media_type?.toUpperCase() }}
              </span>
              <span class="request-date-mini">
                <i class="fas fa-clock"></i>
                {{ formatDate(request.requested_at) }}
              </span>
            </div>
          </div>

          <i class="fas fa-chevron-right request-arrow"></i>
        </div>
      </div>

      <button 
        v-if="recentRequests.length > 0" 
        @click="goToRequestsPage" 
        class="btn-view-all">
        <span>View All {{ totalRequests }} Requests</span>
        <i class="fas fa-arrow-right"></i>
      </button>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'SettingsRequests',
  data() {
    return {
      stats: {
        total: 0,
        approved: 0,
        pending: 0,
        today: 0
      },
      recentRequests: [],
      totalRequests: 0,
      loading: false
    };
  },
  mounted() {
    this.loadStats();
    this.loadRecentRequests();
  },
  methods: {
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

        // Flatten first 10 requests
        const allRequests = response.data.data.flatMap(source => 
          source.requests.map(req => ({
            ...req,
            source_title: source.source_title
          }))
        );

        this.recentRequests = allRequests.slice(0, 10);
      } catch (error) {
        console.error('Error loading recent requests:', error);
      } finally {
        this.loading = false;
      }
    },

    formatDate(dateString) {
      if (!dateString) return 'N/A';
      const date = new Date(dateString);
      const diffMs = new Date() - date;
      const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
      
      if (diffDays === 0) return 'today';
      if (diffDays === 1) return 'yesterday';
      if (diffDays < 7) return `${diffDays} days ago`;
      if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
      return date.toLocaleDateString();
    },

    goToRequestsPage() {
      this.$router.push('/requests');
    }
  }
};
</script>

<style scoped>
.requests-wrapper {
  width: 100%;
}

/* Stats Header */
.requests-stats-header {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card-mini {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  transition: all 0.3s ease;
}

.stat-card-mini:hover {
  background: rgba(255, 255, 255, 0.08);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(148, 163, 184, 0.2) 0%, rgba(100, 116, 139, 0.15) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon.success {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.2) 0%, rgba(16, 185, 129, 0.15) 100%);
}

.stat-icon.pending {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(217, 119, 6, 0.15) 100%);
}

.stat-icon.today {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.2) 0%, rgba(37, 99, 235, 0.15) 100%);
}

.stat-icon i {
  font-size: 1.25rem;
  color: #e5e7eb;
}

.stat-icon.success i {
  color: #6ee7b7;
}

.stat-icon.pending i {
  color: #fbbf24;
}

.stat-icon.today i {
  color: #93c5fd;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: #f3f4f6;
  line-height: 1;
  margin-bottom: 0.25rem;
}

.stat-label {
  font-size: 0.8125rem;
  color: #9ca3af;
  font-weight: 500;
}

/* Full Page Action */
.full-page-action {
  margin-bottom: 1.5rem;
}

.btn-view-full {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem 1.5rem;
  background: linear-gradient(135deg, rgba(100, 116, 139, 0.3) 0%, rgba(71, 85, 105, 0.2) 100%);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 10px;
  color: #e5e7eb;
  text-decoration: none;
  font-weight: 600;
  transition: all 0.3s ease;
}

.btn-view-full:hover {
  background: linear-gradient(135deg, rgba(100, 116, 139, 0.4) 0%, rgba(71, 85, 105, 0.3) 100%);
  border-color: rgba(148, 163, 184, 0.5);
  transform: translateX(4px);
  color: #ffffff;
}

/* Recent Requests Preview */
.recent-requests-preview {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 1.5rem;
}

.preview-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.25rem;
  color: #f3f4f6;
  margin: 0 0 1.5rem 0;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  color: #9ca3af;
}

.spinner-small {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(148, 163, 184, 0.3);
  border-top-color: #94a3b8;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state i {
  font-size: 2rem;
  margin-bottom: 1rem;
  opacity: 0.5;
}

/* Requests Grid Preview */
.requests-grid-preview {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.request-card-preview {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.request-card-preview:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(148, 163, 184, 0.2);
  transform: translateX(4px);
}

.request-poster-mini {
  width: 48px;
  height: 72px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  background: rgba(0, 0, 0, 0.3);
}

.request-poster-mini img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.poster-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
}

.request-info-mini {
  flex: 1;
  min-width: 0;
}

.request-title-mini {
  margin: 0 0 0.5rem 0;
  color: #f3f4f6;
  font-size: 0.9375rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.request-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.badge-media-mini {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.625rem;
  background: rgba(100, 116, 139, 0.3);
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #cbd5e1;
}

.request-date-mini {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.8125rem;
  color: #9ca3af;
}

.request-arrow {
  color: #6b7280;
  transition: all 0.3s ease;
}

.request-card-preview:hover .request-arrow {
  color: #e5e7eb;
  transform: translateX(4px);
}

/* View All Button */
.btn-view-all {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.875rem;
  background: rgba(148, 163, 184, 0.1);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: #cbd5e1;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn-view-all:hover {
  background: rgba(148, 163, 184, 0.2);
  border-color: rgba(148, 163, 184, 0.3);
  color: #e5e7eb;
}

/* Responsive */
@media (max-width: 768px) {
  .requests-stats-header {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.75rem;
  }

  .stat-card-mini {
    padding: 1rem;
  }

  .stat-icon {
    width: 40px;
    height: 40px;
  }

  .stat-value {
    font-size: 1.5rem;
  }

  .request-card-preview {
    padding: 0.875rem;
  }

  .request-poster-mini {
    width: 40px;
    height: 60px;
  }

  .request-title-mini {
    font-size: 0.875rem;
  }
}
</style>
