<template>
  <div class="settings-container" :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">
    <div class="settings-content">
      <!-- Header -->
      <div class="settings-header">
        <!-- Back Button -->
        <button @click="goToDashboard" class="back-button">
          <i class="fas fa-arrow-left"></i>
          Back to Home
        </button>

        <div class="header-content">
          <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank">
            <img src="@/assets/logo.png" alt="SuggestArr Logo" class="logo">
          </a>
          <h1 class="settings-title">Settings</h1>
          <p class="settings-subtitle">Manage your SuggestArr configuration</p>
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
          {{ tab.name }}
        </button>
      </div>

      <!-- Tab Content -->
      <div class="tab-content">
        <component
          :is="activeTabComponent"
          :config="config"
          :isLoading="isLoading"
          :testingConnections="testingConnections"
          @save-section="saveSection"
          @test-connection="testConnection"
        />
      </div>

      <!-- Save Button -->
      <div class="settings-footer">
        <div class="footer-spacer"></div>
        <button
          @click="exportConfig"
          class="btn btn-outline mr-2"
          :disabled="isLoading"
        >
          <i class="fas fa-download"></i>
          Export
        </button>
        <button
          @click="importConfig"
          class="btn btn-outline mr-2"
          :disabled="isLoading"
        >
          <i class="fas fa-upload"></i>
          Import
        </button>
        <button
          @click="resetConfig"
          class="btn btn-danger"
          :disabled="isLoading"
        >
          <i class="fas fa-trash"></i>
          Reset All
        </button>
      </div>

      <!-- Loading Overlay -->
      <div v-if="isLoading" class="loading-overlay">
        <div class="spinner"></div>
        <p>Saving configuration...</p>
      </div>

      <!-- Hidden file input for import -->
      <input
        type="file"
        ref="fileInput"
        @change="handleFileImport"
        accept=".json"
        style="display: none"
      />

      <!-- Reset Confirmation Modal -->
      <div v-if="showResetModal" class="modal-overlay">
        <div class="modal-content">
          <h3>Confirm Reset</h3>
          <p>Are you sure you want to reset all settings? This action cannot be undone.</p>
          <div class="modal-actions">
            <button @click="showResetModal = false" class="btn btn-secondary">Cancel</button>
            <button @click="confirmReset" class="btn btn-danger">Reset All Settings</button>
          </div>
        </div>
      </div>

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

