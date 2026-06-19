<template>
  <Teleport to="body">
    <transition name="request-details-fade">
      <div
        v-if="show && selectedSource"
        class="request-details-modal"
        @click.self="$emit('close')">
        <div class="request-details-modal__content">
          <button @click="$emit('close')" class="request-details-modal__close">
            <i class="fas fa-times"></i>
          </button>

          <div class="request-details-modal__layout">
            <div class="request-details-modal__poster-section">
              <div class="request-details-modal__poster-frame">
                <img
                  v-if="selectedSource.poster_path"
                  :src="selectedSource.poster_path"
                  :alt="selectedSource.title"
                  class="request-details-modal__poster" />
                <div v-else class="request-details-modal__poster-placeholder">
                  <i class="fas fa-image text-6xl"></i>
                </div>

                <div class="request-details-modal__poster-overlay request-details-modal__poster-overlay--top">
                  <span v-if="selectedSource.media_type" class="request-details-modal__poster-pill request-details-modal__poster-pill--media">
                    <i :class="selectedSource.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
                    {{ selectedSource.media_type.toUpperCase() }}
                  </span>
                  <span v-if="selectedSource.rating" class="request-details-modal__poster-pill request-details-modal__poster-pill--rating">
                    <i class="fas fa-star"></i>
                    {{ selectedSource.rating }}
                  </span>
                </div>

                <div v-if="posterDateLabel" class="request-details-modal__poster-overlay request-details-modal__poster-overlay--bottom">
                  <span class="request-details-modal__poster-date">
                    <i :class="selectedSource.requested_at ? 'fas fa-clock' : 'fas fa-calendar'"></i>
                    {{ posterDateLabel }}
                  </span>
                  <span v-if="requestMethodLabel" class="request-details-modal__poster-origin">
                    <i :class="requestMethodIcon"></i>
                    {{ requestMethodLabel }}
                  </span>
                </div>
              </div>
            </div>

            <div class="request-details-modal__details-section">
              <h2 class="request-details-modal__title">{{ selectedSource.title }}</h2>

              <div v-if="hasContextRows" class="request-details-modal__context">
                <div v-if="requestMethodLabel" class="request-details-modal__context-row">
                  <i :class="requestMethodIcon"></i>
                  <span>Request method <strong>{{ requestMethodLabel }}</strong></span>
                </div>
                <div v-if="selectedSource.release_date && selectedSource.requested_at" class="request-details-modal__context-row">
                  <i class="fas fa-calendar"></i>
                  <span>Released <strong>{{ selectedSource.release_date }}</strong></span>
                </div>
                <div v-if="selectedSource.source_origin === 'trakt_history'" class="request-details-modal__context-row">
                  <i class="fas fa-history"></i>
                  <span>Seed origin <strong>Trakt History</strong></span>
                </div>
                <div v-if="showSourceContent" class="request-details-modal__context-row">
                  <i class="fas fa-link"></i>
                  <span>Source content <strong>{{ selectedSource.source_title }}</strong></span>
                </div>
                <div v-if="selectedSource.user_name" class="request-details-modal__context-row">
                  <i class="fas fa-user"></i>
                  <span>Requested for <strong>{{ selectedSource.user_name }}</strong></span>
                </div>
              </div>

              <div class="request-details-modal__separator"></div>

              <div v-if="selectedSource.rationale" class="request-details-modal__section">
                <h3 class="request-details-modal__section-title" :class="{ 'request-details-modal__section-title--ai': selectedSource._isAiRequest }">
                  <i :class="selectedSource._isAiRequest ? 'fas fa-search' : 'fas fa-robot'"></i>
                  {{ selectedSource._isAiRequest ? 'Search Query' : 'AI Reasoning' }}
                </h3>
                <p class="request-details-modal__overview request-details-modal__overview--rationale" :class="{ 'request-details-modal__overview--ai': selectedSource._isAiRequest }">
                  {{ selectedSource.rationale }}
                </p>
              </div>

              <div class="request-details-modal__section">
                <h3 class="request-details-modal__section-title">
                  <i class="fas fa-align-left"></i>
                  Overview
                </h3>
                <p class="request-details-modal__overview">{{ selectedSource.overview || 'No overview available.' }}</p>
              </div>

              <div v-if="selectedSource.requests && selectedSource.requests.length > 0" class="request-details-modal__section">
                <h3 class="request-details-modal__section-title">
                  <i class="fas fa-list"></i>
                  Requested Media ({{ selectedSource.requests.length }})
                </h3>
                <div class="request-details-modal__requests-list">
                  <div
                    v-for="request in selectedSource.requests"
                    :key="request.request_id"
                    class="request-details-modal__request-item"
                    @click="$emit('select-related', request)">
                    <div class="request-details-modal__request-info">
                      <h4 class="request-details-modal__request-title">{{ request.title }}</h4>
                      <p class="request-details-modal__request-date">
                        <i class="fas fa-clock"></i>
                        Requested on {{ formatDate(request.requested_at) }}
                      </p>
                      <p v-if="request.user_name" class="request-details-modal__request-date">
                        <i class="fas fa-user"></i>
                        {{ request.user_name }}
                      </p>
                    </div>
                    <button class="request-details-modal__request-btn">
                      <i class="fas fa-external-link-alt"></i>
                      Details
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script>
import { formatDate } from '@/utils/dateUtils.js';

