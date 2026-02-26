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
        <div class="summary-bar" :class="{ empty: items.length === 0 }">
          <span class="summary-count">
            <i class="fas fa-list-ul"></i>
            <strong>{{ items.length }}</strong> item{{ items.length !== 1 ? 's' : '' }} would be requested
          </span>
          <span class="summary-note">
            <i class="fas fa-shield-alt"></i>
            No actual requests were made
          </span>
        </div>

        <!-- Empty state -->
        <div v-if="items.length === 0" class="empty-state">
          <i class="fas fa-check-circle"></i>
          <p>Nothing new to request</p>
          <span>All matching content is already downloaded, requested, or the filters returned no results.</span>
        </div>

        <!-- Items list -->
        <div v-else class="items-list">
          <div v-for="item in items" :key="item.tmdb_id" class="item-card">
            <!-- Poster -->
            <div class="item-poster">
              <img
                v-if="item.poster_path"
                :src="`https://image.tmdb.org/t/p/w92${item.poster_path}`"
                :alt="item.title"
                loading="lazy"
              />
              <div v-else class="poster-placeholder">
                <i :class="item.media_type === 'tv' ? 'fas fa-tv' : 'fas fa-film'"></i>
              </div>
            </div>

            <!-- Info -->
            <div class="item-info">
              <div class="item-title">{{ item.title }}</div>
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
        <button @click="$emit('run')" class="btn btn-primary" v-if="items.length > 0">
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
  methods: {
    releaseYear(item) {
      const date = item.release_date;
      return date ? date.slice(0, 4) : null;
    },
    truncate(text, maxLen) {
      if (!text) return '';
      return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
    }
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
  max-width: 680px;
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
  gap: 1rem;
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

.summary-note {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.78rem;
  color: var(--color-text-muted, #888);
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

.item-title {
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--color-text-primary, #fff);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
