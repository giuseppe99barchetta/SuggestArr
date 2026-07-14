<template>
  <div class="trakt-recommendation-filters">
    <div class="form-group">
      <label id="trakt-user-label">Trakt Account</label>
      <p class="form-help">
        Choose the media user whose linked Trakt recommendations this job should fetch.
      </p>

      <div v-if="isLoading" class="loading-users">
        <i class="fas fa-spinner fa-spin"></i>
        <span>Loading Trakt users...</span>
      </div>

      <div v-else-if="!traktConfigured" class="no-users">
        <i class="fas fa-link-slash"></i>
        <span>Configure Trakt app credentials in Services first.</span>
      </div>

      <div v-else-if="connectedUsers.length === 0" class="no-users">
        <i class="fas fa-user-slash"></i>
        <span>No media users have a linked Trakt account yet.</span>
      </div>

      <div
        v-else
        class="users-list"
        role="radiogroup"
        aria-labelledby="trakt-user-label"
      >
        <button
          v-for="user in connectedUsers"
          :key="user.external_user_id"
          type="button"
          class="user-item"
          :class="{ selected: selectedUserId === user.external_user_id }"
          role="radio"
          :aria-checked="selectedUserId === user.external_user_id"
          @click="selectUser(user.external_user_id)"
        >
          <div class="user-avatar">
            <i class="fas fa-user"></i>
          </div>
          <div class="user-meta">
            <span class="user-name">{{ user.external_username || user.external_user_id }}</span>
            <span class="user-sub">Trakt connected</span>
          </div>
          <i v-if="selectedUserId === user.external_user_id" class="fas fa-check check-icon"></i>
        </button>
      </div>
    </div>

    <div class="form-group">
      <label>Request Behavior</label>
      <div class="toggle-options">
        <div class="toggle-item">
          <BaseCheckbox v-model="localFilters.exclude_downloaded">
            <span class="toggle-label-modal">
              <i class="fas fa-download"></i>
              Exclude downloaded content
            </span>
          </BaseCheckbox>
        </div>
        <small class="toggle-help">Skip titles already in your library</small>

        <div class="toggle-item">
          <BaseCheckbox v-model="localFilters.exclude_requested">
            <span class="toggle-label-modal">
              <i class="fas fa-clock"></i>
              Exclude requested content
            </span>
          </BaseCheckbox>
        </div>
        <small class="toggle-help">Skip titles already requested in Seer</small>
      </div>
    </div>

    <div v-if="showAdvanced" class="form-group">
      <label for="maxTraktResults">Total Request Limit: {{ maxResults }}</label>
      <input
        id="maxTraktResults"
        :value="maxResults"
        type="range"
        min="5"
        max="100"
        step="5"
        class="form-range"
        @input="updateMaxResults"
      />
      <small class="form-help">Maximum Trakt recommendations to request per run</small>
    </div>
  </div>
</template>

<script>
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';

export default {
  name: 'TraktRecommendationFilters',
  components: { BaseCheckbox },
  props: {
    modelValue: {
      type: Object,
      default: () => ({})
    },
    showAdvanced: {
      type: Boolean,
      default: false
    },
    traktConfigured: {
      type: Boolean,
      default: false
    },
    connectedUsers: {
      type: Array,
      default: () => []
    },
    isLoading: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:modelValue'],
  data() {
    return {
      isUpdatingFromParent: false,
      localFilters: {
        exclude_downloaded: true,
        exclude_requested: true
      }
    };
  },
  computed: {
    selectedUserId() {
      const ids = this.modelValue.user_ids || [];
      return ids.length ? ids[0] : '';
    },
    maxResults() {
      return this.modelValue.max_results || 20;
    }
  },
  watch: {
    modelValue: {
      handler(newVal) {
        this.isUpdatingFromParent = true;
        this.localFilters = {
          exclude_downloaded: newVal.filters?.exclude_downloaded ?? true,
          exclude_requested: newVal.filters?.exclude_requested ?? true
        };
        this.$nextTick(() => {
          this.isUpdatingFromParent = false;
        });
      },
      deep: true,
      immediate: true
    },
    localFilters: {
      handler(newVal) {
        if (!this.isUpdatingFromParent) {
          this.updateFilters(newVal);
        }
      },
      deep: true
    },
    connectedUsers: {
      handler(users) {
        if (!this.selectedUserId && users.length === 1) {
          this.selectUser(users[0].external_user_id);
        }
      },
      immediate: true
    }
  },
  mounted() {
    if (
      this.modelValue.filters?.exclude_downloaded === undefined
      || this.modelValue.filters?.exclude_requested === undefined
    ) {
      this.updateFilters(this.localFilters);
    }
  },
  methods: {
    selectUser(externalUserId) {
      this.$emit('update:modelValue', {
        ...this.modelValue,
        user_ids: [externalUserId]
      });
    },
    updateFilters(filters) {
      this.$emit('update:modelValue', {
        ...this.modelValue,
        filters: {
          ...this.modelValue.filters,
          ...filters
        }
      });
    },
    updateMaxResults(event) {
      this.$emit('update:modelValue', {
        ...this.modelValue,
        max_results: Number(event.target.value)
      });
    }
  }
};
</script>

<style scoped>
.trakt-recommendation-filters {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.trakt-recommendation-filters .form-help {
  display: block;
  margin-bottom: 0.75rem;
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.users-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.user-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: var(--transition-base);
}

.user-item:hover {
  background: var(--color-bg-overlay-light);
}

.user-item:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.user-item.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-alpha-10);
}

.user-avatar {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-interactive);
  color: var(--color-text-muted);
}

.user-meta {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  flex: 1;
}

.user-name {
  font-size: 0.85rem;
  color: var(--color-text-primary);
}

.user-sub {
  font-size: 0.7rem;
  color: var(--color-text-muted);
}

.check-icon {
  color: var(--color-primary);
}

.no-users,
.loading-users {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  border: 1px dashed var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.toggle-options {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.toggle-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.toggle-label-modal {
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.toggle-help {
  display: block;
  margin: 0 0 0.5rem 1.75rem;
  font-size: 0.75rem;
  color: var(--color-text-muted);
}
</style>
