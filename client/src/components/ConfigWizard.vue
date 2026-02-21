<template>
  <div class="wizard-container">
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

    <button v-if="!showWelcome" @click="toggleLogs" class="floating-log-btn" 
            title="View Setup Logs">
      <i class="fas fa-clipboard-list"></i>
    </button>

    <div class="wizard-content">
      <!-- Welcome Screen -->
      <div v-if="showWelcome" class="wizard-screen">
        <div class="wizard-header">
          <div class="header-content">
            <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank" rel="noopener noreferrer">
              <img src="@/assets/logo.png" alt="SuggestArr Logo" class="logo">
            </a>
          </div>
        </div>

        <div class="wizard-body">
          <WizardWelcome
            :hasExistingConfig="hasExistingConfig"
            :isImporting="isImporting"
            @start-quick="startQuickSetup"
            @start-advanced="startAdvancedSetup"
            @import-config="importConfig"
          />
        </div>

        <input 
          ref="fileInput" 
          type="file" 
          accept=".json,application/json"
          @change="handleFileImport"
          style="display: none;"
        />

        <Footer />
      </div>

      <!-- Setup Wizard -->
      <div v-else-if="currentStep <= steps.length" class="wizard-screen">
        <div class="wizard-header">
          <div class="header-content">
            <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank" rel="noopener noreferrer">
              <img src="@/assets/logo.png" alt="SuggestArr Logo" class="logo">
            </a>
          </div>
        </div>

        <div class="progress-container">
          <div class="progress-bar">
            <div class="progress" :style="{ width: progressBarWidth }"></div>
          </div>
        </div>

        <div class="wizard-body">
          <transition name="fade-slide" mode="out-in">
            <component
              :is="currentStepComponent"
              :config="config"
              :isQuickSetup="setupMode === 'quick'"
              :isFirstStep="currentStep === 1"
              @next-step="handleStepChange(1)"
              @previous-step="handleStepChange(-1)"
              @update-config="updateConfig"
              @skip-step="skipStep"
            />
          </transition>
        </div>

        <Footer />
      </div>

      <!-- Completion Screen -->
      <div v-else-if="currentStep === steps.length + 1" class="wizard-screen">
        <div class="wizard-header">
          <div class="header-content">
            <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank" rel="noopener noreferrer">
              <img src="@/assets/logo.png" alt="SuggestArr Logo" class="logo">
            </a>
          </div>
        </div>

        <div class="wizard-body">
          <WizardCompletion
            @go-settings="goToSettings"
            @go-requests="goToRequests"
          />
        </div>

        <Footer />
      </div>
    </div>

    <!-- Logs Modal -->
    <transition name="fade">
      <div v-if="showLogs" class="modal-overlay" @click.self="toggleLogs">
        <div class="modal-content changelog-modal">
          <div class="modal-header">
            <div class="modal-header-left">
              <div class="modal-icon">
                <i class="fas fa-file-alt"></i>
              </div>
              <h3 class="modal-title">System Logs</h3>
            </div>
            
            <button @click="toggleLogs" class="btn-close" aria-label="Close modal">
              <i class="fas fa-times"></i>
            </button>
          </div>

          <div class="modal-body changelog-body">
            <LogsComponent />
          </div>

          <div class="modal-actions">
            <button @click="toggleLogs" class="btn btn-primary">
              <i class="fas fa-times"></i>
              Close
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import { ref, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import '@/assets/styles/dashboardPage.css';

import Footer from './AppFooter.vue';
import LogsComponent from './LogsComponent.vue';
import WizardWelcome from './wizard/WizardWelcome.vue';
import WizardCompletion from './wizard/WizardCompletion.vue';

import { useConfigManager } from '@/composables/useConfigManager';
import { useConfigImport } from '@/composables/useConfigImport';
import { useBackgroundImage } from '@/composables/useBackgroundImage';

// Wizard step components
import MediaServiceSelection from './configWizard/MediaServiceSelection.vue';
import TmdbConfig from './configWizard/TmdbConfig.vue';
import OmdbConfig from './configWizard/OmdbConfig.vue';
import JellyfinConfig from './configWizard/JellyfinConfig.vue';
import PlexConfig from './configWizard/PlexConfig.vue';
import SeerConfig from './configWizard/SeerConfig.vue';
import DbConfig from './configWizard/DbConfig.vue';
import ContentFilterSettings from './configWizard/ContentFilterSettings.vue';
import AdditionalSettings from './configWizard/AdditionalSettings.vue';

const QUICK_SETUP_DEFAULTS = {
  DB_TYPE: 'sqlite',
  MAX_SIMILAR_MOVIE: 5,
  MAX_SIMILAR_TV: 2,
  MAX_CONTENT_CHECKS: 10,
  SEARCH_SIZE: 20,
  CRON_TIMES: '0 0 * * *',
  EXCLUDE_DOWNLOADED: true,
  EXCLUDE_REQUESTED: true,
};

export default {
  name: 'ConfigWizard',
  components: {
    Footer,
    LogsComponent,
    WizardWelcome,
    WizardCompletion,
    MediaServiceSelection,
    TmdbConfig,
    OmdbConfig,
    JellyfinConfig,
    PlexConfig,
    SeerConfig,
    DbConfig,
    ContentFilterSettings,
    AdditionalSettings,
  },
  setup() {
    const router = useRouter();
    const toast = useToast();

    // State
    const showWelcome = ref(true);
    const showLogs = ref(false);
    const setupMode = ref('quick');
    const currentStep = ref(1);

    // Composables
    const { config, hasExistingConfig, fetchConfig, saveConfig: saveConfigFn, updateConfig } = useConfigManager();
    const { isImporting, fileInput, importConfig: importConfigFn, handleFileImport: handleFileImportFn } = useConfigImport(fetchConfig);
    const { currentBackgroundUrl, nextBackgroundUrl, isTransitioning, startDefaultImageRotation, startBackgroundImageRotation, stopBackgroundImageRotation } = useBackgroundImage();

    // Computed
    const progressBarWidth = computed(() => `${(currentStep.value / steps.value.length) * 100}%`);
    
    const steps = computed(() => {
      const stepsByService = {
        quick: {
          jellyfin: ['MediaServiceSelection', 'TmdbConfig', 'OmdbConfig', 'JellyfinConfig', 'SeerConfig'],
          plex: ['MediaServiceSelection', 'TmdbConfig', 'OmdbConfig', 'PlexConfig', 'SeerConfig'],
          emby: ['MediaServiceSelection', 'TmdbConfig', 'OmdbConfig', 'JellyfinConfig', 'SeerConfig'],
        },
        advanced: {
          jellyfin: ['MediaServiceSelection', 'TmdbConfig', 'OmdbConfig', 'JellyfinConfig', 'SeerConfig', 'DbConfig', 'ContentFilterSettings', 'AdditionalSettings'],
          plex: ['MediaServiceSelection', 'TmdbConfig', 'OmdbConfig', 'PlexConfig', 'SeerConfig', 'DbConfig', 'ContentFilterSettings', 'AdditionalSettings'],
          emby: ['MediaServiceSelection', 'TmdbConfig', 'OmdbConfig', 'JellyfinConfig', 'SeerConfig', 'DbConfig', 'ContentFilterSettings', 'AdditionalSettings'],
        }
      };

      const mode = stepsByService[setupMode.value];
      const service = config.value.SELECTED_SERVICE || 'jellyfin';
      return mode[service];
    });

    const currentStepComponent = computed(() => steps.value[currentStep.value - 1]);

    // Watchers
    watch(() => config.value.TMDB_API_KEY, (newApiKey) => {
      if (newApiKey) {
        // Clear any existing rotation and start TMDB rotation
        stopBackgroundImageRotation();
        startBackgroundImageRotation(newApiKey);
      }
    });

    watch(showLogs, (isOpen) => {
      document.body.style.overflow = isOpen ? 'hidden' : '';
    });

    // Methods
    async function saveConfig() {
      const result = await saveConfigFn(setupMode.value, QUICK_SETUP_DEFAULTS);
      
      if (result.success) {
        toast.success('Setup completed successfully!');
        currentStep.value = steps.value.length + 1;
      } else {
        toast.error('Error saving configuration. Please try again!');
      }
    }

    async function handleFileImport(event) {
      const result = await handleFileImportFn(event);
      
      if (result.success) {
        toast.success('Configuration imported successfully!');
        setTimeout(() => router.push('/'), 1500);
      } else {
        toast.error('Failed to import: Invalid file format');
      }
    }

    function startQuickSetup() {
      setupMode.value = 'quick';
      showWelcome.value = false;
      currentStep.value = 1;
    }

    function startAdvancedSetup() {
      setupMode.value = 'advanced';
      showWelcome.value = false;
      currentStep.value = 1;
    }

    function goToSettings() {
      router.push('/dashboard');
    }

    function goToRequests() {
      router.push('/requests');
    }

    function skipStep() {
      if (currentStep.value < steps.value.length) {
        currentStep.value++;
      }
    }

    function handleStepChange(stepChange) {
      if (stepChange < 0 && currentStep.value === 1) {
        showWelcome.value = true;
        return;
      }

      if (currentStep.value + stepChange > 0 && currentStep.value + stepChange <= steps.value.length) {
        currentStep.value += stepChange;
      } else if (currentStep.value + stepChange > steps.value.length) {
        saveConfig();
      }
    }

    function toggleLogs() {
      showLogs.value = !showLogs.value;
    }

    // Initialization
    fetchConfig().then(() => {
      if (!config.value.TMDB_API_KEY) {
        startDefaultImageRotation();
      }
      // TMDB rotation will start via the watcher when config is loaded
    });

return {
      showWelcome,
      showLogs,
      setupMode,
      currentStep,
      config,
      hasExistingConfig,
      isImporting,
      fileInput,
      currentBackgroundUrl,
      nextBackgroundUrl,
      isTransitioning,
      progressBarWidth,
      steps,
      currentStepComponent,
      importConfig: importConfigFn,
      handleFileImport,
      startQuickSetup,
      startAdvancedSetup,
      goToSettings,
      goToRequests,
      updateConfig,
      skipStep,
      handleStepChange,
      toggleLogs,
    };
  },
};
</script>