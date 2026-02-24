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
          <div v-else class="user-grid">
            <div
              v-for="user in availableUsers"
              :key="user.id"
              :class="['user-card', { 'selected': isUserSelected(user.id) }]"
              @click="toggleUserSelection(user.id)"
            >
              <div class="user-avatar">
                <img v-if="user.avatar" :src="user.avatar" :alt="user.name" />
                <i v-else class="fas fa-user"></i>
              </div>
              <div class="user-info">
                <div class="user-name">{{ user.name }}</div>
                <div class="user-type">{{ user.type || 'User' }}</div>
              </div>
              <div class="user-selection-indicator">
                <i class="fas fa-check"></i>
              </div>
            </div>
            <div v-if="availableUsers.length === 0" class="no-users">
              <i class="fas fa-users-slash"></i>
              <p>No users available</p>
              <small>Please configure your media service first</small>
            </div>
          </div>
          <small class="form-help">
            Click on users to select/deselect them for suggestion generation. Leave empty to include all users.
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
      
        <div class="form-group feature-wrapper" :class="{ 'feature-disabled': !localConfig.ENABLE_BETA_FEATURES }">
          <label class="checkbox-label">
            <input
              v-model="localConfig.ENABLE_ADVANCED_ALGORITHM"
              type="checkbox"
              :disabled="isLoading || !localConfig.ENABLE_BETA_FEATURES"
            />
            <span class="checkbox-text">Use advanced suggestion algorithm</span>
          </label>
          <small class="form-help">
            Use an AI-powered algorithm for hyper-personalized content suggestions based on watch history.
          </small>
        </div>

      </div>

      <!-- AI Provider Configuration (visible only when advanced algorithm is enabled) -->
      <transition name="ai-card">
        <div
          v-if="localConfig.ENABLE_ADVANCED_ALGORITHM && localConfig.ENABLE_BETA_FEATURES"
          class="settings-group ai-group"
        >
          <h3>
            <i class="fas fa-robot"></i>
            AI Provider Configuration
            <button class="info-btn" @click="showAiInfoModal = true" title="Learn how to configure AI providers">
              <i class="fas fa-circle-info"></i>
            </button>
          </h3>

          <div class="form-group">
            <label for="openaiApiKey">
              API Key
              <span class="optional-tag">Optional</span>
            </label>
            <input
              id="openaiApiKey"
              v-model="localConfig.OPENAI_API_KEY"
              type="password"
              placeholder="sk-..."
              class="form-control"
              :disabled="isLoading"
            />
            <small class="form-help">
              Required for OpenAI and hosted providers. Not needed for local LLMs like Ollama (leave blank or enter any value).
            </small>
          </div>

          <div class="form-group">
            <label for="llmModel">Model</label>
            <input
              id="llmModel"
              v-model="localConfig.LLM_MODEL"
              type="text"
              placeholder="gpt-4o-mini"
              class="form-control"
              :disabled="isLoading"
            />
            <small class="form-help">
              The model name to use. For Ollama, use the name of the locally installed model (e.g. <code>mistral</code>, <code>llama3</code>).
            </small>
          </div>

          <div class="form-group">
            <label for="openaiBaseUrl">
              Base URL
              <span class="optional-tag">Optional</span>
            </label>
            <input
              id="openaiBaseUrl"
              v-model="localConfig.OPENAI_BASE_URL"
              type="text"
              placeholder="https://api.openai.com/v1"
              class="form-control"
              :disabled="isLoading"
            />
            <small class="form-help">
              Leave blank for OpenAI. Set to <code>http://localhost:11434/v1</code> for Ollama, or your OpenRouter / LiteLLM endpoint.
            </small>
          </div>

          <div class="form-group">
            <button
              @click="testLlmConnection"
              class="btn btn-outline btn-sm"
              :disabled="isLoading || isTestingLlm"
            >
              <i :class="isTestingLlm ? 'fas fa-spinner fa-spin' : 'fas fa-plug'"></i>
              {{ isTestingLlm ? 'Testing...' : 'Test Connection' }}
            </button>
          </div>
        </div>
      </transition>

      <!-- AI Info Modal -->
      <teleport to="body">
        <transition name="modal-fade">
          <div v-if="showAiInfoModal" class="modal-overlay" @click.self="showAiInfoModal = false">
            <div class="modal-box">
              <div class="modal-header">
                <h3><i class="fas fa-robot"></i> AI Provider Setup Guide</h3>
                <button class="modal-close" @click="showAiInfoModal = false">
                  <i class="fas fa-times"></i>
                </button>
              </div>
              <div class="modal-body">
                <p class="modal-intro">
                  SuggestArr uses any <strong>OpenAI-compatible API</strong> to generate personalized recommendations based on your watch history. You can use a cloud provider or a local LLM running on your machine.
                </p>

                <div class="provider-list">
                  <div class="provider-card">
                    <div class="provider-name"><i class="fas fa-cloud"></i> OpenAI</div>
                    <table class="provider-table">
                      <tbody>
                        <tr><td>API Key</td><td><code>sk-proj-...</code> (required)</td></tr>
                        <tr><td>Base URL</td><td><em>leave blank</em></td></tr>
                        <tr><td>Model</td><td><code>gpt-4o-mini</code></td></tr>
                      </tbody>
                    </table>
                  </div>

                  <div class="provider-card">
                    <div class="provider-name"><i class="fas fa-gem"></i> Google Gemini</div>
                    <table class="provider-table">
                      <tbody>
                        <tr><td>API Key</td><td><code>AIza...</code> (from Google AI Studio)</td></tr>
                        <tr><td>Base URL</td><td><code>https://generativelanguage.googleapis.com/v1beta/openai/</code></td></tr>
                        <tr><td>Model</td><td><code>gemini-2.0-flash</code>, <code>gemini-1.5-pro</code>, etc.</td></tr>
                      </tbody>
                    </table>
                    <small class="provider-note">Get your free API key at <a href="https://aistudio.google.com/" target="_blank" rel="noopener">aistudio.google.com</a>. The Base URL must end with <code>/openai/</code>.</small>
                  </div>

                  <div class="provider-card provider-card--local">
                    <div class="provider-name"><i class="fas fa-server"></i> Ollama <span class="badge-local">Local</span></div>
                    <table class="provider-table">
                      <tbody>
                        <tr><td>API Key</td><td><em>not required</em></td></tr>
                        <tr><td>Base URL</td><td><code>http://localhost:11434/v1</code></td></tr>
                        <tr><td>Model</td><td><code>mistral</code>, <code>llama3</code>, etc.</td></tr>
                      </tbody>
                    </table>
                    <small class="provider-note">Make sure Ollama is running and the model is pulled before saving.</small>
                  </div>

                  <div class="provider-card">
                    <div class="provider-name"><i class="fas fa-network-wired"></i> OpenRouter</div>
                    <table class="provider-table">
                      <tbody>
                        <tr><td>API Key</td><td><code>sk-or-v1-...</code> (required)</td></tr>
                        <tr><td>Base URL</td><td><code>https://openrouter.ai/api/v1</code></td></tr>
                        <tr><td>Model</td><td><code>meta-llama/llama-3-8b-instruct</code></td></tr>
                      </tbody>
                    </table>
                  </div>

                  <div class="provider-card">
                    <div class="provider-name"><i class="fas fa-exchange-alt"></i> LiteLLM Proxy</div>
                    <table class="provider-table">
                      <tbody>
                        <tr><td>API Key</td><td>depends on your proxy config</td></tr>
                        <tr><td>Base URL</td><td><code>http://&lt;your-proxy&gt;:4000</code></td></tr>
                        <tr><td>Model</td><td>depends on your proxy config</td></tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div class="modal-tip">
                  <i class="fas fa-lightbulb"></i>
                  <span>The system sends your watch history to the LLM and receives a ranked list of recommendations with reasoning. No personal data is stored by the provider beyond your API usage.</span>
                </div>
              </div>
            </div>
          </div>
        </transition>
      </teleport>

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

        <div class="form-group">
          <label class="checkbox-label">
            <input
              :checked="!localConfig.ENABLE_VISUAL_EFFECTS"
              @change="localConfig.ENABLE_VISUAL_EFFECTS = !$event.target.checked"
              type="checkbox"
              :disabled="isLoading"
            />
            <span class="checkbox-text">Disable visual effects (blur)</span>
          </label>
          <small class="form-help">
            Check this box to improve UI performance and frame rates by turning off heavy CSS background blurs.
          </small>
        </div>

        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="localConfig.ENABLE_STATIC_BACKGROUND"
              type="checkbox"
              :disabled="isLoading"
            />
            <span class="checkbox-text">Enable static colored background</span>
          </label>
          <small class="form-help">
            Override the app's default rotating background pictures with a static color.
          </small>
        </div>

        <div class="form-group" v-if="localConfig.ENABLE_STATIC_BACKGROUND">
          <label for="staticBackgroundColor">Static Background Color (Hex)</label>
          <div style="display: flex; gap: 10px; align-items: center; margin-top: 0.5rem;">
            <input
              id="staticBackgroundColor"
              v-model="localConfig.STATIC_BACKGROUND_COLOR"
              type="color"
              class="form-control"
              style="width: 50px; padding: 0.2rem; height: 38px; cursor: pointer;"
              :disabled="isLoading"
            />
            <input
              v-model="localConfig.STATIC_BACKGROUND_COLOR"
              type="text"
              placeholder="#2E3440"
              class="form-control"
              pattern="^#[0-9A-Fa-f]{6}$"
              title="Must be a valid hex color code (e.g. #FF0000)"
              :disabled="isLoading"
            />
          </div>
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

      <div class="settings-group">
        <h3>
          <i class="fas fa-gear"></i>
          Application
        </h3>

        <div class="form-group">
          <label for="subpath">Subpath</label>
          <input id="subpath" v-model="localConfig.SUBPATH" type="text" placeholder="/suggestarr" class="form-control"
            :disabled="isLoading" />
          <small class="form-help">
            Subpath for running SuggestArr under a subdirectory (e.g., "/suggestarr"). Leave empty for root.
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
      showAiInfoModal: false,
      isTestingLlm: false,
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
          OPENAI_API_KEY: '',
          OPENAI_BASE_URL: '',
          LLM_MODEL: 'gpt-4o-mini',
          ENABLE_SOCIAL_FEATURES: false,
          ENABLE_VISUAL_EFFECTS: true,
          ENABLE_STATIC_BACKGROUND: false,
          STATIC_BACKGROUND_COLOR: '#2E3440',
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
    isUserSelected(userId) {
      if (!Array.isArray(this.localConfig.SELECTED_USERS)) {
        return false;
      }
      // Handle both formats: array of objects or array of IDs (legacy)
      return this.localConfig.SELECTED_USERS.some(user => {
        if (typeof user === 'string') {
          return user === userId;
        } else if (typeof user === 'object' && user.id) {
          return user.id === userId;
        }
        return false;
      });
    },

    toggleUserSelection(userId) {
      if (!Array.isArray(this.localConfig.SELECTED_USERS)) {
        this.localConfig.SELECTED_USERS = [];
      }

      // Normalize to array of objects format
      const normalized = this.localConfig.SELECTED_USERS.map(user => {
        if (typeof user === 'string') {
          // Convert legacy format to new format
          const fullUser = this.availableUsers.find(u => u.id === user);
          return fullUser ? { id: fullUser.id, name: fullUser.name } : { id: user, name: user };
        } else if (typeof user === 'object' && user.id) {
          return { id: user.id, name: user.name };
        }
        return null;
      }).filter(u => u !== null);

      // Find index by comparing IDs
      const index = normalized.findIndex(u => u.id === userId);

      if (index > -1) {
        // Remove user from selection
        normalized.splice(index, 1);
      } else {
        // Add user to selection - find full user object
        const userToAdd = this.availableUsers.find(u => u.id === userId);
        if (userToAdd) {
          normalized.push({ id: userToAdd.id, name: userToAdd.name });
        } else {
          // Fallback if user not found in availableUsers
          normalized.push({ id: userId, name: userId });
        }
      }

      this.localConfig.SELECTED_USERS = normalized;
    },

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
            OPENAI_API_KEY: this.localConfig.OPENAI_API_KEY || '',
            OPENAI_BASE_URL: this.localConfig.OPENAI_BASE_URL || '',
            LLM_MODEL: this.localConfig.LLM_MODEL || 'gpt-4o-mini',
            ENABLE_SOCIAL_FEATURES: this.localConfig.ENABLE_SOCIAL_FEATURES || false,
            ENABLE_VISUAL_EFFECTS: this.localConfig.ENABLE_VISUAL_EFFECTS !== false,
            ENABLE_STATIC_BACKGROUND: this.localConfig.ENABLE_STATIC_BACKGROUND || false,
            STATIC_BACKGROUND_COLOR: this.localConfig.STATIC_BACKGROUND_COLOR || '#2E3440',
            SUBPATH: this.localConfig.SUBPATH || null,
          },
        });

        this.originalConfig = { ...this.localConfig };
      } catch (error) {
        console.error('Error saving advanced settings:', error);
      }
    },

    async testLlmConnection() {
      this.isTestingLlm = true;
      try {
        const response = await axios.post('/api/jobs/llm-test', {
          OPENAI_API_KEY: this.localConfig.OPENAI_API_KEY || '',
          OPENAI_BASE_URL: this.localConfig.OPENAI_BASE_URL || '',
          LLM_MODEL: this.localConfig.LLM_MODEL || 'gpt-4o-mini',
        });
        if (response.data.status === 'success') {
          this.$toast.success('AI connection successful!');
        } else {
          this.$toast.error(response.data.message || 'Connection failed');
        }
      } catch (error) {
        const msg = error.response?.data?.message || 'Connection failed';
        this.$toast.error(msg);
      } finally {
        this.isTestingLlm = false;
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
        OPENAI_API_KEY: '',
        OPENAI_BASE_URL: '',
        LLM_MODEL: 'gpt-4o-mini',
        ENABLE_SOCIAL_FEATURES: false,
        ENABLE_VISUAL_EFFECTS: true,
        ENABLE_STATIC_BACKGROUND: false,
        STATIC_BACKGROUND_COLOR: '#2E3440',
        SUBPATH: null,
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
  color: var(--color-text-primary);
}

.section-header {
  margin-bottom: 2rem;
}

.section-header h2 {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
  color: var(--color-text-primary);
}

.section-header p {
  color: var(--color-text-muted);
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
  border-radius: var(--border-radius-md);
  padding: 1.5rem;
}

.settings-group.experimental {
  border-color: var(--color-warning);
  background: rgba(245, 158, 11, 0.05);
}

.settings-group h3 {
  font-size: 1.2rem;
  margin-bottom: 1rem;
  color: var(--color-text-primary);
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
  margin-top: 0.5rem;
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
  vertical-align: middle;
  width: 1.25rem;
  height: 1.25rem;
  accent-color: var(--color-primary);
}

.checkbox-text {
  vertical-align: middle;
  margin-left: 0.5rem;
  color: #e5e7eb;
  font-weight: 500;
}

.form-control {
  width: 100%;
  padding: 0.75rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-primary);
  font-size: 1rem;
  transition: var(--transition-base);
}

