<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="dryrun-modal">
      <!-- Header -->
      <div class="modal-header">
        <div class="header-title">
          <i class="fas fa-eye header-icon"></i>
          <div>
            <h2>Dry Run Preview</h2>
            <span class="job-subtitle">{{ job.name }}</span>
          </div>
        </div>
        <button @click="$emit('close')" class="close-btn" title="Close">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <!-- Body -->
      <div class="modal-body">
        <!-- Summary bar -->
        <div class="summary-bar" :class="{ empty: wouldRequestCount === 0 }">
          <span class="summary-count">
            <i class="fas fa-list-ul"></i>
            <strong>{{ wouldRequestCount }}</strong> item{{ wouldRequestCount !== 1 ? 's' : '' }} would be requested
          </span>
          <span v-if="filteredOutCount > 0" class="summary-filtered">
            <i class="fas fa-filter"></i>
            {{ filteredOutCount }} filtered out
          </span>
          <span class="summary-note">
            <i class="fas fa-shield-alt"></i>
            No actual requests were made
          </span>
        </div>

        <!-- View toggle (only when there are filtered items) -->
        <div v-if="hasFilterData && filteredOutCount > 0" class="view-toggle">
          <button
            :class="['toggle-btn', { active: showAll }]"
            @click="showAll = true"
          >
            <i class="fas fa-th-list"></i> All ({{ items.length }})
          </button>
          <button
            :class="['toggle-btn', { active: !showAll }]"
            @click="showAll = false"
          >
            <i class="fas fa-check-circle"></i> Would be requested ({{ wouldRequestCount }})
          </button>
        </div>

        <!-- Empty state -->
        <div v-if="displayedItems.length === 0" class="empty-state">
          <i class="fas fa-check-circle"></i>
          <p>Nothing new to request</p>
          <span>All matching content is already downloaded, requested, or the filters returned no results.</span>
        </div>

        <!-- Items list -->
        <div v-else class="items-list">
          <div
            v-for="item in displayedItems"
            :key="item.tmdb_id"
            class="item-card"
            :class="{ 'item-filtered': !itemWouldRequest(item) }"
          >
            <!-- Poster -->
            <div class="item-poster">
              <img
                v-if="item.poster_path"
                :src="posterUrl(item)"
                :alt="item.title"
                loading="lazy"
              />
              <div v-else class="poster-placeholder">
                <i :class="item.media_type === 'tv' ? 'fas fa-tv' : 'fas fa-film'"></i>
              </div>
            </div>

            <!-- Info -->
            <div class="item-info">
              <div class="item-header-row">
                <div class="item-title">{{ item.title }}</div>
                <!-- Library status badges -->
                <span v-if="item.already_downloaded" class="status-badge downloaded">
                  <i class="fas fa-check"></i> In Library
                </span>
                <span v-else-if="item.already_requested" class="status-badge requested">
                  <i class="fas fa-clock"></i> Requested
                </span>
                <span v-else-if="itemWouldRequest(item)" class="status-badge will-request">
                  <i class="fas fa-plus"></i> Will Request
                </span>
              </div>

              <div class="item-meta">
                <span class="media-type-badge" :class="item.media_type">
                  {{ item.media_type === 'tv' ? 'TV' : 'Movie' }}
                </span>
                <span v-if="releaseYear(item)" class="item-year">{{ releaseYear(item) }}</span>
                <span v-if="item.vote_average" class="item-rating">
                  <i class="fas fa-star"></i>
                  {{ Number(item.vote_average).toFixed(1) }}
                </span>
              </div>

              <!-- Filter badges -->
              <div v-if="hasFilters(item)" class="filter-badges">
                <template v-for="(filter, key) in activeFilters(item)" :key="key">
                  <span
                    v-if="filter.passed !== undefined"
                    class="filter-badge"
                    :class="filterBadgeClass(filter)"
                    :title="filterTitle(filter)"
                  >
                    <i :class="filterIcon(filter)"></i>
                    {{ filter.label }}
                    <span v-if="filter.value != null" class="filter-value">{{ filter.value }}</span>
                  </span>
                </template>
              </div>

              <div v-if="item.rationale" class="item-rationale">
                <i class="fas fa-magic"></i> {{ item.rationale }}
              </div>
              <div v-if="item.overview" class="item-overview">
                {{ truncate(item.overview, 130) }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="modal-footer">
        <button @click="$emit('close')" class="btn btn-secondary">
          <i class="fas fa-times"></i> Close
        </button>
        <button @click="$emit('run')" class="btn btn-primary" v-if="wouldRequestCount > 0">
          <i class="fas fa-bolt"></i> Run Job Now
        </button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DryRunResultModal',
  props: {
    job: {
      type: Object,
      required: true
    },
    items: {
      type: Array,
      default: () => []
    }
  },
  emits: ['close', 'run'],
  data() {
    return {
      showAll: true,
    };
  },
  computed: {
    hasFilterData() {
      return this.items.some(i => i.filter_results != null);
    },
    wouldRequestCount() {
      return this.items.filter(i => this.itemWouldRequest(i)).length;
    },
    filteredOutCount() {
      return this.items.length - this.wouldRequestCount;
    },
    displayedItems() {
      if (!this.hasFilterData || this.showAll) return this.items;
      return this.items.filter(i => this.itemWouldRequest(i));
    },
  },
  methods: {
    itemWouldRequest(item) {
      // New format: explicit would_request flag
      if (item.would_request !== undefined) return item.would_request;
      // Legacy format: no filter data means it passed everything
      return true;
    },
    posterUrl(item) {
      const p = item.poster_path;
      if (!p) return null;
      if (p.startsWith('http')) return p;
      return `https://image.tmdb.org/t/p/w92${p}`;
    },
    releaseYear(item) {
      const date = item.release_date;
      return date ? date.slice(0, 4) : null;
    },
    truncate(text, maxLen) {
      if (!text) return '';
      return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
    },
    hasFilters(item) {
      if (!item.filter_results) return false;
      return Object.keys(item.filter_results).some(k => k !== 'passed');
    },
    activeFilters(item) {
      if (!item.filter_results) return {};
      const { passed, ...filters } = item.filter_results; // eslint-disable-line no-unused-vars
      return filters;
    },
    filterBadgeClass(filter) {
      if (filter.passed === true) return 'badge-pass';
      if (filter.passed === false) return 'badge-fail';
      return 'badge-na';
    },
    filterIcon(filter) {
      if (filter.passed === true) return 'fas fa-check';
      if (filter.passed === false) return 'fas fa-times';
      return 'fas fa-minus';
    },
    filterTitle(filter) {
      if (filter.reason) return filter.reason;
      if (filter.passed === true) return `${filter.label}: OK`;
      if (filter.passed === null) return `${filter.label}: not configured`;
      return filter.label;
    },
  }
};
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dryrun-modal {
  background: var(--color-bg-content, #1a1a1c);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-lg, 12px);
  width: 90%;
  max-width: 720px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.header-icon {
  font-size: 1.4rem;
  color: #22d3ee;
}

.modal-header h2 {
  margin: 0 0 0.15rem 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-text-primary, #fff);
}

.job-subtitle {
  font-size: 0.8rem;
  color: var(--color-text-muted, #888);
}

.close-btn {
  background: none;
  border: none;
  color: var(--color-text-muted, #888);
  cursor: pointer;
  font-size: 1rem;
  padding: 0.3rem;
  transition: color 0.15s;
}

.close-btn:hover {
  color: var(--color-text-primary, #fff);
}

/* Body */
.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

/* Summary bar */
.summary-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: rgba(6, 182, 212, 0.08);
  border: 1px solid rgba(6, 182, 212, 0.2);
  border-radius: var(--radius-sm, 6px);
  font-size: 0.875rem;
}

.summary-bar.empty {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
}

.summary-count {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #22d3ee;
  font-weight: 500;
}

.summary-count i {
  opacity: 0.7;
}

.summary-filtered {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.78rem;
  color: #fb923c;
}

.summary-note {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.78rem;
  color: var(--color-text-muted, #888);
}

/* View toggle */
.view-toggle {
  display: flex;
  gap: 0.4rem;
  flex-shrink: 0;
}

.toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.75rem;
  font-size: 0.78rem;
  border-radius: var(--radius-sm, 6px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  color: var(--color-text-muted, #888);
  cursor: pointer;
  transition: all 0.15s;
}

.toggle-btn.active {
  background: rgba(34, 211, 238, 0.12);
  border-color: rgba(34, 211, 238, 0.35);
  color: #22d3ee;
}

.toggle-btn:hover:not(.active) {
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-text-primary, #fff);
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2.5rem 1rem;
  text-align: center;
  gap: 0.5rem;
}

.empty-state i {
  font-size: 2.5rem;
  color: #00c896;
  margin-bottom: 0.5rem;
}

.empty-state p {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-primary, #fff);
  margin: 0;
}

.empty-state span {
  font-size: 0.85rem;
  color: var(--color-text-muted, #888);
  max-width: 380px;
}

/* Items list */
.items-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.item-card {
  display: flex;
  gap: 0.9rem;
  padding: 0.85rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: var(--radius-sm, 6px);
  transition: border-color 0.15s;
}

.item-card:hover {
  border-color: rgba(255, 255, 255, 0.14);
}

.item-card.item-filtered {
  opacity: 0.6;
  border-color: rgba(255, 255, 255, 0.04);
}

.item-card.item-filtered:hover {
  opacity: 0.8;
}

/* Poster */
.item-poster {
  flex-shrink: 0;
  width: 46px;
  height: 69px;
  border-radius: 4px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.06);
}

.item-poster img {
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
  color: var(--color-text-muted, #888);
  font-size: 1.1rem;
}

/* Item info */
.item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.item-header-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  min-width: 0;
}

.item-title {
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--color-text-primary, #fff);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

/* Status badges */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.62rem;
  font-weight: 600;
  padding: 0.12rem 0.4rem;
  border-radius: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.status-badge.will-request {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.status-badge.downloaded {
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
}

.status-badge.requested {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.media-type-badge {
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.15rem 0.4rem;
  border-radius: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.media-type-badge.movie {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.media-type-badge.tv {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.item-year {
  font-size: 0.78rem;
  color: var(--color-text-muted, #888);
}

.item-rating {
  font-size: 0.78rem;
  color: #fbbf24;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

/* Filter badges row */
.filter-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.1rem;
}

.filter-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.62rem;
  font-weight: 500;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  cursor: default;
  white-space: nowrap;
}

.filter-badge i {
  font-size: 0.55rem;
}

.filter-value {
  opacity: 0.75;
  font-weight: 400;
}

.badge-pass {
  background: rgba(34, 197, 94, 0.12);
  color: #4ade80;
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.badge-fail {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.badge-na {
  background: rgba(255, 255, 255, 0.05);
  color: var(--color-text-muted, #888);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.item-rationale {
  font-size: 0.78rem;
  color: #c084fc;
  font-style: italic;
  display: flex;
  align-items: flex-start;
  gap: 0.35rem;
}

.item-rationale i {
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.item-overview {
  font-size: 0.78rem;
  color: var(--color-text-muted, #888);
  line-height: 1.4;
}

/* Footer */
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.6rem 1rem;
  border-radius: var(--radius-sm, 6px);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
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
}

@media (max-width: 600px) {
  .dryrun-modal {
    max-width: 100%;
    max-height: 100vh;
    border-radius: 0;
  }

  .summary-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .modal-footer {
    flex-direction: column-reverse;
  }

  .modal-footer .btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
