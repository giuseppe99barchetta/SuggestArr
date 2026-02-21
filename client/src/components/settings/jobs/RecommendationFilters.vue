<template>
  <div class="recommendation-filters">
    <!-- User Selection Mode -->
    <div class="form-group">
      <label>Monitor Users</label>
      <div class="user-mode-selector">
        <button
          type="button"
          class="mode-btn"
          :class="{ active: userMode === 'all' }"
          @click="setUserMode('all')"
        >
          <i class="fas fa-users"></i>
          All Users
        </button>
        <button
          type="button"
          class="mode-btn"
          :class="{ active: userMode === 'specific' }"
          @click="setUserMode('specific')"
        >
          <i class="fas fa-user-check"></i>
          Specific Users
        </button>
      </div>
    </div>

    <!-- User Selection (when specific mode) -->
    <div v-if="userMode === 'specific'" class="form-group">
      <label>Select Users</label>
      <div class="users-list" v-if="availableUsers.length > 0">
        <div
          v-for="user in availableUsers"
          :key="user.id"
          class="user-item"
          :class="{ selected: isUserSelected(user.id) }"
          @click="toggleUser(user.id)"
        >
          <div class="user-avatar">
            <i class="fas fa-user"></i>
          </div>
          <span class="user-name">{{ user.name || user.id }}</span>
          <i v-if="isUserSelected(user.id)" class="fas fa-check check-icon"></i>
        </div>
      </div>
      <div v-else-if="isLoading" class="loading-users">
        <i class="fas fa-spinner fa-spin"></i>
        <span>Loading users...</span>
      </div>
      <div v-else class="no-users">
        <i class="fas fa-user-slash"></i>
        <span>No users found. Configure SELECTED_USERS in settings.</span>
      </div>
    </div>

    <!-- Advanced Recommendation Settings (only shown when showAdvanced is true) -->
    <template v-if="showAdvanced">
      <!-- Recommendation-specific settings -->
      <div class="form-group">
        <label for="maxSimilarMovie">Similar Movies Per Watched: {{ localFilters.max_similar_movie || 5 }}</label>
        <input
          id="maxSimilarMovie"
          v-model.number="localFilters.max_similar_movie"
          type="range"
          min="1"
          max="10"
          step="1"
          class="form-range"
        />
        <small class="form-help">How many similar movies to find for each watched movie</small>
      </div>

      <div class="form-group">
        <label for="maxSimilarTv">Similar TV Shows Per Watched: {{ localFilters.max_similar_tv || 2 }}</label>
        <input
          id="maxSimilarTv"
          v-model.number="localFilters.max_similar_tv"
          type="range"
          min="1"
          max="10"
          step="1"
          class="form-range"
        />
        <small class="form-help">How many similar TV shows to find for each watched show</small>
      </div>

      <div class="form-group">
        <label for="maxContent">Max Content to Check: {{ localFilters.max_content || 10 }}</label>
        <input
          id="maxContent"
          v-model.number="localFilters.max_content"
          type="range"
          min="5"
          max="50"
          step="5"
          class="form-range"
        />
        <small class="form-help">Maximum recently watched items to analyze per user</small>
      </div>

      <div class="form-group">
        <label for="searchSize">Search Size: {{ localFilters.search_size || 20 }}</label>
        <input
          id="searchSize"
          v-model.number="localFilters.search_size"
          type="range"
          min="10"
          max="50"
          step="5"
          class="form-range"
        />
        <small class="form-help">Number of results to fetch per TMDb search</small>
      </div>

      <!-- Behavior Toggles -->
      <div class="form-group">
        <label>Behavior Options</label>
        <div class="toggle-options">
          <label class="toggle-item">
            <input
              v-model="localFilters.exclude_downloaded"
              type="checkbox"
            />
            <span class="toggle-label">
              <i class="fas fa-download"></i>
              Exclude Downloaded Content
            </span>
          </label>
          <small class="toggle-help">Skip content already in your library</small>

          <label class="toggle-item">
            <input
              v-model="localFilters.exclude_requested"
              type="checkbox"
            />
            <span class="toggle-label">
              <i class="fas fa-clock"></i>
              Exclude Requested Content
            </span>
          </label>
          <small class="toggle-help">Skip content already requested in Jellyseer/Overseer</small>

          <label class="toggle-item">
            <input
              v-model="localFilters.honor_jellyseer_discovery"
              type="checkbox"
            />
            <span class="toggle-label">
              <i class="fas fa-compass"></i>
              Honor Jellyseer Discovery
            </span>
          </label>
          <small class="toggle-help">Respect Jellyseer's discovery settings for requests</small>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'RecommendationFilters',
  props: {
    modelValue: {
      type: Object,
      default: () => ({})
    },
    showAdvanced: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:modelValue'],
  data() {
    return {
      availableUsers: [],
      isLoading: false,
      localFilters: {
        max_similar_movie: 5,
        max_similar_tv: 2,
        max_content: 10,
        search_size: 20,
        exclude_downloaded: true,
        exclude_requested: true,
        honor_jellyseer_discovery: false
      },
      isUpdatingFromParent: false,
      localUserMode: 'all'
    };
  },
  computed: {
    userMode() {
      return this.localUserMode;
    }
  },
  watch: {
    modelValue: {
      handler(newVal) {
        if (newVal.filters) {
          this.isUpdatingFromParent = true;
          this.localFilters = {
            max_similar_movie: newVal.filters.max_similar_movie ?? 5,
            max_similar_tv: newVal.filters.max_similar_tv ?? 2,
            max_content: newVal.filters.max_content ?? 10,
            search_size: newVal.filters.search_size ?? 20,
            exclude_downloaded: newVal.filters.exclude_downloaded ?? true,
            exclude_requested: newVal.filters.exclude_requested ?? true,
            honor_jellyseer_discovery: newVal.filters.honor_jellyseer_discovery ?? false
          };
          this.$nextTick(() => {
            this.isUpdatingFromParent = false;
          });
        }
        // Initialize user mode based on user_ids
        if (newVal.user_ids && newVal.user_ids.length > 0) {
          this.localUserMode = 'specific';
        }
      },
      deep: true,
      immediate: true
    },
    localFilters: {
      handler(newVal) {
        // Don't emit if the change came from the parent
        if (!this.isUpdatingFromParent) {
          this.updateFilters(newVal);
        }
      },
      deep: true
    }
  },
  async mounted() {
    await this.loadUsers();
  },
  methods: {
    async loadUsers() {
      this.isLoading = true;
      try {
        // Try to get users from the config
        const response = await axios.get('/api/config/fetch');
        if (response.data && response.data.SELECTED_USERS) {
          const users = response.data.SELECTED_USERS;
          this.availableUsers = users.map(u => {
            if (typeof u === 'string') {
              return { id: u, name: u };
            }
            return { id: u.id, name: u.name || u.id };
          });
        }
      } catch (error) {
        console.error('Failed to load users:', error);
      } finally {
        this.isLoading = false;
      }
    },

    setUserMode(mode) {
      this.localUserMode = mode;
      if (mode === 'all') {
        this.$emit('update:modelValue', {
          ...this.modelValue,
          user_ids: []
        });
      }
      // For 'specific', don't change user_ids - let user select
    },

    isUserSelected(userId) {
      return this.modelValue.user_ids && this.modelValue.user_ids.includes(userId);
    },

    toggleUser(userId) {
      const currentIds = this.modelValue.user_ids || [];
      let newIds;

      if (this.isUserSelected(userId)) {
        newIds = currentIds.filter(id => id !== userId);
      } else {
        newIds = [...currentIds, userId];
      }

      this.$emit('update:modelValue', {
        ...this.modelValue,
        user_ids: newIds
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
    }
  }
};
</script>

<style scoped>
.recommendation-filters {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: 0.5rem;
}

.user-mode-selector {
  display: flex;
  gap: 0.5rem;
}

.mode-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: var(--transition-base);
  font-size: 0.9rem;
}

.mode-btn:hover {
  border-color: var(--color-border-heavy);
  color: var(--color-text-primary);
}

.mode-btn.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
}

