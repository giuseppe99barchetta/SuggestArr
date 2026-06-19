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
    </div>

    <div class="request-card-body">
      <h3 class="request-card-title">{{ item.title }}</h3>

      <div class="badge-container">
        <span class="badge badge-media">
          <i :class="item.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
          {{ item.media_type.toUpperCase() }}
        </span>
        <span v-if="showRating" class="badge badge-rating">
          <i class="fas fa-star"></i>
          {{ item.rating || 'N/A' }}
        </span>
        <span class="badge badge-requested">
          <i class="fas fa-clock"></i>
          {{ formatDate(item.requested_at) }}
        </span>
      </div>

      <div v-if="sourceMode === 'ai' && item.rationale" class="source-link">
        <i class="fas fa-search"></i>
        <span>Search: <em>"{{ item.rationale }}"</em></span>
      </div>
      <div v-else-if="sourceMode === 'ai'" class="source-link">
        <i class="fas fa-magic"></i>
        <span>From: <strong>AI Search</strong></span>
      </div>
      <div v-else-if="showSource && item.source_title" class="source-link">
        <i class="fas fa-arrow-left"></i>
        <span>From: <strong>{{ item.source_title }}</strong></span>
      </div>
    </div>
  </div>
</template>

<script>
import { formatDate } from '@/utils/dateUtils.js';

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
  },
  methods: {
    formatDate,
  },
};
</script>

<style scoped>
.request-card {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: var(--transition-base);
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
  padding: 1rem;
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

.badge-container {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge i {
  font-size: 0.85rem;
}

.badge-media,
.badge-rating,
.badge-requested {
  background-color: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
}

.badge-media {
  color: var(--color-info);
}

.badge-rating {
  color: var(--color-success);
}

.badge-requested {
  color: var(--color-primary);
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

@media (max-width: 768px) {
  .request-card-title {
    font-size: 0.95rem;
  }

  .request-card--compact .request-card-title {
    font-size: 0.7rem;
  }

  .request-card--compact .badge {
    font-size: 0.625rem;
    padding: 0.25rem 0.5rem;
  }

  .source-link {
    font-size: 0.75rem;
    padding: 0.375rem 0.5rem;
  }
}

@media (max-width: 480px) {
  .request-card--compact .request-card-body {
    padding: 0.5rem;
  }

  .request-card--compact .request-card-title {
    font-size: 0.6875rem;
    min-height: 1.8em;
  }
}
</style>
