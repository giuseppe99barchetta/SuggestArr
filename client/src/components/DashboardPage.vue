<template>
  <div class="settings-container">
    <div 
      class="background-layer current-bg" 
      :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }"
      :class="{ 'fade-out': isTransitioning }"
    ></div>
    <div 
      class="background-layer next-bg" 
      :style="{ backgroundImage: 'url(' + nextBackgroundImageUrl + ')' }"
      :class="{ 'fade-in': isTransitioning }"
    ></div>
    <div class="settings-content">
      <!-- Header -->
      <div class="settings-header">

        <div class="header-content">
          <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank" rel="noopener noreferrer">
            <img src="@/assets/logo.png" alt="SuggestArr Logo" class="logo">
          </a>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <!-- Desktop Navigation -->
      <div class="tabs-navigation desktop-nav">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="['tab-button', { active: activeTab === tab.id }]"
        >
          <i :class="tab.icon"></i>
          <span>{{ tab.name }}</span>
          <!-- Badge per Requests -->
          <span v-if="tab.id === 'requests' && requestCount > 0" class="tab-badge">
            {{ requestCount }}
          </span>
        </button>
      </div>

      <!-- Mobile Navigation -->
      <div class="mobile-nav">
        <div class="mobile-tab-selector">
          <button 
            @click="showMobileDropdown = !showMobileDropdown"
            class="mobile-dropdown-button"
            :class="{ active: showMobileDropdown }"
          >
            <i :class="getCurrentTabIcon()"></i>
            <span class="current-tab-name">{{ getCurrentTabName() }}</span>
            <!-- Badge per Requests -->
            <span v-if="currentTabId === 'requests' && requestCount > 0" class="tab-badge">
              {{ requestCount }}
            </span>
            <i class="fas fa-chevron-down dropdown-arrow" :class="{ rotated: showMobileDropdown }"></i>
          </button>
          
          <transition name="dropdown-slide">
            <div v-if="showMobileDropdown" class="mobile-dropdown">
              <button
                v-for="tab in tabs"
                :key="tab.id"
                @click="selectMobileTab(tab.id)"
                :class="['mobile-dropdown-item', { active: activeTab === tab.id }]"
              >
                <i :class="tab.icon"></i>
                <span>{{ tab.name }}</span>
                <!-- Badge per Requests -->
                <span v-if="tab.id === 'requests' && requestCount > 0" class="tab-badge">
                  {{ requestCount }}
                </span>
              </button>
            </div>
          </transition>
        </div>
      </div>

      <!-- Tab Content -->
      <div class="tab-content">
        <transition name="fade-slide" mode="out-in">
          <component
            :key="activeTab"
            :is="activeTabComponent"
            :config="config"
            :isLoading="isLoading"
            :testingConnections="testingConnections"
            :getServiceStatus="getServiceStatus"
            :getServiceIcon="getServiceIcon"
            @save-section="saveSection"
            @test-connection="testConnection"
          />
        </transition>
      </div>

      <!-- Action Footer -->
      <div class="settings-footer">
        <div class="footer-info">
          <button 
                @click="showChangelog" 
                class="changelog-btn"
                title="View changelog for current version"
              >
          <i class="fas fa-info-circle"></i>
          </button>
          <div class="version-info">
            <div class="version-text-container">
              <span>SuggestArr {{ currentVersion }}</span>
              <span 
                v-if="currentImageTag === 'nightly'" 
                class="nightly-badge"
              >
                ({{ currentImageTag }})
              </span>
            </div>
            <button 
              @click="checkForUpdates" 
              :disabled="updateAvailable === null"
              class="version-check-btn"
              :class="{ 'update-available': updateAvailable }"
              :title="updateAvailable ? `Update available!` : 'Check for updates'"
            >
              <i :class="updateAvailable === null ? 'fas fa-spinner fa-spin' : updateAvailable ? 'fas fa-arrow-up' : 'fas fa-sync'"></i>
              <span v-if="updateAvailable" class="update-indicator">Update</span>
            </button>
          </div>
        </div>
        
        <div class="footer-actions">
          <button
            @click="exportConfig"
            class="btn btn-outline"
            :disabled="isLoading"
            title="Export configuration to JSON file">
            <i class="fas fa-download"></i>
            <span>Export</span>
          </button>
          
          <button
            @click="importConfig"
            class="btn btn-outline"
            :disabled="isLoading"
            title="Import configuration from JSON file">
            <i class="fas fa-upload"></i>
            <span>Import</span>
          </button>
          
          <button
            @click="resetConfig"
            class="btn btn-danger"
            :disabled="isLoading"
            title="Reset all settings to default">
            <i class="fas fa-trash-alt"></i>
            <span>Reset All</span>
          </button>
        </div>
      </div>

      <!-- Loading Overlay -->
      <transition name="fade">
        <div v-if="isLoading" class="loading-overlay">
          <div class="loading-content">
            <div class="spinner"></div>
            <p>{{ loadingMessage }}</p>
          </div>
        </div>
      </transition>

      <!-- Changelog Modal -->
      <transition name="fade">
        <div v-if="showChangelogModal" class="modal-overlay" @click.self="showChangelogModal = false">
          <div class="modal-content changelog-modal">
            <div class="modal-header">
              <i class="fab fa-github changelog-icon"></i>
              <h3>Changelog - {{ currentVersion }}</h3>
            </div>
            
            <div class="modal-body changelog-body">
              <div v-if="isLoadingChangelog" class="changelog-loading">
                <i class="fas fa-spinner fa-spin"></i>
                <span>Loading changelog...</span>
              </div>
              
              <div v-else-if="changelogError" class="changelog-error">
                <i class="fas fa-exclamation-triangle"></i>
                <span>{{ changelogError }}</span>
                <button @click="showChangelog" class="btn btn-secondary btn-sm">Retry</button>
              </div>
              
              <div v-else class="changelog-content">
                <div v-if="changelogData" v-html="changelogData"></div>
                <div v-else class="no-changelog">
                  <i class="fas fa-info-circle"></i>
                  <span>No changelog available for this version</span>
                </div>
              </div>
            </div>
            
            <div class="modal-actions">
              <a 
                :href="`https://github.com/giuseppe99barchetta/SuggestArr/releases/tag/${currentVersion}`" 
                target="_blank" 
                class="btn btn-outline"
                v-if="changelogData"
              >
                <i class="fas fa-external-link-alt"></i>
                View on GitHub
              </a>
              <button @click="showChangelogModal = false" class="btn btn-primary">
                <i class="fas fa-times"></i>
                Close
              </button>
            </div>
          </div>
        </div>
      </transition>

      <!-- Hidden file input for import -->
      <input
        type="file"
        ref="fileInput"
        @change="handleFileImport"
        accept=".json"
        style="display: none"
      />

      <!-- Reset Confirmation Modal -->
      <transition name="fade">
        <div v-if="showResetModal" class="modal-overlay" @click.self="showResetModal = false">
          <div class="modal-content">
            <div class="modal-header">
              <i class="fas fa-exclamation-triangle warning-icon"></i>
              <h3>Confirm Reset</h3>
            </div>
            
            <p class="modal-body">
              Are you sure you want to reset all settings to default? 
              <strong>This action cannot be undone</strong> and will:
            </p>
            
            <ul class="reset-warning-list">
              <li><i class="fas fa-times-circle"></i> Clear all service connections</li>
              <li><i class="fas fa-times-circle"></i> Remove all custom filters</li>
              <li><i class="fas fa-times-circle"></i> Reset scheduling preferences</li>
              <li><i class="fas fa-times-circle"></i> Clear database configuration</li>
            </ul>
            
            <div class="modal-actions">
              <button @click="showResetModal = false" class="btn btn-secondary">
                <i class="fas fa-times"></i>
                Cancel
              </button>
              <button @click="confirmReset" class="btn btn-danger">
                <i class="fas fa-exclamation-triangle"></i>
                Yes, Reset Everything
              </button>
            </div>
          </div>
        </div>
      </transition>

      <Footer />
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import Footer from './AppFooter.vue';
import backgroundManager from '@/api/backgroundManager';
import { fetchRandomMovieImage } from '@/api/tmdbApi';
import { useVersionCheck } from '@/composables/useVersionCheck';