export default {
  name: 'RequestDetailsModal',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    selectedSource: {
      type: Object,
      default: null,
    },
  },
  emits: ['close', 'select-related'],
  computed: {
    posterDateLabel() {
      if (this.selectedSource?.requested_at) {
        return `Requested ${this.formatDate(this.selectedSource.requested_at)}`;
      }

      return this.selectedSource?.release_date || '';
    },
    hasContextRows() {
      return Boolean(
        this.requestMethodLabel ||
        (this.selectedSource?.release_date && this.selectedSource?.requested_at) ||
        this.selectedSource?.source_origin === 'trakt_history' ||
        this.showSourceContent ||
        this.selectedSource?.user_name
      );
    },
    showSourceContent() {
      return Boolean(this.selectedSource?.source_title && this.selectedSource?.source_id !== 'trakt_recommendations');
    },
    requestMethodLabel() {
      const sourceId = String(this.selectedSource?.source_id ?? this.selectedSource?.id ?? '');

      if (this.selectedSource?._isAiRequest || sourceId === 'ai_search') {
        return 'AI Search';
      }
      if (sourceId === 'trakt_recommendations') {
        return 'Trakt Recommendations';
      }
      if (sourceId === 'discover') {
        return 'Discover';
      }
      if (/^\d+$/.test(sourceId)) {
        return 'TMDB';
      }

      return '';
    },
    requestMethodIcon() {
      const sourceId = String(this.selectedSource?.source_id ?? this.selectedSource?.id ?? '');

      if (this.selectedSource?._isAiRequest || sourceId === 'ai_search') {
        return 'fas fa-magic';
      }
      if (sourceId === 'trakt_recommendations') {
        return 'icon-trakt';
      }
      if (sourceId === 'discover') {
        return 'fas fa-search';
      }

      return 'fas fa-database';
    },
  },
  methods: {
    formatDate,
  },
};
</script>

<style scoped>
.request-details-modal {
  position: fixed;
  inset: 0;
  background-color: var(--color-bg-overlay-heavy);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
  overflow-y: auto;
}

.request-details-modal__content {
  position: relative;
  background-color: var(--surface-overlay);
  backdrop-filter: blur(15px);
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border-light);
  max-width: 1200px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--modal-shadow);
  margin: auto;
}

.request-details-modal__close {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: 50%;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: var(--transition-base);
  z-index: 10;
}

.request-details-modal__close:hover {
  background-color: var(--color-danger);
  color: var(--color-text-primary);
  border-color: var(--color-danger);
  transform: rotate(90deg);
}

.request-details-modal__layout {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  padding: 2rem;
}

.request-details-modal__poster-section {
  flex-shrink: 0;
  width: 100%;
}

.request-details-modal__poster-frame {
  position: relative;
  width: 100%;
  aspect-ratio: 2/3;
  overflow: hidden;
  background-color: var(--color-bg-primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--elevation-3);
}

.request-details-modal__poster-frame::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    var(--color-bg-overlay-light),
    transparent 32%,
    transparent 58%,
    var(--surface-overlay)
  );
  opacity: var(--alpha-80);
  pointer-events: none;
}

