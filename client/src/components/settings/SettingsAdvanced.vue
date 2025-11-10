<template>
  <div class="settings-advanced">
    <div class="section-header">
      <h2>Advanced Settings</h2>
      <p>Configure advanced options and experimental features</p>
    </div>

    <div class="settings-grid">
      <!-- User Selection -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-users"></i>
          User Selection
        </h3>

        <div class="form-group">
          <label for="selectedUsers">Selected Users</label>
          <div v-if="isLoadingUsers" class="loading-users">
            <i class="fas fa-spinner fa-spin"></i>
            Loading users...
          </div>
          <div v-else class="user-selector">
            <div
              v-for="user in availableUsers"
              :key="user.id"
              class="user-item"
            >
              <input
                :id="`user-${user.id}`"
                v-model="localConfig.SELECTED_USERS"
                :value="user.id"
                type="checkbox"
                class="user-checkbox"
                :disabled="isLoading"
              />
              <label :for="`user-${user.id}`" class="user-label">
                <div class="user-avatar">
                  <img v-if="user.avatar" :src="user.avatar" :alt="user.name" />
                  <i v-else class="fas fa-user"></i>
                </div>
                <div class="user-info">
                  <div class="user-name">{{ user.name }}</div>
                  <div class="user-type">{{ user.type || 'User' }}</div>
                </div>
              </label>
            </div>
          </div>
          <small class="form-help">
            Select users for whom to generate suggestions. Leave empty to include all users.
          </small>
        </div>

        <div class="form-group">
          <button
            @click="refreshUsers"
            class="btn btn-outline btn-sm"
            :disabled="isLoading || isLoadingUsers"
          >
            <i class="fas fa-sync"></i>
            Refresh Users
          </button>
        </div>
      </div>

      <!-- Experimental Features -->
      <div class="settings-group experimental">
        <h3>
          <i class="fas fa-flask"></i>
          Experimental Features
        </h3>

        <div class="warning-box">
          <i class="fas fa-exclamation-triangle"></i>
          <div>
            <strong>Warning:</strong>
            <p>
              These features are experimental and may cause unexpected behavior. Use with caution.
            </p>
          </div>
        </div>

        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="localConfig.ENABLE_BETA_FEATURES"
              type="checkbox"
              :disabled="isLoading"
            />
            <span class="checkbox-text">Enable beta features</span>
          </label>
          <small class="form-help">
            Enable experimental features that are still in development
          </small>
        </div>

        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="localConfig.ENABLE_ADVANCED_ALGORITHM"
              type="checkbox"
              :disabled="isLoading"
            />
            <span class="checkbox-text">Use advanced suggestion algorithm</span>
          </label>
          <small class="form-help">
            Use an enhanced algorithm for better content suggestions (may be slower)
          </small>
        </div>

        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="localConfig.ENABLE_SOCIAL_FEATURES"
              type="checkbox"
              :disabled="isLoading"
            />
            <span class="checkbox-text">Enable social features</span>
          </label>
          <small class="form-help">
            Enable social features like sharing and collaborative filtering
          </small>
        </div>
      </div>

      <!-- Debug Settings -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-bug"></i>
          Debug Settings
        </h3>

        <BaseDropdown
            v-model="localConfig.LOG_LEVEL"
          :options="logLevelOptions"
          label="Log Level"
          help-text="Set the verbosity of application logs"
            :disabled="isLoading"
          id="logLevel"
        />

        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="localConfig.ENABLE_DEBUG_MODE"
              type="checkbox"
              :disabled="isLoading"
            />
            <span class="checkbox-text">Enable debug mode</span>
          </label>
          <small class="form-help">
            Enable detailed logging and debugging information
          </small>
        </div>

        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="localConfig.ENABLE_PERFORMANCE_MONITORING"
              type="checkbox"
              :disabled="isLoading"
            />
            <span class="checkbox-text">Enable performance monitoring</span>
          </label>
          <small class="form-help">
            Track performance metrics for optimization
          </small>
        </div>
      </div>

      <!-- Cache Settings -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-memory"></i>
          Cache Settings
        </h3>

        <div class="form-group">
          <label for="cacheTtl">Cache TTL (hours)</label>
          <input
            id="cacheTtl"
            v-model.number="localConfig.CACHE_TTL"
            type="number"
            min="1"
            max="168"
            placeholder="24"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">
            How long to cache API responses and data (1-168 hours)
          </small>
        </div>

        <div class="form-group">
          <label for="maxCacheSize">Max Cache Size (MB)</label>
          <input
            id="maxCacheSize"
            v-model.number="localConfig.MAX_CACHE_SIZE"
            type="number"
            min="10"
            max="1024"
            placeholder="100"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">
            Maximum cache size in megabytes (10-1024 MB)
          </small>
        </div>

        <div class="form-group">
          <button
            @click="clearCache"
            class="btn btn-outline btn-sm"
            :disabled="isLoading"
          >
            <i class="fas fa-trash"></i>
            Clear Cache
          </button>
          <small class="form-help">
            Clear all cached data and force fresh API calls
          </small>
        </div>
      </div>

      <!-- API Settings -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-code"></i>
          API Settings
        </h3>

        <div class="form-group">
          <label for="apiTimeout">API Timeout (seconds)</label>
          <input
            id="apiTimeout"
            v-model.number="localConfig.API_TIMEOUT"
            type="number"
            min="5"
            max="120"
            placeholder="30"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">
            Timeout for external API calls (5-120 seconds)
          </small>
        </div>

        <div class="form-group">
          <label for="apiRetries">API Retry Attempts</label>
          <input
            id="apiRetries"
            v-model.number="localConfig.API_RETRIES"
            type="number"
            min="0"
            max="5"
            placeholder="3"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">
            Number of retry attempts for failed API calls (0-5)
          </small>
        </div>

        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="localConfig.ENABLE_API_CACHING"
              type="checkbox"
              :disabled="isLoading"
            />
            <span class="checkbox-text">Enable API response caching</span>
          </label>
          <small class="form-help">
            Cache API responses to reduce external service load
          </small>
        </div>
      </div>
    </div>

    <!-- Save Button -->
    <div class="settings-actions">
      <button
        @click="saveSettings"
        class="btn btn-primary"
        :disabled="isLoading || !hasChanges"
      >
        <i class="fas fa-save"></i>
        {{ isLoading ? 'Saving...' : 'Save Changes' }}
      </button>

      <button
        @click="resetToDefaults"
        class="btn btn-outline"
        :disabled="isLoading"
      >
        <i class="fas fa-undo"></i>
        Reset to Defaults
      </button>
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import BaseDropdown from '@/components/common/BaseDropdown.vue';

