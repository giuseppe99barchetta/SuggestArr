<template>
  <div class="request-card" :class="{ 'request-card--compact': compact }" @click="$emit('select', item)">
    <div class="request-card-poster">
      <img
        v-if="item.poster_path"
        :src="item.poster_path"
        :alt="item.title"
        class="poster-image"
        loading="lazy" />
      <div v-else class="poster-placeholder">
        <i :class="placeholderIcon"></i>
      </div>

      <div class="poster-overlay poster-overlay--top">
        <span class="poster-pill poster-pill--media">
          <i :class="item.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
          {{ item.media_type.toUpperCase() }}
        </span>
        <span v-if="showRating" class="poster-pill poster-pill--rating">
          <i class="fas fa-star"></i>
          {{ item.rating || 'N/A' }}
        </span>
      </div>

      <div class="poster-overlay poster-overlay--bottom">
        <span class="poster-date">
          <i class="fas fa-clock"></i>
          {{ formatDate(item.requested_at) }}
        </span>
        <span v-if="requestMethodLabel" class="poster-origin">
          <i :class="requestMethodIcon"></i>
          {{ requestMethodLabel }}
        </span>
      </div>
    </div>

    <div class="request-card-body">
      <h3 class="request-card-title">{{ item.title }}</h3>

      <div v-if="sourceMode === 'ai' && item.rationale" class="source-link">
        <i class="fas fa-search"></i>
        <span>Search: <em>"{{ item.rationale }}"</em></span>
      </div>
      <div v-else-if="sourceMode === 'ai'" class="source-link">
        <i class="fas fa-magic"></i>
        <span>From: <strong>AI Search</strong></span>
      </div>
      <div v-else-if="showSourceContent" class="source-link">
        <i class="fas fa-arrow-left"></i>
        <span>From: <strong>{{ sourceContentMetadata.label }}</strong></span>
      </div>
    </div>
  </div>
</template>

<script>
import { formatDate } from '@/utils/dateUtils.js';
import {
  getRequestMethodMetadata,
  getRequestSourceContentMetadata,
} from '@/utils/requestSourceMetadata.js';

export default {
  name: 'RequestPosterCard',
  props: {
    item: {
      type: Object,
      required: true,
    },
    compact: {
      type: Boolean,
      default: false,
    },
    placeholderIcon: {
      type: String,
      default: 'fas fa-image',
    },
    showMissingRating: {
      type: Boolean,
      default: true,
    },
    showSource: {
      type: Boolean,
      default: true,
    },
    sourceMode: {
      type: String,
      default: 'source',
      validator: value => ['source', 'ai'].includes(value),
    },
  },
  emits: ['select'],
  computed: {
    showRating() {
      return this.showMissingRating || Boolean(this.item.rating);
    },
    showSourceContent() {
      return this.showSource && Boolean(this.sourceContentMetadata);
    },
    sourceContentMetadata() {
      return getRequestSourceContentMetadata(this.item);
    },
    requestMethodMetadata() {
      return getRequestMethodMetadata(this.item, { sourceMode: this.sourceMode });
    },
    requestMethodLabel() {
      return this.requestMethodMetadata?.shortLabel || '';
    },
    requestMethodIcon() {
      return this.requestMethodMetadata?.icon || '';
    },
  },
  methods: {
    formatDate,
  },
};
</script>

<style scoped>
.request-card {
  border: none;
  border-radius: var(--radius-lg);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: var(--transition-base);
}

.request-card--compact {
  border-radius: var(--radius-md);
}

.request-card:hover {
  box-shadow: var(--elevation-2);
  transform: translateY(-4px);
}

.request-card-poster {
  position: relative;
  width: 100%;
  aspect-ratio: 2/3;
  overflow: hidden;
  background-color: var(--color-bg-primary);
}

.poster-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.5s ease;
}

.request-card:hover .poster-image {
  transform: scale(1.05);
}

