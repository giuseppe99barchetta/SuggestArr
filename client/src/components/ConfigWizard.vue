<template>
  <button v-if="!showWelcome" @click="toggleLogs" class="floating-log-btn" 
          title="View Setup Logs">
    <i class="fas fa-clipboard-list"></i>
  </button>

  <div>
    <!-- Welcome Screen -->
    <div v-if="showWelcome" class="wizard-container" :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">
      <div class="wizard-content">
        <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank">
          <img src="@/assets/logo.png" alt="SuggestArr Logo" class="attached-logo mb-6">
        </a>

        <WizardWelcome
          :hasExistingConfig="hasExistingConfig"
          :isImporting="isImporting"
          @start-quick="startQuickSetup"
          @start-advanced="startAdvancedSetup"
          @import-config="importConfig"
        />

        <input 
          ref="fileInput" 
          type="file" 
          accept=".json,application/json"
          @change="handleFileImport"
          style="display: none;"
        />
      </div>
    </div>

    <!-- Setup Wizard -->
    <div v-else-if="currentStep <= steps.length" class="wizard-container"
      :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">
      <div class="wizard-content">
        <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank">
          <img src="@/assets/logo.png" alt="SuggestArr Logo" class="attached-logo mb-6">
        </a>

        <div class="progress-bar">
          <div class="progress" :style="{ width: progressBarWidth }"></div>
        </div>
        <p class="steps-count">
          {{ setupMode === 'quick' ? 'Quick Setup' : 'Advanced Setup' }} - Step {{ currentStep }} of {{ steps.length }}
        </p>

        <div class="wizard-step-container">
          <transition name="fade" mode="out-in">
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
    </div>

    <!-- Completion Screen -->
    <div v-else-if="currentStep === steps.length + 1" class="wizard-container" 
         :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">
      <div class="wizard-content">
        <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank">
          <img src="@/assets/logo.png" alt="SuggestArr Logo" class="attached-logo mb-6">
        </a>

        <WizardCompletion
          @go-settings="goToSettings"
          @go-requests="goToRequests"
        />

        <Footer />
      </div>
    </div>
  </div>

  <!-- Logs Modal -->
  <Transition name="modal">
    <div v-if="showLogs" class="modal-overlay" @click.self="toggleLogs">
      <div class="modal-container" @click.stop>
        <div class="modal-header">
          <div class="modal-header-left">
            <div class="modal-icon">
              <i class="fas fa-file-alt"></i>
            </div>
            <h2 class="modal-title">System Logs</h2>
          </div>
          
          <button @click="toggleLogs" class="btn-close" aria-label="Close modal">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="modal-body">
          <LogsComponent />
        </div>

        <div class="modal-footer">
          <button @click="toggleLogs" class="btn-modal-action">
            <i class="fas fa-times"></i>
            Close
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script>
import { ref, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import '@/assets/styles/wizard.css';

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
    const { backgroundImageUrl, startDefaultImageRotation, startBackgroundImageRotation, stopBackgroundImageRotation } = useBackgroundImage();

    // Computed
    const progressBarWidth = computed(() => `${(currentStep.value / steps.value.length) * 100}%`);
    
    const steps = computed(() => {
      const stepsByService = {
        quick: {
          jellyfin: ['MediaServiceSelection', 'TmdbConfig', 'JellyfinConfig', 'SeerConfig'],
          plex: ['MediaServiceSelection', 'TmdbConfig', 'PlexConfig', 'SeerConfig'],
          emby: ['MediaServiceSelection', 'TmdbConfig', 'JellyfinConfig', 'SeerConfig'],
        },
        advanced: {
          jellyfin: ['MediaServiceSelection', 'TmdbConfig', 'JellyfinConfig', 'SeerConfig', 'DbConfig', 'ContentFilterSettings', 'AdditionalSettings'],
          plex: ['MediaServiceSelection', 'TmdbConfig', 'PlexConfig', 'SeerConfig', 'DbConfig', 'ContentFilterSettings', 'AdditionalSettings'],
          emby: ['MediaServiceSelection', 'TmdbConfig', 'JellyfinConfig', 'SeerConfig', 'DbConfig', 'ContentFilterSettings', 'AdditionalSettings'],
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
      backgroundImageUrl,
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

<style scoped>
/* Floating Log Button */
.floating-log-btn {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  width: 56px;
  height: 56px;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: 50%;
  color: var(--color-text-primary);
  cursor: pointer;
  transition: var(--transition-base);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  box-shadow: var(--shadow-base);
  z-index: 1000;
  backdrop-filter: blur(10px);
}

.floating-log-btn:hover {
  background: var(--color-bg-active);
  transform: scale(1.1);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: var(--color-bg-overlay-heavy);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  padding: 1rem;
}

.modal-container {
  background: var(--color-bg-content);
  backdrop-filter: blur(20px);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-xl);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  max-width: 1200px;
  width: 100%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid var(--color-border-light);
  background: var(--color-bg-overlay-light);
}

.modal-header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.modal-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--border-radius-md);
  color: var(--color-text-secondary);
  font-size: 1.25rem;
}

.modal-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text-primary);
}

.btn-close {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-muted);
  font-size: 1.25rem;
  cursor: pointer;
  transition: var(--transition-base);
}

.btn-close:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: var(--color-danger);
  color: var(--color-danger);
  transform: rotate(90deg);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem;
}

.modal-body::-webkit-scrollbar {
  width: 10px;
}

.modal-body::-webkit-scrollbar-track {
  background: var(--color-bg-overlay-light);
}

.modal-body::-webkit-scrollbar-thumb {
  background: var(--color-primary);
  border-radius: var(--border-radius-sm);
}

.modal-body::-webkit-scrollbar-thumb:hover {
  background: var(--color-primary-hover);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.25rem 2rem;
  border-top: 1px solid var(--color-border-light);
  background: var(--color-bg-overlay-light);
}

.btn-modal-action {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-primary);
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition-base);
}

.btn-modal-action:hover {
  background: var(--color-bg-active);
  border-color: var(--color-primary);
}

/* Modal Transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.9) translateY(20px);
  opacity: 0;
}

/* Responsive */
@media (max-width: 768px) {
  .floating-log-btn {
    bottom: 1rem;
    right: 1rem;
    width: 48px;
    height: 48px;
    font-size: 1rem;
  }

  .modal-container {
    max-width: 100%;
    max-height: 95vh;
    border-radius: var(--border-radius-lg);
  }

  .modal-header,
  .modal-body,
  .modal-footer {
    padding: 1rem 1.25rem;
  }

  .modal-title {
    font-size: 1.25rem;
  }

  .modal-icon {
    width: 40px;
    height: 40px;
    font-size: 1rem;
  }
}
</style>