.form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  background: var(--color-bg-active);
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
  color: var(--color-text-muted);
  line-height: 1.4;
}

.warning-box {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: var(--border-radius-sm);
  padding: 1rem;
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.warning-box i {
  color: var(--color-warning);
  margin-top: 0.25rem;
  flex-shrink: 0;
}

.warning-box strong {
  color: var(--color-warning);
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
  color: var(--color-text-muted);
  padding: 1rem;
  text-align: center;
}

.user-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 1rem;
  padding: 0.5rem;
  max-height: 400px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--border-radius-sm);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.user-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 1.25rem 1rem;
  background: rgba(255, 255, 255, 0.05);
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--border-radius-md);
  cursor: pointer;
  transition: var(--transition-base);
  position: relative;
  overflow: hidden;
}

.user-card:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: var(--color-border-light);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.user-card.selected {
  background: rgba(59, 130, 246, 0.2);
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.user-card.selected .user-avatar {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.user-card.selected .user-name {
  color: #60a5fa;
}

.user-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--color-bg-interactive);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid transparent;
  transition: var(--transition-base);
}

.user-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar i {
  color: var(--color-text-muted);
  font-size: 1.25rem;
}

.user-info {
  text-align: center;
  flex: 1;
  width: 100%;
}

.user-name {
  color: #e5e7eb;
  font-weight: 500;
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
  word-wrap: break-word;
  white-space: normal;
  line-height: 1.2;
  transition: color 0.3s ease;
}