.request-details-modal__poster {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.request-details-modal__poster-placeholder {
  width: 100%;
  height: 100%;
  background-color: var(--color-bg-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
}

.request-details-modal__poster-overlay {
  position: absolute;
  z-index: 1;
  display: flex;
  pointer-events: none;
}

.request-details-modal__poster-overlay--top {
  top: var(--spacing-sm);
  right: var(--spacing-sm);
  left: var(--spacing-sm);
  justify-content: space-between;
  gap: var(--spacing-xs);
}

.request-details-modal__poster-overlay--bottom {
  right: 0;
  bottom: 0;
  left: 0;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  padding: var(--spacing-3xl) var(--spacing-sm) var(--spacing-sm);
}

.request-details-modal__poster-pill,
.request-details-modal__poster-date,
.request-details-modal__poster-origin {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  min-width: 0;
  border: 1px solid var(--surface-glass-strong);
  border-radius: var(--radius-full);
  background-color: var(--color-bg-overlay-heavy);
  color: var(--color-text-primary);
  box-shadow: var(--shadow-sm);
  font-size: var(--font-size-xs);
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.request-details-modal__poster-pill {
  padding: var(--spacing-xs) var(--spacing-sm);
}

.request-details-modal__poster-pill--media {
  background-color: var(--color-primary-alpha-20);
  border-color: var(--color-primary-alpha-20);
  color: var(--color-primary-light);
}

.request-details-modal__poster-pill--rating {
  margin-left: auto;
  background-color: var(--color-success-alpha-20);
  border-color: var(--color-success-alpha-20);
  color: var(--color-success-light);
}

.request-details-modal__poster-date {
  max-width: 100%;
  padding: var(--spacing-xs) var(--spacing-sm);
  overflow: hidden;
  color: var(--color-warning-light);
  text-overflow: ellipsis;
}

.request-details-modal__poster-origin {
  padding: var(--spacing-xs) var(--spacing-sm);
  background-color: var(--color-info-alpha-20);
  border-color: var(--color-info-alpha-20);
  color: var(--color-info-light);
}

.request-details-modal__poster-pill i,
.request-details-modal__poster-date i,
.request-details-modal__poster-origin i {
  flex: 0 0 auto;
  font-size: var(--font-size-xs);
}

.request-details-modal__details-section {
  flex: 1;
  min-width: 0;
}

.request-details-modal__title {
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-md);
  line-height: 1.2;
  word-wrap: break-word;
}

.request-details-modal__context {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.request-details-modal__context-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  padding: var(--spacing-sm) calc(var(--spacing-sm) + var(--spacing-xs));
  background-color: var(--color-bg-primary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-light);
}

.request-details-modal__context-row i {
  width: var(--spacing-md);
  color: var(--color-primary-light);
  text-align: center;
}

.request-details-modal__context-row strong {
  color: var(--color-primary);
}

.request-details-modal__separator {
  border-top: 1px solid var(--color-border-light);
  margin: var(--spacing-md) 0;
}

.request-details-modal__section {
  margin-bottom: 2rem;
}

.request-details-modal__section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 1rem;
}

.request-details-modal__section-title--ai {
  color: var(--color-info);
}

.request-details-modal__overview {
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.request-details-modal__overview--rationale {
  border-left: 3px solid var(--color-primary);
  padding-left: 1rem;
  margin-top: 0.5rem;
  white-space: pre-wrap;
  font-style: italic;
}

.request-details-modal__overview--ai {
  border-left-color: var(--color-info);
  font-style: normal;
}

.request-details-modal__requests-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.request-details-modal__request-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem;
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-base);
}

.request-details-modal__request-item:hover {
  background-color: var(--color-bg-interactive);
  border-color: var(--color-primary);
}

.request-details-modal__request-info {
  flex: 1;
}

.request-details-modal__request-title {
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 0.25rem;
}

.request-details-modal__request-date {
  font-size: 0.85rem;
  color: var(--color-text-muted);
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.request-details-modal__request-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background-color: var(--color-primary);
  color: var(--color-text-primary);
  border: none;
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition-base);
  flex-shrink: 0;
}

.request-details-modal__request-btn:hover {
  background-color: var(--color-primary-hover);
}

.request-details-fade-enter-active,
.request-details-fade-leave-active {
  transition: opacity 0.3s ease;
}

.request-details-fade-enter-from,
.request-details-fade-leave-to {
  opacity: 0;
}

@media (min-width: 768px) {
  .request-details-modal__layout {
    flex-direction: row;
    gap: 3rem;
    padding: 3rem;
  }

  .request-details-modal__poster-section {
    width: 300px;
  }
}

@media (min-width: 1024px) {
  .request-details-modal__layout {
    gap: 3.5rem;
    padding: 3.5rem 4rem;
  }
}
</style>
