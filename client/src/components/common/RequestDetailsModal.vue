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
              <img
                v-if="selectedSource.poster_path"
                :src="selectedSource.poster_path"
                :alt="selectedSource.title"
                class="request-details-modal__poster" />
              <div v-else class="request-details-modal__poster-placeholder">
                <i class="fas fa-image text-6xl"></i>
              </div>
            </div>

            <div class="request-details-modal__details-section">
              <h2 class="request-details-modal__title">{{ selectedSource.title }}</h2>

            <div class="request-details-modal__badges">
              <span class="request-details-modal__badge request-details-modal__badge--media">
                <i :class="selectedSource.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
                {{ selectedSource.media_type?.toUpperCase() }}
              </span>
              <span class="request-details-modal__badge request-details-modal__badge--rating">
                <i class="fas fa-star"></i>
                {{ selectedSource.rating || 'N/A' }}
              </span>
              <span class="request-details-modal__badge request-details-modal__badge--date">
                <i class="fas fa-calendar"></i>
                {{ selectedSource.release_date }}
              </span>
              <span v-if="selectedSource.requested_at" class="request-details-modal__badge request-details-modal__badge--requested">
                <i class="fas fa-clock"></i>
                Requested {{ formatDate(selectedSource.requested_at) }}
              </span>
              <span v-if="selectedSource.source_origin === 'trakt_history'" class="request-details-modal__badge request-details-modal__badge--date">
                <i class="fas fa-history"></i>
                Trakt History
              </span>
            </div>

            <div v-if="selectedSource.source_title" class="request-details-modal__source">
              <i class="fas fa-link"></i>
              <span>Requested from: <strong>{{ selectedSource.source_title }}</strong></span>
            </div>

            <div v-if="selectedSource.user_name" class="request-details-modal__source">
              <i class="fas fa-user"></i>
              <span>Requested for: <strong>{{ selectedSource.user_name }}</strong></span>
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

.request-details-modal__poster {
  width: 100%;
  height: auto;
  border-radius: var(--radius-lg);
  box-shadow: var(--elevation-3);
}

.request-details-modal__poster-placeholder {
  width: 100%;
  aspect-ratio: 2/3;
  background-color: var(--color-bg-primary);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
}

.request-details-modal__details-section {
  flex: 1;
  min-width: 0;
}

.request-details-modal__title {
  font-size: 2rem;
  font-weight: bold;
  color: var(--color-text-primary);
  margin-bottom: 1rem;
  line-height: 1.2;
  word-wrap: break-word;
}

.request-details-modal__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.request-details-modal__badge {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
}

.request-details-modal__badge i {
  font-size: 0.85rem;
}

.request-details-modal__badge--media {
  color: var(--color-info);
}

.request-details-modal__badge--rating {
  color: var(--color-success);
}

.request-details-modal__badge--date {
  color: var(--color-warning);
}

.request-details-modal__badge--requested {
  color: var(--color-primary);
}

.request-details-modal__source {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--color-text-muted);
  padding: 0.5rem 0.75rem;
  background-color: var(--color-bg-primary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-light);
  margin-bottom: 0.5rem;
}

.request-details-modal__source strong {
  color: var(--color-primary);
}

.request-details-modal__separator {
  border-top: 1px solid var(--color-border-light);
  margin: 1rem 0;
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
