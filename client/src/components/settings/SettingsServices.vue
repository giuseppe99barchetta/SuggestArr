<template>
  <div class="settings-services">
    <div class="section-header">
      <h2>Service Configuration</h2>
      <p>Configure external service connections</p>
    </div>

    <div class="settings-grid">
      <!-- TMDB Configuration -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-film"></i>
          TMDB API
        </h3>

        <div class="form-group">
          <label for="tmdbApiKey">TMDB API Key</label>
          <div class="input-group">
            <input
              id="tmdbApiKey"
              v-model="localConfig.TMDB_API_KEY"
              :type="showTmdbKey ? 'text' : 'password'"
              placeholder="Enter your TMDB API key"
              class="form-control"
              :disabled="isLoading"
            />
            <button
              @click="showTmdbKey = !showTmdbKey"
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="isLoading"
            >
              <i :class="showTmdbKey ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
          <small class="form-help">
            API key for The Movie Database. Get one from
            <a href="https://www.themoviedb.org/settings/api" target="_blank" class="link">TMDB Settings</a>
          </small>
        </div>

        <div class="form-group">
          <button
            @click="testTmdbConnection"
            class="btn btn-outline"
            :disabled="isLoading || !localConfig.TMDB_API_KEY || testingConnections.tmdb"
          >
            <i v-if="testingConnections.tmdb" class="fas fa-spinner fa-spin"></i>
            <i v-else class="fas fa-plug"></i>
            {{ testingConnections.tmdb ? 'Testing...' : 'Test Connection' }}
          </button>
        </div>
      </div>

      <!-- Media Server Configuration -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-server"></i>
          Media Server
        </h3>

        <BaseDropdown
          v-model="localConfig.SELECTED_SERVICE"
          :options="serviceOptions"
          label="Selected Service"
          placeholder="Select a service"
          help-text="Choose your media server"
          :disabled="isLoading"
          id="selectedService"
        />

        <!-- Plex Configuration -->
        <div v-if="localConfig.SELECTED_SERVICE === 'plex'" class="service-config">
          <div class="form-group">
            <label for="plexToken">Plex Token</label>
            <div class="input-group">
              <input
                id="plexToken"
                v-model="localConfig.PLEX_TOKEN"
                :type="showPlexToken ? 'text' : 'password'"
                placeholder="Enter your Plex token"
                class="form-control"
                :disabled="isLoading"
              />
              <button
                @click="showPlexToken = !showPlexToken"
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="isLoading"
              >
                <i :class="showPlexToken ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
              </button>
            </div>
          </div>

          <div class="form-group">
            <label for="plexApiUrl">Plex API URL</label>
            <input
              id="plexApiUrl"
              v-model="localConfig.PLEX_API_URL"
              type="url"
              placeholder="http://localhost:32400"
              class="form-control"
              :disabled="isLoading"
            />
          </div>

          <div class="form-group">
            <button
              @click="testPlexConnection"
              class="btn btn-outline"
              :disabled="isLoading || !localConfig.PLEX_TOKEN || !localConfig.PLEX_API_URL || testingConnections.plex"
            >
              <i v-if="testingConnections.plex" class="fas fa-spinner fa-spin"></i>
              <i v-else class="fas fa-plug"></i>
              {{ testingConnections.plex ? 'Testing...' : 'Test Plex Connection' }}
            </button>
          </div>
        </div>

        <!-- Jellyfin Configuration -->
        <div v-if="localConfig.SELECTED_SERVICE === 'jellyfin'" class="service-config">
          <div class="form-group">
            <label for="jellyfinApiUrl">Jellyfin API URL</label>
            <input
              id="jellyfinApiUrl"
              v-model="localConfig.JELLYFIN_API_URL"
              type="url"
              placeholder="http://localhost:8096"
              class="form-control"
              :disabled="isLoading"
            />
          </div>

          <div class="form-group">
            <label for="jellyfinToken">Jellyfin Token</label>
            <div class="input-group">
              <input
                id="jellyfinToken"
                v-model="localConfig.JELLYFIN_TOKEN"
                :type="showJellyfinToken ? 'text' : 'password'"
                placeholder="Enter your Jellyfin API token"
                class="form-control"
                :disabled="isLoading"
              />
              <button
                @click="showJellyfinToken = !showJellyfinToken"
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="isLoading"
              >
                <i :class="showJellyfinToken ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
              </button>
            </div>
          </div>

          <div class="form-group">
            <button
              @click="testJellyfinConnection"
              class="btn btn-outline"
              :disabled="isLoading || !localConfig.JELLYFIN_API_URL || !localConfig.JELLYFIN_TOKEN || testingConnections.jellyfin"
            >
              <i v-if="testingConnections.jellyfin" class="fas fa-spinner fa-spin"></i>
              <i v-else class="fas fa-plug"></i>
              {{ testingConnections.jellyfin ? 'Testing...' : 'Test Jellyfin Connection' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Overseer/Jellyseer Configuration -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-list-alt"></i>
          Overseer/Jellyseer
        </h3>

        <div class="form-group">
          <label for="seerApiUrl">API URL</label>
          <input
            id="seerApiUrl"
            v-model="localConfig.SEER_API_URL"
            type="url"
            placeholder="http://localhost:5055"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">URL for your Overseer or Jellyseer instance</small>
        </div>

        <div class="form-group">
          <label for="seerToken">API Token</label>
          <div class="input-group">
            <input
              id="seerToken"
              v-model="localConfig.SEER_TOKEN"
              :type="showSeerToken ? 'text' : 'password'"
              placeholder="Enter your API token"
              class="form-control"
              :disabled="isLoading"
            />
            <button
              @click="showSeerToken = !showSeerToken"
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="isLoading"
            >
              <i :class="showSeerToken ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
        </div>

        <div class="form-group">
          <label for="seerUserName">Username</label>
          <input
            id="seerUserName"
            v-model="localConfig.SEER_USER_NAME"
            type="text"
            placeholder="Your username"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">Username for making requests</small>
        </div>

        <div class="form-group">
          <button
            @click="testSeerConnection"
            class="btn btn-outline"
            :disabled="isLoading || !localConfig.SEER_API_URL || !localConfig.SEER_TOKEN || testingConnections.seer"
          >
            <i v-if="testingConnections.seer" class="fas fa-spinner fa-spin"></i>
            <i v-else class="fas fa-plug"></i>
            {{ testingConnections.seer ? 'Testing...' : 'Test Connection' }}
          </button>
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
import BaseDropdown from '@/components/common/BaseDropdown.vue';

export default {
  name: 'SettingsServices',
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
    testingConnections: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['save-section', 'test-connection'],
  data() {
    return {
      localConfig: {},
      originalConfig: {},
      showTmdbKey: false,
      showPlexToken: false,
      showJellyfinToken: false,
      showSeerToken: false,
      serviceOptions: [
        { value: 'plex', label: 'Plex' },
        { value: 'jellyfin', label: 'Jellyfin' },
        { value: 'emby', label: 'Emby (Experimental)' }
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
      },
    },
  },
  methods: {
    async testTmdbConnection() {
      try {
        await this.$emit('test-connection', 'tmdb', {
          api_key: this.localConfig.TMDB_API_KEY,
        });
      } catch (error) {
        console.error('Error testing TMDB connection:', error);
      }
    },

    async testPlexConnection() {
      try {
        await this.$emit('test-connection', 'plex', {
          token: this.localConfig.PLEX_TOKEN,
          api_url: this.localConfig.PLEX_API_URL,
        });
      } catch (error) {
        console.error('Error testing Plex connection:', error);
      }
    },

    async testJellyfinConnection() {
      try {
        await this.$emit('test-connection', 'jellyfin', {
          api_url: this.localConfig.JELLYFIN_API_URL,
          token: this.localConfig.JELLYFIN_TOKEN,
        });
      } catch (error) {
        console.error('Error testing Jellyfin connection:', error);
      }
    },

    async testSeerConnection() {
      try {
        await this.$emit('test-connection', 'seer', {
          api_url: this.localConfig.SEER_API_URL,
          token: this.localConfig.SEER_TOKEN,
        });
      } catch (error) {
        console.error('Error testing Seer connection:', error);
      }
    },

    async saveSettings() {
      try {
        const dataToSave = {
          TMDB_API_KEY: this.localConfig.TMDB_API_KEY,
          SELECTED_SERVICE: this.localConfig.SELECTED_SERVICE,
        };

        // Add service-specific data
        if (this.localConfig.SELECTED_SERVICE === 'plex') {
          Object.assign(dataToSave, {
            PLEX_TOKEN: this.localConfig.PLEX_TOKEN,
            PLEX_API_URL: this.localConfig.PLEX_API_URL,
            PLEX_LIBRARIES: this.localConfig.PLEX_LIBRARIES || [],
          });
        } else if (this.localConfig.SELECTED_SERVICE === 'jellyfin') {
          Object.assign(dataToSave, {
            JELLYFIN_API_URL: this.localConfig.JELLYFIN_API_URL,
            JELLYFIN_TOKEN: this.localConfig.JELLYFIN_TOKEN,
            JELLYFIN_LIBRARIES: this.localConfig.JELLYFIN_LIBRARIES || [],
          });
        }

        // Add Overseer/Jellyseer data
        Object.assign(dataToSave, {
          SEER_API_URL: this.localConfig.SEER_API_URL,
          SEER_TOKEN: this.localConfig.SEER_TOKEN,
          SEER_USER_NAME: this.localConfig.SEER_USER_NAME || null,
        });

        await this.$emit('save-section', {
          section: 'services',
          data: dataToSave,
        });

        this.originalConfig = { ...this.localConfig };
      } catch (error) {
        console.error('Error saving service settings:', error);
      }
    },

    async resetToDefaults() {
      const defaults = {
        TMDB_API_KEY: '',
        SELECTED_SERVICE: '',
        PLEX_TOKEN: '',
        PLEX_API_URL: '',
        PLEX_LIBRARIES: [],
        JELLYFIN_API_URL: '',
        JELLYFIN_TOKEN: '',
        JELLYFIN_LIBRARIES: [],
        SEER_API_URL: '',
        SEER_TOKEN: '',
        SEER_USER_NAME: null,
      };

      if (confirm('Are you sure you want to reset all service settings to their defaults?')) {
        this.localConfig = { ...this.localConfig, ...defaults };
        await this.saveSettings();
      }
    },
  },
};
</script>

<style scoped>
.settings-services {
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
  background-color: var(--color-bg-content-secondary);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-md);
  padding: 1.5rem;
}

.settings-group h3 {
  font-size: 1.2rem;
  margin-bottom: 1rem;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.service-config {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--color-border-light);
}

/* Spinner animation */
.fa-spinner.fa-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Testing state button styling */
.btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.btn:disabled .fa-spinner {
  animation: spin 1s linear infinite;
}

.form-group label {
  display: block;
  margin-top: 0.5rem;
  font-weight: 500;
  color: var(--color-text-secondary);
}

.form-group button {
  margin-top: 0.5rem;
}

.form-control {
  width: 100%;
  padding: 0.75rem;
  background-color: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-primary);
  font-size: 1rem;
  transition: var(--transition-base);
}

.form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  background-color: var(--color-bg-active);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-group {
  display: flex;
  gap: 0.5rem;
}

.input-group .form-control {
  flex: 1;
}

.select-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.select-wrapper .form-control {
  padding-right: 2.5rem;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
}

.chevron-indicator {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--color-text-muted);
  font-size: 0.75rem;
  transition: transform 0.2s ease;
}

.select-wrapper:focus-within .chevron-indicator {
  transform: translateY(-50%) rotate(180deg);
  color: var(--color-primary);
}

.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: var(--color-text-muted);
  line-height: 1.4;
}

.link {
  color: var(--color-primary);
  text-decoration: none;
}

.link:hover {
  text-decoration: underline;
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

@media (max-width: 768px) {
  .settings-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .settings-group {
    padding: 1rem;
  }

  .input-group {
    flex-direction: column;
  }

  .settings-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>