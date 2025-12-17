<template>
  <div class="settings-container" :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">
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
      <div class="tabs-navigation">
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
          <i class="fas fa-info-circle"></i>
          <span>Changes are saved per section automatically</span>
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
      backgroundImageUrl: '',
      requestCount: 0,
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
        { id: 'content_filters', name: 'Content Filters', icon: 'fas fa-filter' },
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
        database: 'SettingsDatabase',
        content_filters: 'SettingsContentFilters',
        advanced: 'SettingsAdvanced',
        logs: 'LogsComponent',
      };
      return componentMap[this.activeTab];
    },
  },
  async mounted() {
    await this.loadConfig();
    await this.loadRequestCount();
    this.startBackgroundImageRotation(
      this.config.TMDB_API_KEY ? fetchRandomMovieImage : null,
      this.config.TMDB_API_KEY
    );
  },
  methods: {
    async loadConfig() {
      this.loadingMessage = 'Loading configuration...';
      this.isLoading = true;
      try {
        const response = await axios.get('/api/config/fetch');
        this.config = response.data;
      } catch (error) {
        this.$toast.open({
          message: 'Failed to load configuration',
          type: 'error',
          duration: 5000,
          position: 'top-right'
        });
        console.error('Error loading config:', error);
      } finally {
        this.isLoading = false;
      }
    },

    async loadRequestCount() {
      try {
        const response = await axios.get('/api/automation/requests/stats');
        this.requestCount = response.data.today || 0;
      } catch (error) {
        console.error('Error loading request count:', error);
      }
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

    async testConnection(type, data) {
      try {
        this.testingConnections[type] = true;

        const endpoints = {
          tmdb: '/api/tmdb/test',
          jellyfin: '/api/jellyfin/test',
          plex: '/api/plex/test',
          seer: '/api/seer/test',
          database: '/api/config/test-db-connection',
        };

        const endpoint = endpoints[type];
        if (!endpoint) throw new Error(`Unknown connection type: ${type}`);

        const response = await axios.post(endpoint, data);
        
        if (response.data.status === 'success') {
          this.$toast.open({
            message: `${type.toUpperCase()} connection successful!`,
            type: 'success',
            duration: 3000,
            position: 'top-right'
          });
        } else {
          this.$toast.open({
            message: `${type.toUpperCase()} connection failed`,
            type: 'error',
            duration: 5000,
            position: 'top-right'
          });
        }
        return response.data;
      } catch (error) {
        this.$toast.open({
          message: `${type.toUpperCase()} connection test failed`,
          type: 'error',
          duration: 5000,
          position: 'top-right'
        });
        throw error;
      } finally {
        this.testingConnections[type] = false;
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
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}

.settings-content {
  min-height: 100vh;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(10px);
  padding: 2rem;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border-light);
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

/* Tabs */
.tabs-navigation {
  display: flex;
  justify-content: center;
  margin-bottom: 2rem;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.tab-button {
  background-color: var(--color-bg-interactive);
  border: 2px solid var(--color-border-light);
  color: var(--color-text-muted);
  padding: 0.75rem 1.5rem;
  border-radius: var(--border-radius-md);
  cursor: pointer;
  transition: var(--transition-base);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  font-weight: 500;
}

.tab-button:hover {
  background-color: var(--color-bg-active);
  color: var(--color-text-primary);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.tab-button.active {
  background-color: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
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

/* Fade Transition */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* Mobile Responsive */
@media (max-width: 768px) {
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

  .tabs-navigation {
    justify-content: flex-start;
    overflow-x: auto;
    padding-bottom: 0.5rem;
  }

  .tab-button {
    flex-shrink: 0;
    font-size: 0.8rem;
    padding: 0.6rem 1rem;
  }

  .tab-button span {
    display: none;
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

  .footer-actions {
    order: 1;
    flex-direction: column;
  }

  .btn {
    width: 100%;
    justify-content: center;
  }

  .modal-content {
    padding: 1.5rem;
  }

  .modal-actions {
    flex-direction: column;
  }

  .modal-actions .btn {
    width: 100%;
  }
}
</style>