// Import tab components
import SettingsGeneral from './settings/SettingsGeneral.vue';
import SettingsServices from './settings/SettingsServices.vue';
import SettingsDatabase from './settings/SettingsDatabase.vue';
import SettingsContentFilters from './settings/SettingsContentFilters.vue';
import SettingsAdvanced from './settings/SettingsAdvanced.vue';
import SettingsRequests from './settings/SettingsRequests.vue';
import LogsComponent from './LogsComponent.vue';

export default {
  name: 'SettingsPage',
  components: {
    Footer,
    SettingsGeneral,
    SettingsServices,
    SettingsDatabase,
    SettingsContentFilters,
    SettingsAdvanced,
    SettingsRequests,
    LogsComponent,
  },
  mixins: [backgroundManager],
  data() {
    return {
      config: {},
      isLoading: false,
      loadingMessage: 'Processing...',
      activeTab: 'requests',
      showResetModal: false,
      showChangelogModal: false,
      changelogData: null,
      isLoadingChangelog: false,
      changelogError: null,
      backgroundImageUrl: '',
      nextBackgroundImageUrl: '',
      isTransitioning: false,
      requestCount: 0,
      showMobileDropdown: false,
      // Cache per migliorare performance
      testingConnections: {
        tmdb: false,
        plex: false,
        jellyfin: false,
        seer: false,
        database: false,
      },
      tabs: [
        { id: 'requests', name: 'Requests', icon: 'fas fa-paper-plane' },
        { id: 'general', name: 'General', icon: 'fas fa-cog' },
        { id: 'services', name: 'Services', icon: 'fas fa-plug' },
        { id: 'database', name: 'Database', icon: 'fas fa-database' },
        { id: 'content_filters', name: 'Filters', icon: 'fas fa-filter' },
        { id: 'advanced', name: 'Advanced', icon: 'fas fa-sliders-h' },
        { id: 'logs', name: 'Logs', icon: 'fas fa-file-alt' },
      ],
    };
  },
  setup() {
    const { currentVersion, currentImageTag, currentBuildDate, updateAvailable, checkForUpdates } = useVersionCheck();
    
    return {
      currentVersion,
      currentImageTag,
      currentBuildDate,
      updateAvailable,
      checkForUpdates
    };
  },
  computed: {
    activeTabComponent() {
      const componentMap = {
        requests: 'SettingsRequests',
        general: 'SettingsGeneral',
        services: 'SettingsServices',
        database: 'SettingsDatabase',
        content_filters: 'SettingsContentFilters',
        advanced: 'SettingsAdvanced',
        logs: 'LogsComponent',
      };
      return componentMap[this.activeTab];
    },
    currentTabId() {
      return this.activeTab;
    },
  },
  watch: {
    isTransitioning(newValue) {
      if (newValue) {
        setTimeout(() => {
          this.backgroundImageUrl = this.nextBackgroundImageUrl;
          this.isTransitioning = false;
        }, 800);
      }
    }
  },
  async mounted() {
    try {
      await this.loadConfig();
      
      this.loadRequestCount();
      
      if (this.config.TMDB_API_KEY) {
        this.startBackgroundImageRotation(fetchRandomMovieImage, this.config.TMDB_API_KEY);
      }
    } catch (error) {
      console.error('Error during component mount:', error);
      this.isLoading = false;
    }
  },
  methods: {
    selectMobileTab(tabId) {
      this.activeTab = tabId;
      this.showMobileDropdown = false;
    },
    getCurrentTabName() {
      const currentTab = this.tabs.find(tab => tab.id === this.activeTab);
      return currentTab ? currentTab.name : '';
    },
    getCurrentTabIcon() {
      const currentTab = this.tabs.find(tab => tab.id === this.activeTab);
      return currentTab ? currentTab.icon : 'fas fa-question';
    },
    async loadConfig(force = false) {
      this.loadingMessage = 'Loading configuration...';
      this.isLoading = true;
      try {
        const response = await axios.get('/api/config/fetch', {
          timeout: 10000 // 10 second timeout
        });
        this.config = response.data;
      } catch (error) {
        this.$toast.open({
          message: 'Failed to load configuration',
          type: 'error',
          duration: 5000,
          position: 'top-right'
        });
        console.error('Error loading config:', error);
        if (error.code === 'ECONNABORTED') {
          this.$toast.open({
            message: 'Configuration loading timed out. Please check your connection.',
            type: 'warning',
            duration: 5000,
            position: 'top-right'
          });
        }
      } finally {
        this.isLoading = false;
      }
    },

    async loadRequestCount() {
      try {
        const response = await axios.get('/api/automation/requests/stats', {
          timeout: 5000 // 5 second timeout
        });
        this.requestCount = response.data.today || 0;
      } catch (error) {
        console.error('Error loading request count:', error);
      }
    },

    async showChangelog() {
      this.showChangelogModal = true;
      this.changelogError = null;
      
      if (!this.changelogData) {
        this.isLoadingChangelog = true;
        try {
          // Get release info from GitHub API
          const response = await axios.get(`https://api.github.com/repos/giuseppe99barchetta/SuggestArr/releases/tags/${this.currentVersion}`);
          
          if (response.data && response.data.body) {
            // Convert markdown to basic HTML
            this.changelogData = this.parseMarkdown(response.data.body);
          } else {
            this.changelogData = null;
          }
        } catch (error) {
          console.error('Error fetching changelog:', error);
          this.changelogError = 'Failed to load changelog from GitHub. Please check your internet connection.';
        } finally {
          this.isLoadingChangelog = false;
        }
      }
    },

    parseMarkdown(markdown) {
      if (!markdown) return '';
      
      // Basic markdown to HTML conversion
      return markdown
        // Headers
        .replace(/^### (.*$)/gim, '<h4>$1</h4>')
        .replace(/^## (.*$)/gim, '<h3>$1</h3>')
        .replace(/^# (.*$)/gim, '<h2>$1</h2>')
        // Bold
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // Italic
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // Links
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
        // Line breaks
        .replace(/\n/g, '<br>')
        // Lists (basic)
        .replace(/^- (.+)$/gim, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    },

    async saveSection({ section, data }) {
      this.loadingMessage = `Saving ${section} settings...`;
      this.isLoading = true;
      try {
        await axios.post(`/api/config/section/${section}`, data);
        Object.assign(this.config, data);

        this.$toast.open({
          message: `✅ ${section} settings saved successfully!`,
          type: 'success',
          duration: 3000,
          position: 'top-right'
        });
      } catch (error) {
        this.$toast.open({
          message: `❌ Failed to save ${section} settings`,
          type: 'error',
          duration: 5000,
          position: 'top-right'
        });
        console.error('Error saving section:', error);
      } finally {
        this.isLoading = false;
      }
    },
    async testConnection(service, config) {
      this.testingConnections[service] = true;
    
      try {
        let endpoint = '';
        let payload = {};
      
        switch (service) {
          case 'tmdb':
            endpoint = '/api/tmdb/test';
            payload = { api_key: config.api_key };
            break;
          case 'plex':
            endpoint = '/api/plex/test';
            payload = { token: config.token, api_url: config.api_url };
            break;
          case 'jellyfin':
            endpoint = '/api/jellyfin/test';
            payload = { 
              api_url: config.api_url,
              token: config.token 
            };
            break;
          case 'emby':
            endpoint = '/api/jellyfin/test';
            payload = { 
              api_url: config.api_url,
              token: config.token 
            };
            break;
          case 'seer':
            endpoint = '/api/seer/test';
            payload = { 
              api_url: config.api_url, 
              token: config.token 
            };
            break;
          case 'database':
            endpoint = '/api/config/test-db-connection';
            payload = {
              DB_TYPE: config.DB_TYPE,
              DB_HOST: config.DB_HOST,
              DB_PORT: config.DB_PORT,
              DB_NAME: config.DB_NAME,
              DB_USER: config.DB_USER,
              DB_PASSWORD: config.DB_PASSWORD,
            };
            break;
          default:
            throw new Error('Unknown service');
        }
      
        const response = await axios.post(endpoint, payload);
      
        if (this.$toast) {
          this.$toast.success(
            response.data.message || `${service.toUpperCase()} connection successful!`,
            {
              position: 'top-right',
              duration: 3000
            }
          );
        } else {
          alert(response.data.message || `${service.toUpperCase()} connection successful!`);
        }
      
        return response.data;
      
      } catch (error) {
        console.error(`${service} connection test failed:`, error);
      
        let errorMessage = 'Connection test failed';
      
        if (error.response) {
          const status = error.response.status;
          const data = error.response.data;
        
          if (status === 400) {
            errorMessage = data?.message || 'Invalid credentials or server unreachable. Please check your URL and token.';
          } else if (status === 401) {
            errorMessage = 'Invalid authentication token. Please check your API token.';
          } else if (status === 404) {
            errorMessage = 'Server not found. Please check your URL.';
          } else if (status === 500) {
            errorMessage = 'Server error. Please check server logs.';
          } else if (status === 503) {
            errorMessage = 'Service unavailable. The server might be down.';
          } else {
            errorMessage = data?.message || `Error ${status}: Connection failed`;
          }
        } else if (error.request) {
          errorMessage = 'No response from server. Check your network connection and server URL.';
        } else {
          errorMessage = error.message || 'Request configuration error';
        }
      
        if (this.$toast) {
          this.$toast.error(errorMessage, {
            position: 'top-right',
            duration: 5000
          });
        } else {
          alert(`Error: ${errorMessage}`);
        }
      
        return {
          status: 'error',
          message: errorMessage
        };
      
      } finally {
        this.testingConnections[service] = false;
      }
    },
    getServiceStatus() {
      const service = this.config.SELECTED_SERVICE;
      if (!service) return 'status-disconnected';
      
      if (service === 'plex' && this.config.PLEX_TOKEN) return 'status-connected';
      if ((service === 'jellyfin' || service === 'emby') && this.config.JELLYFIN_TOKEN) return 'status-connected';
      
      return 'status-warning';
    },

    getServiceIcon() {
      const icons = {
        plex: 'fas fa-play-circle',
        jellyfin: 'fas fa-server',
        emby: 'fas fa-server'
      };
      return icons[this.config.SELECTED_SERVICE] || 'fas fa-question-circle';
    },

    goToDashboard() {
      this.$router.push({ name: 'Home' });
    },

    async exportConfig() {
      this.loadingMessage = 'Exporting configuration...';
      this.isLoading = true;
      try {
        const response = await axios.get('/api/config/fetch');
        const configData = response.data;

        const blob = new Blob([JSON.stringify(configData, null, 2)], {
          type: 'application/json',
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `suggestarr-config-${new Date().toISOString().split('T')[0]}.json`;
        link.click();
        URL.revokeObjectURL(url);

        this.$toast.open({
          message: 'Configuration exported successfully!',
          type: 'success',
          duration: 3000,
          position: 'top-right'
        });
      } catch (error) {
        this.$toast.open({
          message: 'Failed to export configuration',
          type: 'error',
          duration: 5000,
          position: 'top-right'
        });
        console.error('Error exporting config:', error);
      } finally {
        this.isLoading = false;
      }
    },

    importConfig() {
      this.$refs.fileInput.click();
    },

    async handleFileImport(event) {
      const file = event.target.files[0];
      if (!file) return;

      this.loadingMessage = 'Importing configuration...';
      this.isLoading = true;
      
      try {
        const text = await file.text();
        const configData = JSON.parse(text);

        await axios.post('/api/config/save', configData);
        await this.loadConfig();

        this.$toast.open({
          message: 'Configuration imported successfully!',
          type: 'success',
          duration: 3000,
          position: 'top-right'
        });
      } catch (error) {
        this.$toast.open({
          message: 'Failed to import: Invalid file format',
          type: 'error',
          duration: 5000,
          position: 'top-right'
        });
        console.error('Error importing config:', error);
      } finally {
        this.isLoading = false;
        event.target.value = '';
      }
    },

    resetConfig() {
      this.showResetModal = true;
    },

    async confirmReset() {
      this.showResetModal = false;
      this.loadingMessage = 'Resetting configuration...';
      this.isLoading = true;

      try {
        await axios.post('/api/config/reset');
        this.$toast.open({
          message: 'Configuration reset successfully!',
          type: 'success',
          duration: 3000,
          position: 'top-right'
        });

        setTimeout(() => {
          this.$router.push({ name: 'Home' });
        }, 1000);
      } catch (error) {
        this.$toast.open({
          message: 'Failed to reset configuration',
          type: 'error',
          duration: 5000,
          position: 'top-right'
        });
        console.error('Error resetting config:', error);
      } finally {
        this.isLoading = false;
      }
    },
  },
  beforeUnmount() {
    this.stopBackgroundImageRotation();
  },
};
</script>

<style scoped>
.settings-container {
  min-height: 100vh;
  position: relative;
}

.background-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
  transition: opacity 0.8s ease-in-out;
}

.current-bg {
  opacity: 1;
}

.current-bg.fade-out {
  opacity: 0;
}

.next-bg {
  opacity: 0;
}

.next-bg.fade-in {
  opacity: 1;
}

.settings-content {
  min-height: 100vh;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(10px);
  padding: 2rem;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border-light);
  position: relative;
  z-index: 1;
}

.settings-header {
  margin-bottom: 2rem;
  display: flex;
  flex-direction: column;
}

.header-content {
  text-align: center;
}

.back-button {
  align-self: flex-start;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  background-color: var(--color-bg-interactive);
  color: var(--color-text-muted);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  cursor: pointer;
  transition: var(--transition-base);
  font-size: 0.9rem;
  font-weight: 500;
}

.back-button:hover {
  background-color: var(--color-bg-active);
  color: var(--color-text-primary);
  transform: translateX(-4px);
}

.logo {
  width: 100px;
  height: auto;
  margin: 0 auto 1rem auto; /* Center horizontally */
  display: block; /* Ensure block-level element */
  transition: transform 0.3s ease;
}

.logo:hover {
  transform: scale(1.05);
}

.settings-title {
  font-size: 2.5rem;
  font-weight: bold;
  color: var(--color-text-primary);
  margin-bottom: 0.5rem;
}

.settings-subtitle {
  color: var(--color-text-muted);
  font-size: 1.1rem;
  margin-bottom: 1.5rem;
}

/* Status Indicators */
.status-indicators {
  display: flex;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 1rem;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
  border: 2px solid;
  transition: var(--transition-base);
}

.status-connected {
  background-color: rgba(16, 185, 129, 0.1);
  border-color: var(--color-success);
  color: var(--color-success);
}

.status-disconnected {
  background-color: rgba(239, 68, 68, 0.1);
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.status-warning {
  background-color: rgba(245, 158, 11, 0.1);
  border-color: var(--color-warning);
  color: var(--color-warning);
}


/* Content */
.tab-content {
  flex: 1;
  border-radius: var(--border-radius-lg);
  padding: 2rem;
  backdrop-filter: blur(10px);
  border: 1px solid var(--color-border-light);
  min-height: 400px;
}

/* Transitions */
.fade-slide-enter-active, .fade-slide-leave-active {
  transition: all 0.3s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* Footer */
.settings-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid var(--color-border-light);
  flex-wrap: wrap;
  gap: 1rem;
}

.footer-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--color-text-muted);
  font-size: 0.85rem;
}

.version-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.version-text-container {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.changelog-btn {
  background: none;
  border: none;
  color: var(--color-text-muted);
  cursor: pointer;
  padding: 0.25rem;
  border-radius: var(--border-radius-sm);
  transition: var(--transition-base);
  font-size: 0.875rem;
}

.changelog-btn:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-interactive);
}

.version-check-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.25rem 0.625rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-muted);
  font-size: 0.8rem;
  cursor: pointer;
  transition: var(--transition-base);
  position: relative;
}