.user-type {
  color: var(--color-text-muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  font-weight: 500;
}

.user-selection-indicator {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  width: 24px;
  height: 24px;
  background: var(--color-primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transform: scale(0.8);
  transition: var(--transition-base);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
}

.user-card.selected .user-selection-indicator {
  opacity: 1;
  transform: scale(1);
}

.user-selection-indicator i {
  color: white;
  font-size: 0.75rem;
}

.no-users {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  color: var(--color-text-muted);
  text-align: center;
}

.no-users i {
  font-size: 2rem;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.no-users p {
  margin: 0 0 0.5rem 0;
  font-weight: 500;
  color: #e5e7eb;
}

.no-users small {
  font-size: 0.875rem;
  opacity: 0.8;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: var(--border-radius-sm);
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition-base);
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
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.btn-outline {
  background: var(--color-bg-interactive);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-medium);
}

/* Disabled feature styling with blur effect */
.feature-disabled {
  opacity: 0.5;
  filter: blur(0.8px);
  pointer-events: none;
  transition: all 0.3s ease;
}

.feature-disabled .checkbox-label {
  cursor: not-allowed;
}

.feature-disabled input[type="checkbox"] {
  opacity: 0.4;
}

.feature-disabled .checkbox-text,
.feature-disabled .form-help {
  color: var(--color-text-muted);
}

/* Feature wrapper for positioning */
.feature-wrapper {
  position: relative;
}

.btn-outline:hover:not(:disabled) {
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

/* AI Provider card */
.settings-group.ai-group {
  border-color: rgba(99, 102, 241, 0.45);
  background: rgba(99, 102, 241, 0.07);
}

.settings-group.ai-group h3 {
  color: #a5b4fc;
}

.settings-group.ai-group h3 i {
  color: #818cf8;
}

.optional-tag {
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--color-text-muted);
  background: rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 0.1rem 0.45rem;
  margin-left: 0.4rem;
  vertical-align: middle;
}

/* Transition for the AI card appearing in the grid */
.ai-card-enter-active,
.ai-card-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.ai-card-enter-from,
.ai-card-leave-to {
  opacity: 0;
  transform: scale(0.97) translateY(-8px);
}

.ai-card-enter-to,
.ai-card-leave-from {
  opacity: 1;
  transform: scale(1) translateY(0);
}

/* Info button next to AI section title */
.info-btn {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  color: #818cf8;
  font-size: 1rem;
  padding: 0.2rem 0.4rem;
  border-radius: 50%;
  transition: color 0.2s, background 0.2s;
  line-height: 1;
}

.info-btn:hover {
  color: #a5b4fc;
  background: rgba(165, 180, 252, 0.12);
}

/* Modal overlay */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 1rem;
}

.modal-box {
  background: #1e1e2e;
  border: 1px solid rgba(165, 180, 252, 0.3);
  border-radius: var(--border-radius-md);
  width: 100%;
  max-width: 620px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6);
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #a5b4fc;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.modal-close {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-muted);
  font-size: 1rem;
  padding: 0.35rem 0.5rem;
  border-radius: var(--border-radius-sm);
  transition: color 0.2s, background 0.2s;
}

