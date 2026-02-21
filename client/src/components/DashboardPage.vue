<template>
  <div class="settings-container">
    <div 
      class="background-layer current-bg" 
      :style="{ backgroundImage: 'url(' + currentBackgroundUrl + ')' }"
      :class="{ 'fade-out': isTransitioning }"
    ></div>
    <div 
      class="background-layer next-bg" 
      :style="{ backgroundImage: 'url(' + nextBackgroundUrl + ')' }"
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
            title="Reset all settings to defaults">
            <i class="fas fa-undo"></i>
            <span>Reset</span>
          </button>
          
          <button
            @click="forceRunAutomation"
            class="btn btn-secondary"
            :disabled="isForceRunning"
            title="Force run automation script now">
            <i :class="isForceRunning ? 'fas fa-spinner fa-spin' : 'fas fa-play'"></i>
            <span>Force Run</span>
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
import { useBackgroundImage } from '@/composables/useBackgroundImage';
import { useVersionCheck } from '@/composables/useVersionCheck';
import '@/assets/styles/dashboardPage.css';

// Import tab components
import SettingsGeneral from './settings/SettingsGeneral.vue';
import SettingsServices from './settings/SettingsServices.vue';
import SettingsDatabase from './settings/SettingsDatabase.vue';
import SettingsAdvanced from './settings/SettingsAdvanced.vue';
import SettingsRequests from './settings/SettingsRequests.vue';
import SettingsJobs from './settings/SettingsJobs.vue';
import LogsComponent from './LogsComponent.vue';

export default {
  name: 'SettingsPage',
  components: {
    Footer,
    SettingsGeneral,
    SettingsServices,
    SettingsDatabase,
    SettingsAdvanced,
    SettingsRequests,
    SettingsJobs,
    LogsComponent,
  },
  setup() {
    const { currentBackgroundUrl, nextBackgroundUrl, isTransitioning, startDefaultImageRotation, startBackgroundImageRotation, stopBackgroundImageRotation } = useBackgroundImage();
    const { currentVersion, currentImageTag, currentBuildDate, updateAvailable, checkForUpdates } = useVersionCheck();
    
    return {
      currentBackgroundUrl,
      nextBackgroundUrl,
      isTransitioning,
      startDefaultImageRotation,
      startBackgroundImageRotation,
      stopBackgroundImageRotation,
      currentVersion,
      currentImageTag,
      currentBuildDate,
      updateAvailable,
      checkForUpdates
    };
  },
    data() {
    return {
      config: {},
      isLoading: false,
      isForceRunning: false,
      loadingMessage: 'Processing...',
      activeTab: 'requests',
      showResetModal: false,
      showChangelogModal: false,
      changelogData: null,
      isLoadingChangelog: false,
      changelogError: null,
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
        { id: 'jobs', name: 'Jobs', icon: 'fas fa-briefcase' },
        { id: 'database', name: 'Database', icon: 'fas fa-database' },
        { id: 'advanced', name: 'Advanced', icon: 'fas fa-sliders-h' },
        { id: 'logs', name: 'Logs', icon: 'fas fa-file-alt' },
      ],
    };
  },
  computed: {
    activeTabComponent() {
      const componentMap = {
        requests: 'SettingsRequests',
        general: 'SettingsGeneral',
        services: 'SettingsServices',
        jobs: 'SettingsJobs',
        database: 'SettingsDatabase',
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
        // Handle background transition state if needed
      }
    }
  },
  async mounted() {
    try {
      await this.loadConfig();
      
      this.loadRequestCount();
      
      if (this.config.TMDB_API_KEY) {
        this.startBackgroundImageRotation(this.config.TMDB_API_KEY);
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
          message: `Settings saved successfully!`,
          type: 'success',
          duration: 3000,
          position: 'top-right'
        });
      } catch (error) {
        this.$toast.open({
          message: `Failed to save settings, see logs for details.`,
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

    async forceRunAutomation() {
      this.isForceRunning = true;
      this.loadingMessage = 'Manually running fetch...';

      try {
        await axios.post('/api/automation/force_run');
        this.$toast.open({
          message: 'Force run started in the background!',
          type: 'success',
          duration: 3000,
          position: 'top-right'
        });
      } catch (error) {
        if (error.response && error.response.status === 409) {
          this.$toast.open({
            message: 'A force run is already in progress.',
            type: 'warning',
            duration: 4000,
            position: 'top-right'
          });
        } else {
          this.$toast.open({
            message: 'Force run failed, see logs for details.',
            type: 'error',
            duration: 5000,
            position: 'top-right'
          });
          console.error('Error force running automation:', error);
        }
      } finally {
        this.isForceRunning = false;
        this.loadingMessage = 'Processing...';
      }
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
          this.$router.push({ name: 'Setup' });
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
};
</script>
