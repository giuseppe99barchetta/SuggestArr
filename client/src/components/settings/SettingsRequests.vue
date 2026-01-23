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
        <div class="stat-icon today">
          <i class="fas fa-calendar-day"></i>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.today || 0 }}</div>
          <div class="stat-label">Today</div>
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
        
        <!-- Quick Filters -->
        <div class="quick-filters" v-if="!loading && recentRequests.length > 0">
          <button 
            v-for="filter in filters" 
            :key="filter.value"
            @click="activeFilter = filter.value"
            :class="['filter-badge', { active: activeFilter === filter.value }]">
            <i :class="filter.icon"></i>
            {{ filter.label }}
          </button>
        </div>
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

      <div v-else class="requests-grid-preview">
        <div 
          v-for="request in filteredRequests" 
          :key="request.request_id"
          class="request-card-preview"
          @click="goToRequestsPage">
          
          <div class="request-poster-mini">
            <img 
              v-if="request.poster_path" 
              :src="request.poster_path" 
              :alt="request.title"
              loading="lazy" />
            <div v-else class="poster-placeholder">
              <i class="fas fa-image"></i>
            </div>
          </div>

          <div class="request-info-mini">
            <h4 class="request-title-mini">{{ request.title }}</h4>
            
            <div class="request-meta">
              <span class="badge-media-mini">
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
        class="tab-button btn-view-all">
        <span>View All {{ totalRequests }} Requests</span>
        <i class="fas fa-arrow-right"></i>
      </button>
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import { formatDate } from '@/utils/dateUtils.js';

export default {
  name: 'SettingsRequests',
  data() {
    return {
      stats: {
        total: 0,
        today: 0
      },
      recentRequests: [],
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
      if (this.activeFilter === 'all') {
        return this.recentRequests;
      }
      return this.recentRequests.filter(req => req.media_type === this.activeFilter);
    }
  },
  mounted() {
    this.loadStats();
    this.loadRecentRequests();
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

        this.recentRequests = allRequests.slice(0, 10);
      } catch (error) {
        console.error('Error loading recent requests:', error);
      } finally {
        this.loading = false;
      }
    },



    getStatusClass(status) {
      return status || 'pending';
    },

    goToRequestsPage() {
      this.$router.push('/requests');
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
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1.25rem;
  margin-bottom: 2rem;
}

.stat-card-mini {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  padding: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1.25rem;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.stat-card-mini:hover {
  background: rgba(255, 255, 255, 0.12);
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
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

.stat-icon i {
  font-size: 1.375rem;
  color: #e5e7eb;
}

.stat-icon.today i {
  color: #93c5fd;
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
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
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

/* Quick Filters */
.quick-filters {
  display: flex;
  gap: 0.625rem;
  flex-wrap: wrap;
}

.filter-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 1rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-badge:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
  border-color: rgba(255, 255, 255, 0.15);
}

.filter-badge.active {
  background: rgba(59, 130, 246, 0.2);
  color: #93c5fd;
  border-color: rgba(59, 130, 246, 0.3);
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
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
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

/* Requests Grid Preview */
.requests-grid-preview {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
  margin-bottom: 1.5rem;
}

.request-card-preview {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.125rem;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.request-card-preview::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  width: 3px;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.request-card-preview:hover::before {
  opacity: 1;
}

.request-card-preview:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(148, 163, 184, 0.25);
  transform: translateX(6px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.request-poster-mini {
  width: 48px;
  height: 72px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  background: rgba(0, 0, 0, 0.4);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.request-poster-mini img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.request-card-preview:hover .request-poster-mini img {
  transform: scale(1.05);
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
  margin: 0 0 0.625rem 0;
  color: #f3f4f6;
  font-size: 0.9375rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.2s ease;
}

.request-card-preview:hover .request-title-mini {
  color: #fff;
}

.request-meta {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  flex-wrap: wrap;
}

.badge-media-mini {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  background: rgba(100, 116, 139, 0.35);
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #cbd5e1;
  border: 1px solid rgba(100, 116, 139, 0.2);
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
  font-size: 0.875rem;
}

.request-card-preview:hover .request-arrow {
  color: var(--color-primary);
  transform: translateX(4px);
}

/* View All Button */
.btn-view-all {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.625rem;
  width: 100%;
  padding: 1rem;
  border-radius: 10px;
  color: #cbd5e1;
  font-weight: 600;
  font-size: 0.9375rem;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn-view-all i {
  transition: transform 0.3s ease;
}

.btn-view-all:hover i {
  transform: translateX(4px);
}

/* Responsive */
@media (max-width: 768px) {
  .requests-stats-header {
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
  }

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

  .quick-filters {
    gap: 0.5rem;
  }

  .filter-badge {
    padding: 0.375rem 0.75rem;
    font-size: 0.75rem;
  }

  .request-card-preview {
    padding: 1rem;
  }

  .request-poster-mini {
    width: 40px;
    height: 60px;
  }

  .request-title-mini {
    font-size: 0.875rem;
  }

  .request-arrow {
    display: none;
  }
}

@media (max-width: 480px) {
  .requests-stats-header {
    grid-template-columns: 1fr;
  }

  .stat-card-mini {
    padding: 1rem;
  }

  .recent-requests-preview {
    padding: 1.25rem;
  }

  .request-card-preview {
    padding: 0.875rem;
  }

  .request-status {
    display: none;
  }
}
</style>