export default {
  name: 'SettingsAdvanced',
  components: {
    BaseDropdown
  },
  props: {
    config: {
      type: Object,
      required: true,
    },
    isLoading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['save-section'],
  data() {
    return {
      localConfig: {},
      originalConfig: {},
      availableUsers: [],
      isLoadingUsers: false,
      logLevelOptions: [
        { value: 'ERROR', label: 'Error' },
        { value: 'WARNING', label: 'Warning' },
        { value: 'INFO', label: 'Info' },
        { value: 'DEBUG', label: 'Debug' }
      ]
    };
  },
  computed: {
    hasChanges() {
      return JSON.stringify(this.localConfig) !== JSON.stringify(this.originalConfig);
    },
  },
  watch: {
    config: {
      immediate: true,
      handler(newConfig) {
        this.localConfig = { ...newConfig };
        this.originalConfig = { ...newConfig };

        // Ensure arrays are properly initialized
        if (!Array.isArray(this.localConfig.SELECTED_USERS)) {
          this.localConfig.SELECTED_USERS = [];
        }

        // Set default values for new advanced settings
        const advancedDefaults = {
          LOG_LEVEL: 'INFO',
          ENABLE_DEBUG_MODE: false,
          ENABLE_PERFORMANCE_MONITORING: false,
          CACHE_TTL: 24,
          MAX_CACHE_SIZE: 100,
          API_TIMEOUT: 30,
          API_RETRIES: 3,
          ENABLE_API_CACHING: true,
          ENABLE_BETA_FEATURES: false,
          ENABLE_ADVANCED_ALGORITHM: false,
          ENABLE_SOCIAL_FEATURES: false,
        };

        Object.keys(advancedDefaults).forEach(key => {
          if (this.localConfig[key] === undefined) {
            this.localConfig[key] = advancedDefaults[key];
          }
        });
      },
    },
  },
  mounted() {
    this.loadUsers();
  },
  methods: {
    async loadUsers() {
      this.isLoadingUsers = true;
      try {
        const service = this.localConfig.SELECTED_SERVICE;
        if (!service) {
          this.availableUsers = [];
          return;
        }

        let endpoint;
        if (service === 'plex') {
          endpoint = '/api/plex/users';
        } else if (service === 'jellyfin') {
          endpoint = '/api/jellyfin/users';
        } else if (service === 'seer') {
          endpoint = '/api/seer/users';
        }

        if (endpoint) {
          let url = endpoint;
          let params = {};

          // Add required parameters for Plex
          if (service === 'plex') {
            params.PLEX_TOKEN = this.localConfig.PLEX_TOKEN;
            if (this.localConfig.PLEX_API_URL) {
              params.PLEX_API_URL = this.localConfig.PLEX_API_URL;
            }
          }

          const response = await axios.get(url, { params });
          this.availableUsers = response.data.users || response.data || [];
        }
      } catch (error) {
        console.error('Error loading users:', error);
        this.availableUsers = [];
      } finally {
        this.isLoadingUsers = false;
      }
    },

    async refreshUsers() {
      await this.loadUsers();
    },

    async clearCache() {
      if (confirm('Are you sure you want to clear all cached data? This may temporarily slow down the application.')) {
        try {
          await axios.post('/api/cache/clear');
          this.$toast.success('Cache cleared successfully!');
        } catch (error) {
          this.$toast.error('Failed to clear cache');
          console.error('Error clearing cache:', error);
        }
      }
    },

    async saveSettings() {
      try {
        await this.$emit('save-section', {
          section: 'advanced',
          data: {
            SELECTED_USERS: this.localConfig.SELECTED_USERS || [],
            LOG_LEVEL: this.localConfig.LOG_LEVEL || 'INFO',
            ENABLE_DEBUG_MODE: this.localConfig.ENABLE_DEBUG_MODE || false,
            ENABLE_PERFORMANCE_MONITORING: this.localConfig.ENABLE_PERFORMANCE_MONITORING || false,
            CACHE_TTL: this.localConfig.CACHE_TTL || 24,
            MAX_CACHE_SIZE: this.localConfig.MAX_CACHE_SIZE || 100,
            API_TIMEOUT: this.localConfig.API_TIMEOUT || 30,
            API_RETRIES: this.localConfig.API_RETRIES || 3,
            ENABLE_API_CACHING: this.localConfig.ENABLE_API_CACHING !== false,
            ENABLE_BETA_FEATURES: this.localConfig.ENABLE_BETA_FEATURES || false,
            ENABLE_ADVANCED_ALGORITHM: this.localConfig.ENABLE_ADVANCED_ALGORITHM || false,
            ENABLE_SOCIAL_FEATURES: this.localConfig.ENABLE_SOCIAL_FEATURES || false,
          },
        });

        this.originalConfig = { ...this.localConfig };
      } catch (error) {
        console.error('Error saving advanced settings:', error);
      }
    },

    async resetToDefaults() {
      const defaults = {
        SELECTED_USERS: [],
        LOG_LEVEL: 'INFO',
        ENABLE_DEBUG_MODE: false,
        ENABLE_PERFORMANCE_MONITORING: false,
        CACHE_TTL: 24,
        MAX_CACHE_SIZE: 100,
        API_TIMEOUT: 30,
        API_RETRIES: 3,
        ENABLE_API_CACHING: true,
        ENABLE_BETA_FEATURES: false,
        ENABLE_ADVANCED_ALGORITHM: false,
        ENABLE_SOCIAL_FEATURES: false,
      };

      if (confirm('Are you sure you want to reset all advanced settings to their defaults?')) {
        this.localConfig = { ...this.localConfig, ...defaults };
        await this.saveSettings();
      }
    },
  },
};
</script>

<style scoped>
.settings-advanced {
  color: #fff;
}

.section-header {
  margin-bottom: 2rem;
}

.section-header h2 {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
  color: #fff;
}

.section-header p {
  color: #9ca3af;
  font-size: 1rem;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 2rem;
  margin-bottom: 2rem;
}

.settings-group {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 0.75rem;
  padding: 1.5rem;
}

.settings-group.experimental {
  border-color: #f59e0b;
  background: rgba(245, 158, 11, 0.05);
}

.settings-group h3 {
  font-size: 1.2rem;
  margin-bottom: 1rem;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #e5e7eb;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
  margin-bottom: 0.5rem;
}

.checkbox-label input[type="checkbox"] {
  width: 1.25rem;
  height: 1.25rem;
  accent-color: #3b82f6;
}

.checkbox-text {
  color: #e5e7eb;
  font-weight: 500;
}

.form-control {
  width: 100%;
  padding: 0.75rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 0.5rem;
  color: #fff;
  font-size: 1rem;
  transition: all 0.3s ease;
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  background: rgba(255, 255, 255, 0.15);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: #9ca3af;
  line-height: 1.4;
}

.warning-box {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 0.5rem;
  padding: 1rem;
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.warning-box i {
  color: #f59e0b;
  margin-top: 0.25rem;
  flex-shrink: 0;
}

.warning-box strong {
  color: #f59e0b;
  display: block;
  margin-bottom: 0.5rem;
}

.warning-box p {
  color: #e5e7eb;
  margin: 0;
  line-height: 1.5;
}

.loading-users {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #9ca3af;
  padding: 1rem;
  text-align: center;
}

.user-selector {
  max-height: 300px;
  overflow-y: auto;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 0.5rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.user-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  border-radius: 0.25rem;
  transition: background-color 0.2s ease;
}

.user-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.user-checkbox {
  width: 1rem;
  height: 1rem;
  accent-color: #3b82f6;
}

.user-label {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
  flex: 1;
  margin: 0;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.user-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar i {
  color: #9ca3af;
  font-size: 0.875rem;
}

.user-info {
  flex: 1;
}

.user-name {
  color: #e5e7eb;
  font-weight: 500;
  font-size: 0.875rem;
}

.user-type {
  color: #9ca3af;
  font-size: 0.75rem;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  border: none;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  font-size: 0.875rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-outline {
  background: transparent;
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.btn-outline:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.5);
}

.btn-sm {
  padding: 0.375rem 0.75rem;
  font-size: 0.8125rem;
}

.settings-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  padding-top: 2rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

@media (max-width: 768px) {
  .settings-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .settings-group {
    padding: 1rem;
  }

  .warning-box {
    flex-direction: column;
    text-align: center;
  }

  .user-selector {
    max-height: 250px;
  }

  .settings-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>