.request-card-poster::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    var(--color-bg-overlay-light),
    transparent 30%,
    transparent 56%,
    var(--surface-overlay)
  );
  opacity: var(--alpha-80);
  pointer-events: none;
}

.poster-placeholder {
  width: 100%;
  height: 100%;
  background-color: var(--color-bg-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
  font-size: 3rem;
}

.poster-overlay {
  position: absolute;
  z-index: 1;
  display: flex;
  pointer-events: none;
}

.poster-overlay--top {
  top: var(--spacing-sm);
  right: var(--spacing-sm);
  left: var(--spacing-sm);
  justify-content: space-between;
  gap: var(--spacing-xs);
}

.poster-overlay--bottom {
  right: 0;
  bottom: 0;
  left: 0;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  padding: var(--spacing-3xl) var(--spacing-sm) var(--spacing-sm);
}

.poster-pill,
.poster-date,
.poster-origin {
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

.poster-pill {
  padding: var(--spacing-xs) var(--spacing-sm);
}

.poster-pill--media {
  background-color: var(--color-primary-alpha-20);
  border-color: var(--color-primary-alpha-20);
  color: var(--color-primary-light);
}

.poster-pill--rating {
  margin-left: auto;
  background-color: var(--color-success-alpha-20);
  border-color: var(--color-success-alpha-20);
  color: var(--color-success-light);
}

.poster-date {
  max-width: 100%;
  padding: var(--spacing-xs) var(--spacing-sm);
  overflow: hidden;
  color: var(--color-warning-light);
  text-overflow: ellipsis;
}

.poster-origin {
  padding: var(--spacing-xs) var(--spacing-sm);
  background-color: var(--color-info-alpha-20);
  border-color: var(--color-info-alpha-20);
  color: var(--color-info-light);
}

.poster-pill i,
.poster-date i,
.poster-origin i {
  flex: 0 0 auto;
  font-size: var(--font-size-xs);
}

.request-card-body {
  background-color: var(--surface-glass-light);
  backdrop-filter: blur(15px);
  padding: 1rem;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.request-card--compact .request-card-body {
  gap: var(--spacing-sm);
  padding: calc(var(--spacing-sm) + var(--spacing-xs));
}

.request-card-title {
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

.source-link {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--color-text-muted);
  padding: 0.5rem 0.75rem;
  background-color: var(--color-bg-primary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-light);
}

.source-link strong {
  color: var(--color-primary);
}

.request-card--compact .request-card-title {
  font-size: var(--font-size-sm);
  line-height: 1.25;
}

.request-card--compact .poster-overlay--top {
  top: var(--spacing-xs);
  right: var(--spacing-xs);
  left: var(--spacing-xs);
}

.request-card--compact .poster-overlay--bottom {
  padding: var(--spacing-2xl) var(--spacing-xs) var(--spacing-xs);
}

.request-card--compact .poster-pill,
.request-card--compact .poster-date,
.request-card--compact .poster-origin {
  gap: var(--spacing-2xs);
  padding: var(--spacing-2xs) var(--spacing-xs);
}

@media (max-width: 768px) {
  .request-card-title {
    font-size: 0.95rem;
  }

  .request-card--compact .request-card-title {
    font-size: var(--font-size-xs);
  }

  .source-link {
    font-size: 0.75rem;
    padding: 0.375rem 0.5rem;
  }

  .poster-overlay--top {
    top: var(--spacing-xs);
    right: var(--spacing-xs);
    left: var(--spacing-xs);
  }

  .poster-overlay--bottom {
    padding: var(--spacing-2xl) var(--spacing-xs) var(--spacing-xs);
  }
}

@media (max-width: 480px) {
  .request-card--compact .request-card-body {
    padding: var(--spacing-sm);
  }

  .request-card--compact .request-card-title {
    font-size: var(--font-size-xs);
    min-height: 1.8em;
  }
}
</style>