.version-check-btn:hover:not(:disabled) {
  background: var(--color-bg-active);
  border-color: var(--color-border-medium);
  color: var(--color-text-primary);
}

.version-check-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.version-check-btn.update-available {
  background: var(--color-success, #28a745);
  border-color: var(--color-success, #28a745);
  color: white;
}

.version-check-btn.update-available:hover {
  background: #218838;
  border-color: #218838;
}

.update-indicator {
  background: rgba(255, 255, 255, 0.2);
  padding: 0.125rem 0.375rem;
  border-radius: var(--border-radius-xs);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.footer-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.btn {
  padding: 0.75rem 1.5rem;
  border-radius: var(--border-radius-sm);
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition-base);
  border: none;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: #6b7280;
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background-color: #4b5563;
}

.btn-outline {
  background: var(--color-bg-interactive);
  color: var(--color-text-primary);
  border: 2px solid var(--color-border-medium);
}

.btn-outline:hover:not(:disabled) {
  background-color: var(--color-bg-active);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.btn-danger {
  background-color: var(--color-danger);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background-color: #dc2626;
}

.tab-badge {
  background: #ef4444;
  color: white;
  font-size: 0.75rem;
  padding: 0.125rem 0.5rem;
  border-radius: 12px;
  font-weight: 700;
  margin-left: 0.5rem;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.tab-button.active .tab-badge {
  background: rgba(255, 255, 255, 0.3);
  color: white;
}

/* Loading Overlay */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--color-bg-overlay-heavy);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.loading-content {
  text-align: center;
  color: var(--color-text-primary);
}

.spinner {
  width: 50px;
  height: 50px;
  border: 4px solid var(--color-border-medium);
  border-top: 4px solid var(--color-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.warning-icon {
  font-size: 2rem;
  color: var(--color-warning);
}

.modal-content h3 {
  color: var(--color-text-primary);
  margin: 0;
  font-size: 1.5rem;
}

.modal-body {
  color: var(--color-text-muted);
  margin-bottom: 1.5rem;
  line-height: 1.6;
}

.reset-warning-list {
  list-style: none;
  padding: 0;
  margin: 0 0 2rem 0;
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--color-danger);
  border-radius: var(--border-radius-sm);
  padding: 1rem;
}

.reset-warning-list li {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--color-danger);
  padding: 0.5rem 0;
  font-size: 0.9rem;
}

.reset-warning-list li i {
  font-size: 1rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--color-bg-overlay-heavy);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-content {
  background-color: var(--color-bg-content);
  backdrop-filter: blur(10px);
  padding: 2rem;
  border-radius: var(--border-radius-lg);
  border: 1px solid var(--color-border-light);
  max-width: 500px;
  width: 100%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.warning-icon {
  font-size: 2rem;
  color: var(--color-warning);
}

.modal-content h3 {
  color: var(--color-text-primary);
  margin: 0;
  font-size: 1.5rem;
}

.modal-body {
  color: var(--color-text-muted);
  margin-bottom: 1.5rem;
  line-height: 1.6;
}

.reset-warning-list {
  list-style: none;
  padding: 0;
  margin: 0 0 2rem 0;
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--color-danger);
  border-radius: var(--border-radius-sm);
  padding: 1rem;
}

.reset-warning-list li {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--color-danger);
  padding: 0.5rem 0;
  font-size: 0.9rem;
}

.reset-warning-list li i {
  font-size: 1rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

/* Changelog Specific Styles */
.changelog-modal {
  max-width: 700px;
  max-height: 80vh;
  overflow-y: auto;
}

.changelog-icon {
  color: var(--color-text-primary);
  font-size: 1.5rem;
}

.changelog-body {
  max-height: 50vh;
  overflow-y: auto;
  padding: 1rem 0;
}

.changelog-loading,
.changelog-error,
.no-changelog {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 2rem;
  color: var(--color-text-muted);
  text-align: center;
}

.changelog-loading i,
.changelog-error i,
.no-changelog i {
  font-size: 2rem;
}

.changelog-error {
  color: var(--color-danger);
}

.changelog-content {
  line-height: 1.6;
  color: var(--color-text-primary);
}

.changelog-content h2 {
  color: var(--color-text-primary);
  margin: 1.5rem 0 1rem 0;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid var(--color-border-medium);
}

.changelog-content h3 {
  color: var(--color-text-primary);
  margin: 1.25rem 0 0.75rem 0;
}

.changelog-content h4 {
  color: var(--color-text-primary);
  margin: 1rem 0 0.5rem 0;
}

.changelog-content ul {
  margin: 0.5rem 0 1rem 0;
  padding-left: 1.5rem;
}

.changelog-content li {
  margin: 0.5rem 0;
  color: var(--color-text-secondary);
}

.changelog-content strong {
  color: var(--color-text-primary);
  font-weight: 600;
}

.changelog-content a {
  color: var(--color-primary, #007bff);
  text-decoration: none;
  border-bottom: 1px dotted var(--color-primary, #007bff);
}

.changelog-content a:hover {
  color: var(--color-primary-hover, #0056b3);
  border-bottom-style: solid;
}

/* Fade Transition */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* Fade Transition */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* Mobile Navigation */
.mobile-nav {
  display: none;
}

.mobile-tab-selector {
  position: relative;
  margin-bottom: 1.5rem;
}

.mobile-dropdown-button {
  width: 100%;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  color: var(--color-text-primary);
  padding: 1rem;
  border-radius: var(--border-radius-sm);
  cursor: pointer;
  transition: var(--transition-base);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1rem;
  font-weight: 500;
  justify-content: space-between;
  min-height: 52px; /* Touch target minimum */
}

.mobile-dropdown-button:hover {
  background-color: var(--color-bg-active);
}

.mobile-dropdown-button.active {
  background-color: var(--button-active-bg);
  border-color: var(--color-primary);
}

.current-tab-name {
  flex: 1;
  text-align: left;
}

.dropdown-arrow {
  transition: transform 0.3s ease;
  color: var(--color-text-muted);
}

.dropdown-arrow.rotated {
  transform: rotate(180deg);
}

.mobile-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: var(--color-bg-content);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  margin-top: 0.5rem;
  z-index: 100;
  box-shadow: var(--shadow-base);
  backdrop-filter: blur(10px);
  max-height: 300px;
  overflow-y: auto;
}

.mobile-dropdown-item {
  width: 100%;
  background: transparent;
  border: none;
  color: var(--color-text-muted);
  padding: 1rem 1.25rem;
  cursor: pointer;
  transition: var(--transition-base);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.95rem;
  text-align: left;
  border-bottom: 1px solid var(--color-border-light);
  min-height: 48px; /* Touch target minimum */
}

.mobile-dropdown-item:last-child {
  border-bottom: none;
}

.mobile-dropdown-item:hover {
  background-color: var(--color-bg-interactive);
  color: var(--color-text-primary);
}

.mobile-dropdown-item.active {
  background-color: var(--button-active-bg);
  color: var(--color-text-primary);
}

/* Desktop Navigation Hide on Mobile */
.desktop-nav {
  display: flex;
}

/* Mobile Responsive */
@media (max-width: 768px) {
  .desktop-nav {
    display: none;
  }

  .mobile-nav {
    display: block;
  }

  .settings-content {
    padding: 1rem;
  }

  .settings-title {
    font-size: 2rem;
  }

  .back-button span {
    display: none;
  }

  .status-indicators {
    gap: 0.5rem;
  }

  .status-badge {
    font-size: 0.75rem;
    padding: 0.4rem 0.8rem;
  }

  .tab-content {
    padding: 1rem;
  }

  .settings-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .footer-info {
    order: 2;
    justify-content: center;
  }

  .version-info {
    flex-direction: column;
    gap: 0.5rem;
    text-align: center;
  }

  .version-text-container {
    justify-content: center;
  }

  .version-check-btn {
    font-size: 0.75rem;
    padding: 0.3125rem 0.5rem;
  }

  .update-indicator {
    font-size: 0.6875rem;
  }

  .changelog-modal {
    max-width: 95%;
    margin: 1rem;
  }

  .footer-actions {
    order: 1;
    flex-direction: column;
  }

  .btn {
    width: 100%;
    justify-content: center;
    min-height: 48px; /* Touch target minimum */
    min-width: 48px; /* Ensure minimum touch target */
  }

  .modal-content {
    padding: 1.5rem;
    margin: 1rem;
    max-width: none;
  }

  .modal-actions {
    flex-direction: column;
  }

  .modal-actions .btn {
    width: 100%;
  }
}

/* Dropdown Transition */
.dropdown-slide-enter-active,
.dropdown-slide-leave-active {
  transition: all 0.3s ease;
  transform-origin: top;
}

.dropdown-slide-enter-from {
  opacity: 0;
  transform: scaleY(0.8) translateY(-10px);
}

.dropdown-slide-leave-to {
  opacity: 0;
  transform: scaleY(0.8) translateY(-10px);
}

</style>