.modal-close:hover {
  color: #e5e7eb;
  background: rgba(255, 255, 255, 0.08);
}

.modal-body {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.modal-intro {
  color: #e5e7eb;
  line-height: 1.6;
  margin: 0;
  font-size: 0.95rem;
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.provider-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--border-radius-sm);
  padding: 0.9rem 1rem;
}

.provider-card--local {
  border-color: rgba(99, 102, 241, 0.35);
  background: rgba(99, 102, 241, 0.06);
}

.provider-name {
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 0.6rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.95rem;
}

.provider-name i {
  color: #818cf8;
}

.badge-local {
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(99, 102, 241, 0.25);
  color: #a5b4fc;
  border-radius: 8px;
  padding: 0.1rem 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.provider-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.provider-table td {
  padding: 0.2rem 0.4rem;
  color: var(--color-text-muted);
}

.provider-table td:first-child {
  font-weight: 500;
  color: #9ca3af;
  width: 90px;
  white-space: nowrap;
}

.provider-table code {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  padding: 0.1rem 0.35rem;
  font-size: 0.8rem;
  color: #c4b5fd;
  font-family: monospace;
}

.provider-note {
  display: block;
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--color-text-muted);
  font-style: italic;
}

.modal-tip {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.2);
  border-radius: var(--border-radius-sm);
  padding: 0.85rem 1rem;
  font-size: 0.875rem;
  color: #fbbf24;
  line-height: 1.5;
}

.modal-tip i {
  margin-top: 0.1rem;
  flex-shrink: 0;
}

/* Modal transition */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
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

  .user-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.75rem;
    padding: 0.25rem;
    max-height: 300px;
  }

  .user-card {
    padding: 1rem 0.75rem;
  }

  .user-avatar {
    width: 40px;
    height: 40px;
  }

  .user-avatar i {
    font-size: 1rem;
  }

  .user-name {
    font-size: 0.8125rem;
  }

  .user-type {
    font-size: 0.6875rem;
  }

  .settings-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>