.users-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 200px;
  overflow-y: auto;
  padding: 0.5rem;
  background: var(--color-bg-overlay-light);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
}

.user-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-base);
}

.user-item:hover {
  border-color: var(--color-border-heavy);
}

.user-item.selected {
  background: var(--color-primary-alpha-10);
  border-color: var(--color-primary);
}

.user-avatar {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-overlay-light);
  border-radius: 50%;
  color: var(--color-text-muted);
}

.user-item.selected .user-avatar {
  background: var(--color-primary);
  color: white;
}

.user-name {
  flex: 1;
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.check-icon {
  color: var(--color-primary);
}

.loading-users,
.no-users {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1.5rem;
  background: var(--color-bg-overlay-light);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.form-range {
  width: 100%;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--color-border-light);
  border-radius: var(--radius-full);
  outline: none;
  margin-top: 0.5rem;
}

.form-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  background: var(--color-primary);
  border-radius: 50%;
  cursor: pointer;
  transition: var(--transition-fast);
}

.form-range::-webkit-slider-thumb:hover {
  transform: scale(1.1);
  box-shadow: var(--shadow-glow);
}

.form-range::-moz-range-thumb {
  width: 18px;
  height: 18px;
  background: var(--color-primary);
  border-radius: 50%;
  cursor: pointer;
  border: none;
}

.form-help {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  margin-top: 0.5rem;
}

.toggle-options {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem;
  background: var(--color-bg-overlay-light);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
}

.toggle-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: var(--transition-base);
}

.toggle-item:hover {
  background: var(--color-bg-interactive);
}

.toggle-item input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.toggle-label i {
  color: var(--color-text-muted);
  width: 1rem;
}

.toggle-help {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  margin-left: 2.5rem;
  margin-bottom: 0.5rem;
}
</style>