export default {
  name: 'SettingsPage',
  components: {
    Footer,
    SettingsGeneral,
    SettingsServices,
    SettingsDatabase,
    SettingsContentFilters,
    SettingsAdvanced,
  },
  mixins: [backgroundManager],
  data() {
    return {
      config: {},
      isLoading: false,
      activeTab: 'general',
      showResetModal: false,
      backgroundImageUrl: '',
      testingConnections: {
        tmdb: false,
        plex: false,
        jellyfin: false,
        seer: false,
        database: false,
      },
      tabs: [
        { id: 'general', name: 'General', icon: 'fas fa-cog' },
        { id: 'services', name: 'Services', icon: 'fas fa-plug' },
        { id: 'database', name: 'Database', icon: 'fas fa-database' },
        { id: 'content_filters', name: 'Content Filters', icon: 'fas fa-filter' },
        { id: 'advanced', name: 'Advanced', icon: 'fas fa-sliders-h' },
      ],
    };
  },
  computed: {
    activeTabComponent() {
      const componentMap = {
        general: 'SettingsGeneral',
        services: 'SettingsServices',
        database: 'SettingsDatabase',
        content_filters: 'SettingsContentFilters',
        advanced: 'SettingsAdvanced',
      };
      return componentMap[this.activeTab];
    },
  },
  async mounted() {
    await this.loadConfig();
    this.startBackgroundImageRotation(
      this.config.TMDB_API_KEY ? fetchRandomMovieImage : null,
      this.config.TMDB_API_KEY
    );
  },
  methods: {
    async loadConfig() {
      try {
        const response = await axios.get('/api/config/fetch');
        this.config = response.data;
      } catch (error) {
        this.$toast.error('Failed to load configuration');
        console.error('Error loading config:', error);
      }
    },

    async saveSection({ section, data }) {
      this.isLoading = true;
      try {
        await axios.post(`/api/config/section/${section}`, data);

        // Update local config with saved data
        Object.assign(this.config, data);

        this.$toast.success(`${section} settings saved successfully!`);
      } catch (error) {
        this.$toast.error(`Failed to save ${section} settings: ${error.response?.data?.message || error.message}`);
        console.error('Error saving section:', error);
      } finally {
        this.isLoading = false;
      }
    },

    async testConnection(type, data) {
      try {
        // Set loading state
        this.testingConnections[type] = true;

        let endpoint;
        switch (type) {
          case 'tmdb':
            endpoint = '/api/tmdb/test';
            break;
          case 'jellyfin':
            endpoint = '/api/jellyfin/test';
            break;
          case 'plex':
            endpoint = '/api/plex/test';
            break;
          case 'seer':
            endpoint = '/api/seer/test';
            break;
          case 'database':
            endpoint = '/api/config/test-db-connection';
            break;
          default:
            throw new Error(`Unknown connection type: ${type}`);
        }

        const response = await axios.post(endpoint, data);
        if (response.data.status === 'success') {
          this.$toast.success(`${type} connection test successful!`);
        } else {
          this.$toast.error(`${type} connection test failed: ${response.data.message}`);
        }
        return response.data;
      } catch (error) {
        this.$toast.error(`${type} connection test failed: ${error.response?.data?.message || error.message}`);
        throw error;
      } finally {
        // Clear loading state
        this.testingConnections[type] = false;
      }
    },

    goToDashboard() {
      this.$router.push({ name: 'Home' });
    },

    async exportConfig() {
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

        this.$toast.success('Configuration exported successfully!');
      } catch (error) {
        this.$toast.error('Failed to export configuration');
        console.error('Error exporting config:', error);
      }
    },

    importConfig() {
      this.$refs.fileInput.click();
    },

    async handleFileImport(event) {
      const file = event.target.files[0];
      if (!file) return;

      try {
        const text = await file.text();
        const configData = JSON.parse(text);

        this.isLoading = true;
        await axios.post('/api/config/save', configData);
        await this.loadConfig();

        this.$toast.success('Configuration imported successfully!');
      } catch (error) {
        this.$toast.error('Failed to import configuration: Invalid file format');
        console.error('Error importing config:', error);
      } finally {
        this.isLoading = false;
        // Reset file input
        event.target.value = '';
      }
    },

    resetConfig() {
      this.showResetModal = true;
    },

    async confirmReset() {
      this.showResetModal = false;
      this.isLoading = true;

      try {
        await axios.post('/api/config/reset');
        this.$toast.success('Configuration reset successfully!');

        // Redirect to setup wizard
        this.$router.push({ name: 'Home' });
      } catch (error) {
        this.$toast.error('Failed to reset configuration');
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
  background-color: var(--color-bg-content);
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
  gap: 1rem;
}

.header-content {
  text-align: center;
}

.back-button {
  align-self: flex-start;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background-color: transparent;
  color: var(--color-text-muted);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  cursor: pointer;
  transition: var(--transition-base);
  font-size: 0.9rem;
  font-weight: 500;
}

.back-button:hover {
  background-color: var(--color-bg-interactive);
  color: var(--color-text-primary);
}

.logo {
  width: 80px;
  height: auto;
  margin-bottom: 1rem;
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
}

.tabs-navigation {
  display: flex;
  justify-content: center;
  margin-bottom: 2rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.tab-button {
  background-color: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  color: var(--color-text-muted);
  padding: 0.75rem 1.5rem;
  border-radius: var(--border-radius-sm);
  cursor: pointer;
  transition: var(--transition-base);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.tab-button:hover {
  background-color: var(--color-bg-active);
  color: var(--color-text-primary);
}

.tab-button.active {
  background-color: var(--color-primary);
  color: var(--color-text-primary);
  border-color: var(--color-primary);
}

.tab-content {
  flex: 1;
  background-color: var(--color-bg-content-secondary);
  border-radius: var(--border-radius-lg);
  padding: 2rem;
  backdrop-filter: blur(10px);
  border: 1px solid var(--color-border-light);
}

.settings-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid var(--color-border-light);
}

.footer-spacer {
  flex: 1;
}

.btn {
  padding: 0.75rem 1.5rem;
  border-radius: var(--border-radius-sm);
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition-base);
  border: none;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: #6b7280;
  color: var(--color-text-primary);
}

.btn-secondary:hover:not(:disabled) {
  background-color: #4b5563;
}

.btn-outline {
  background: var(--color-bg-interactive);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-medium);
}

.btn-outline:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.5);
}

.btn-danger {
  background-color: var(--color-danger);
  color: var(--color-text-primary);
}

.btn-danger:hover:not(:disabled) {
  background-color: #dc2626;
}

.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--color-bg-overlay-heavy);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--color-border-medium)m);
  border-top: 4px solid var(--color-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

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
}

.modal-content {
  background-color: var(--color-bg-content);
  backdrop-filter: blur(10px);
  padding: 2rem;
  border-radius: var(--border-radius-lg);
  border: 1px solid var(--color-border-light);
  max-width: 500px;
  width: 90%;
}

.modal-content h3 {
  color: var(--color-text-primary);
  margin-bottom: 1rem;
}

.modal-content p {
  color: var(--color-text-muted);
  margin-bottom: 2rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

.mr-2 {
  margin-right: 0.5rem;
}

@media (max-width: 768px) {
  .settings-content {
    padding: 1rem;
  }

  .back-button {
    padding: 0.5rem 0.75rem;
    font-size: 0.8rem;
  }

  .tabs-navigation {
    justify-content: flex-start;
    overflow-x: auto;
    padding-bottom: 0.5rem;
  }

  .tab-button {
    flex-shrink: 0;
    font-size: 0.8rem;
    padding: 0.5rem 1rem;
  }

  .tab-content {
    padding: 1rem;
  }

  .settings-footer {
    flex-direction: column;
    gap: 1rem;
    align-items: stretch;
  }

  .footer-spacer {
    display: none;
  }
}
</style>