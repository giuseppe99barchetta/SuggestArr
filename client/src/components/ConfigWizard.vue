<template>
  <div class="wizard-container" :class="{ 'static-bg-active': config.ENABLE_STATIC_BACKGROUND }">
    <!-- Background layers -->
    <div
      v-if="!config.ENABLE_STATIC_BACKGROUND"
      class="background-layer current-bg"
      :style="{ backgroundImage: 'url(' + currentBackgroundUrl + ')' }"
      :class="{ 'fade-out': isTransitioning }"
    ></div>
    <div
      v-if="!config.ENABLE_STATIC_BACKGROUND"
      class="background-layer next-bg"
      :style="{ backgroundImage: 'url(' + nextBackgroundUrl + ')' }"
      :class="{ 'fade-in': isTransitioning }"
    ></div>
    <div
      v-if="config.ENABLE_STATIC_BACKGROUND"
      class="background-layer static-bg"
      :style="{ backgroundColor: config.STATIC_BACKGROUND_COLOR }"
    ></div>

    <!-- WELCOME SCREEN -->
    <div v-if="screen === 'welcome'" class="wizard-welcome-screen">
      <div class="welcome-card glass-card">
        <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank" rel="noopener noreferrer">
          <img src="@/assets/logo.png" alt="SuggestArr Logo" class="welcome-logo">
        </a>
        <h1>Welcome to SuggestArr!</h1>
        <p class="welcome-subtitle">
          Let's get you configured. This wizard guides you through the required steps.
          Optional items can be configured later from the dashboard.
        </p>

        <div class="welcome-actions">
          <button @click="startSetup" class="btn btn-primary btn-xl">
            <i class="fas fa-rocket"></i>
            Start Setup
          </button>
          <button @click="importConfig" class="btn btn-outline" :disabled="isImporting">
            <i :class="isImporting ? 'fas fa-spinner fa-spin' : 'fas fa-file-import'"></i>
            {{ isImporting ? 'Importing...' : 'Import Configuration' }}
          </button>
        </div>
        <p class="import-hint">Already have a configuration file? Import it to restore all settings.</p>

        <div v-if="hasExistingConfig" class="existing-config-notice">
          <i class="fas fa-info-circle"></i>
          Existing configuration detected.
          <router-link to="/" class="go-dashboard-link">Go to Dashboard →</router-link>
        </div>
      </div>
      <Footer />
    </div>

    <!-- WIZARD LAYOUT: centered compact card with top stepper -->
    <div v-else-if="screen === 'wizard'" class="wizard-centered-screen">
      <div class="wizard-card">

        <!-- Card header: logo + step count + logs -->
        <div class="wizard-card-header">
          <img src="@/assets/logo.png" alt="SuggestArr" class="wizard-logo-small">
          <div class="wizard-header-right">
            <span v-if="!currentStep.optional" class="wizard-step-count">
              Step {{ currentRequiredIndex + 1 }} of {{ requiredSteps.length }}
            </span>
            <span v-else class="wizard-step-count is-optional">
              Optional {{ currentOptionalIndex + 1 }} of {{ optionalSteps.length }}
            </span>
            <button @click="showLogs = true" class="btn-icon" title="View Logs">
              <i class="fas fa-clipboard-list"></i>
            </button>
          </div>
        </div>

        <!-- Horizontal stepper -->
        <div class="wizard-stepper">
          <template v-for="(step, i) in allSteps" :key="step.id">
            <div
              class="stepper-step"
              :class="{
                'is-completed': i < currentStepIndex,
                'is-current': i === currentStepIndex,
                'is-optional': step.optional,
              }"
            >
              <div class="stepper-circle">
                <i v-if="i < currentStepIndex" class="fas fa-check"></i>
                <span v-else>{{ i + 1 }}</span>
              </div>
            </div>
            <div
              v-if="i < allSteps.length - 1"
              class="stepper-connector"
              :class="{ 'is-done': i < currentStepIndex }"
            ></div>
          </template>
        </div>

        <!-- Step title & description -->
        <div class="wizard-step-header">
          <div class="step-title-row">
            <h2>{{ currentStep.label }}</h2>
            <div v-if="currentStep.optional" class="step-badge">Optional</div>
          </div>
          <p>{{ currentStep.description }}</p>
        </div>

        <!-- Step component (scrollable body) -->
        <div class="wizard-card-body">
          <transition name="fade-slide" mode="out-in">
            <div :key="currentStep.id">
              <component
                :is="currentStep.component"
                :config="config"
                :wizard-mode="true"
                :wizard-section="currentStep.wizardSection || null"
                :testing-connections="{}"
                :is-loading="false"
                @update-config="handleUpdateConfig"
                @validation-changed="handleValidationChanged"
                @config-changed="handleConfigChanged"
              />
              <!-- When on the service step, show the media server config inline once a service is selected -->
              <template v-if="currentStep.id === 'service' && config.SELECTED_SERVICE">
                <div class="step-section-divider">
                  <span>{{ config.SELECTED_SERVICE.charAt(0).toUpperCase() + config.SELECTED_SERVICE.slice(1) }} Configuration</span>
                </div>
                <SettingsServices
                  :key="'media-server-' + config.SELECTED_SERVICE"
                  :config="config"
                  :wizard-mode="true"
                  wizard-section="media-server"
                  :testing-connections="{}"
                  :is-loading="false"
                  @update-config="handleUpdateConfig"
                  @validation-changed="handleMediaServerValidation"
                  @config-changed="handleConfigChanged"
                />
              </template>
            </div>
          </transition>
        </div>

        <!-- Inline hint: explains why Continue is disabled -->
        <transition name="fade">
          <div
            v-if="!isCurrentStepValid && !currentStep.optional && currentStepHint"
            class="wizard-step-hint"
          >
            <i class="fas fa-info-circle"></i>
            {{ currentStepHint }}
          </div>
        </transition>

        <!-- Navigation footer -->
        <div class="wizard-card-footer">
          <button @click="goBack" class="btn btn-outline">
            <i class="fas fa-arrow-left"></i>
            {{ currentStepIndex === 0 ? 'Welcome' : 'Back' }}
          </button>
          <div class="footer-right">
            <button
              v-if="currentStep.optional"
              @click="skipStep"
              class="btn btn-outline"
            >
              Skip <i class="fas fa-forward"></i>
            </button>
            <button
              @click="goNext"
              class="btn btn-primary"
              :disabled="!isCurrentStepValid && !isSaving"
            >
              <i v-if="isSaving" class="fas fa-spinner fa-spin"></i>
              <template v-else>
                {{ isLastStep ? 'Complete Setup' : 'Continue' }}
                <i v-if="!isLastStep" class="fas fa-arrow-right"></i>
                <i v-else class="fas fa-check"></i>
              </template>
            </button>
          </div>
        </div>

      </div>
    </div>

    <!-- COMPLETION SCREEN -->
    <div v-else-if="screen === 'complete'" class="wizard-welcome-screen">
      <WizardCompletion
        @go-settings="goToSettings"
        @go-requests="goToRequests"
      />
      <Footer />
    </div>

    <!-- LOGS MODAL -->
    <transition name="fade">
      <div v-if="showLogs" class="modal-overlay" @click.self="showLogs = false">
        <div class="modal-content changelog-modal">
          <div class="modal-header">
            <div class="modal-header-left">
              <div class="modal-icon"><i class="fas fa-file-alt"></i></div>
              <h3 class="modal-title">System Logs</h3>
            </div>
            <button @click="showLogs = false" class="btn-close" aria-label="Close">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="modal-body changelog-body">
            <LogsComponent />
          </div>
          <div class="modal-actions">
            <button @click="showLogs = false" class="btn btn-primary">
              <i class="fas fa-times"></i> Close
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Hidden file input for config import -->
    <input
      ref="fileInput"
      type="file"
      accept=".json,application/json"
      @change="handleFileImport"
      style="display: none;"
    />
  </div>
</template>

<script>
import { ref, computed, watch } from 'vue';
import axios from 'axios';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import '@/assets/styles/dashboardPage.css';

import Footer from './AppFooter.vue';
import LogsComponent from './LogsComponent.vue';
import WizardCompletion from './wizard/WizardCompletion.vue';

import { useConfigManager } from '@/composables/useConfigManager';
import { useConfigImport } from '@/composables/useConfigImport';
import { useBackgroundImage } from '@/composables/useBackgroundImage';

// Shared step components (used in both wizard and dashboard)
import MediaServiceSelection from './configWizard/MediaServiceSelection.vue';
import ContentFilterSettings from './configWizard/ContentFilterSettings.vue';
import SchedulingStep from './configWizard/SchedulingStep.vue';
import SettingsServices from './settings/SettingsServices.vue';
import SettingsDatabase from './settings/SettingsDatabase.vue';

const SETUP_DEFAULTS = {
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
    WizardCompletion,
    MediaServiceSelection,
    ContentFilterSettings,
    SchedulingStep,
    SettingsServices,
    SettingsDatabase,
  },
  setup() {
    const router = useRouter();
    const toast = useToast();

    const screen = ref('welcome'); // 'welcome' | 'wizard' | 'complete'
    const showLogs = ref(false);
    const isSaving = ref(false);
    const currentStepIndex = ref(0);

    // Per-step validity (keyed by step id)
    const stepValidity = ref({
      service: false,
      tmdb: false,
      'media-server': false,
      seer: false,
      scheduling: true, // always valid — default 'daily' is pre-selected
      omdb: true,       // optional — always passable
      database: true,   // optional — SQLite is default
      filters: true,    // optional — no blocking errors by default
    });

    // Config management
    const { config, hasExistingConfig, fetchConfig, saveConfig: saveConfigFn } = useConfigManager();
    const { isImporting, fileInput, importConfig: importConfigFn, handleFileImport: handleFileImportFn } = useConfigImport(fetchConfig);
    const { currentBackgroundUrl, nextBackgroundUrl, isTransitioning, startDefaultImageRotation, startBackgroundImageRotation, stopBackgroundImageRotation } = useBackgroundImage();

    // ─── Step Definitions ────────────────────────────────────────────────────
    const allSteps = computed(() => {
      return [
        {
          id: 'service',
          label: 'Media Service',
          description: 'Choose your media platform and configure its connection, libraries, and users.',
          component: MediaServiceSelection,
          optional: false,
        },
        {
          id: 'tmdb',
          label: 'TMDB',
          description: 'Connect to The Movie Database API to power recommendations.',
          component: SettingsServices,
          wizardSection: 'tmdb',
          optional: false,
        },
        {
          id: 'seer',
          label: 'Overseerr / Jellyseerr',
          description: 'Connect your media request manager to submit suggestions.',
          component: SettingsServices,
          wizardSection: 'seer',
          optional: false,
        },
        {
          id: 'scheduling',
          label: 'Schedule',
          description: 'Set how often SuggestArr automatically finds and requests content for you.',
          component: SchedulingStep,
          optional: false,
        },
        {
          id: 'omdb',
          label: 'OMDb (IMDB Ratings)',
          description: 'Filter recommendations by IMDB ratings via the OMDb API.',
          component: SettingsServices,
          wizardSection: 'omdb',
          optional: true,
        },
        {
          id: 'database',
          label: 'Database',
          description: 'Use PostgreSQL or MySQL instead of the default SQLite.',
          component: SettingsDatabase,
          optional: true,
        },
        {
          id: 'filters',
          label: 'Content Filters',
          description: 'Fine-tune which genres, ratings, and regions get recommended.',
          component: ContentFilterSettings,
          optional: true,
        },
      ];
    });

    const requiredSteps = computed(() => allSteps.value.filter(s => !s.optional));
    const optionalSteps = computed(() => allSteps.value.filter(s => s.optional));
    const currentStep = computed(() => allSteps.value[currentStepIndex.value] || allSteps.value[0]);
    const isLastStep = computed(() => currentStepIndex.value === allSteps.value.length - 1);

    // Step counter: separate required vs optional numbering
    const currentRequiredIndex = computed(() =>
      requiredSteps.value.findIndex(s => s.id === currentStep.value.id)
    );
    const currentOptionalIndex = computed(() =>
      optionalSteps.value.findIndex(s => s.id === currentStep.value.id)
    );

    const currentStepHint = computed(() => {
      const step = currentStep.value;
      if (step.id === 'service') {
        if (!config.value.SELECTED_SERVICE) return 'Select a media service above to continue.';
        if (!stepValidity.value['media-server']) return 'Connect your media server to continue.';
      }
      if (step.id === 'tmdb') return 'Test your TMDB connection above to continue.';
      if (step.id === 'seer') return 'Test your Jellyseerr / Overseerr connection above to continue.';
      return '';
    });

    const isCurrentStepValid = computed(() => {
      const step = currentStep.value;
      if (step.optional) return true;
      if (step.id === 'service') {
        return !!(config.value.SELECTED_SERVICE && stepValidity.value['media-server']);
      }
      return !!stepValidity.value[step.id];
    });

    // ─── Watchers ────────────────────────────────────────────────────────────
    watch(() => config.value.TMDB_API_KEY, (newKey) => {
      if (!config.value.ENABLE_STATIC_BACKGROUND && newKey) {
        stopBackgroundImageRotation();
        startBackgroundImageRotation(newKey);
      }
    });

    watch(() => config.value.ENABLE_STATIC_BACKGROUND, (enabled) => {
      if (enabled) {
        stopBackgroundImageRotation();
      } else if (config.value.TMDB_API_KEY) {
        startBackgroundImageRotation(config.value.TMDB_API_KEY);
      } else {
        startDefaultImageRotation();
      }
    });

    watch(() => config.value.SELECTED_SERVICE, (svc, oldSvc) => {
      if (svc !== oldSvc) {
        // Reset media-server validity whenever the service changes
        stepValidity.value['media-server'] = false;
      }
    });

    watch(showLogs, (open) => {
      document.body.style.overflow = open ? 'hidden' : '';
    });

    // ─── Methods ─────────────────────────────────────────────────────────────
    function startSetup() {
      screen.value = 'wizard';
      currentStepIndex.value = 0;
    }

    function goBack() {
      if (currentStepIndex.value === 0) {
        screen.value = 'welcome';
      } else {
        currentStepIndex.value--;
      }
    }

    async function goNext() {
      if (isLastStep.value) {
        await saveSetup();
      } else {
        currentStepIndex.value++;
      }
    }

    function skipStep() {
      if (isLastStep.value) {
        saveSetup();
      } else {
        currentStepIndex.value++;
      }
    }

    async function saveSetup() {
      isSaving.value = true;
      try {
        // Extract wizard-only keys before saving to server
        const wizardSchedule = config.value.WIZARD_SCHEDULE || 'daily';
        delete config.value.WIZARD_SCHEDULE;

        // Mirror the chosen schedule into CRON_TIMES so that system_job_sync
        // creates a job with the correct schedule on the next backend restart
        // (serves as a reliable fallback if the API call below fails)
        config.value.CRON_TIMES = wizardSchedule;

        const result = await saveConfigFn(null, SETUP_DEFAULTS);
        if (result.success) {
          await createDefaultJob(wizardSchedule);
          toast.success('Setup completed successfully!');
          screen.value = 'complete';
        } else {
          toast.error('Error saving configuration. Please try again.');
        }
      } finally {
        isSaving.value = false;
      }
    }

    async function createDefaultJob(scheduleValue) {
      try {
        const res = await axios.post('/api/jobs', {
          name: 'Automatic Recommendations',
          job_type: 'recommendation',
          media_type: 'both',
          filters: {},
          schedule_type: 'preset',
          schedule_value: scheduleValue,
          enabled: true,
        });
        if (res.data?.status !== 'success') {
          throw new Error(res.data?.message || 'Unknown error');
        }
      } catch (e) {
        const msg = e.response?.data?.message || e.message || 'Unknown error';
        console.error('Could not create default job:', msg, e);
        toast.warning(`Setup complete, but the default job could not be created: ${msg}. You can add it manually from Settings → Jobs.`);
      }
    }

    function handleUpdateConfig(key, value) {
      config.value[key] = value;
      if (key === 'SELECTED_SERVICE' && value) {
        stepValidity.value.service = true;
      }
    }

    function handleConfigChanged(partialConfig) {
      // SELECTED_SERVICE is owned by MediaServiceSelection — never let a child snapshot override it
      const copy = { ...partialConfig };
      delete copy.SELECTED_SERVICE;
      Object.assign(config.value, copy);
    }

    function handleValidationChanged(isValid) {
      const stepId = currentStep.value?.id;
      if (stepId) {
        stepValidity.value[stepId] = isValid;
      }
    }

    function handleMediaServerValidation(isValid) {
      stepValidity.value['media-server'] = isValid;
    }

    // Auto-validate steps when credentials are already present in config
    // (used after import or when re-entering the wizard with an existing config)
    function preValidateFromConfig() {
      const cfg = config.value;
      if (cfg.TMDB_API_KEY) stepValidity.value.tmdb = true;
      if (cfg.SEER_API_URL && cfg.SEER_TOKEN) stepValidity.value.seer = true;
      const svc = cfg.SELECTED_SERVICE;
      if (svc) {
        if (svc === 'plex' && cfg.PLEX_TOKEN && cfg.PLEX_API_URL) {
          stepValidity.value['media-server'] = true;
        } else if ((svc === 'jellyfin' || svc === 'emby') && cfg.JELLYFIN_API_URL && cfg.JELLYFIN_TOKEN) {
          stepValidity.value['media-server'] = true;
        } else if (svc === 'trakt' && cfg.TRAKT_ACCESS_TOKEN) {
          stepValidity.value['media-server'] = true;
        }
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

    function goToSettings() { router.push('/dashboard?tour=1'); }
    function goToRequests() { router.push('/dashboard?tour=1'); }

    // ─── Step Class Helpers ───────────────────────────────────────────────────
    function getStepItemClass(absoluteIndex) {
      const isCompleted = absoluteIndex < currentStepIndex.value;
      const isCurrent = absoluteIndex === currentStepIndex.value;
      return {
        'is-completed': isCompleted,
        'is-current': isCurrent,
        'is-pending': !isCompleted && !isCurrent,
      };
    }

    function isRequiredStepDone(requiredIndex) {
      // A required step is "done" if its validity is true AND we're past it
      const step = requiredSteps.value[requiredIndex];
      return requiredIndex < currentStepIndex.value && stepValidity.value[step.id];
    }

    function isOptionalStepDone(optionalIndex) {
      const absoluteIndex = requiredSteps.value.length + optionalIndex;
      return absoluteIndex < currentStepIndex.value;
    }

    function isOptionalStepSkipped() {
      return false; // simplified
    }

    // ─── Initialization ───────────────────────────────────────────────────────
    fetchConfig().then(() => {
      if (!config.value.ENABLE_STATIC_BACKGROUND && !config.value.TMDB_API_KEY) {
        startDefaultImageRotation();
      }
      preValidateFromConfig();
    });

    return {
      screen,
      showLogs,
      isSaving,
      currentStepIndex,
      config,
      hasExistingConfig,
      isImporting,
      fileInput,
      currentBackgroundUrl,
      nextBackgroundUrl,
      isTransitioning,
      allSteps,
      requiredSteps,
      optionalSteps,
      currentStep,
      isLastStep,
      isCurrentStepValid,
      currentStepHint,
      currentRequiredIndex,
      currentOptionalIndex,
      stepValidity,
      importConfig: importConfigFn,
      handleFileImport,
      handleUpdateConfig,
      handleConfigChanged,
      handleValidationChanged,
      handleMediaServerValidation,
      startSetup,
      goBack,
      goNext,
      skipStep,
      goToSettings,
      goToRequests,
      getStepItemClass,
      isRequiredStepDone,
      isOptionalStepDone,
      isOptionalStepSkipped,
    };
  },
};
</script>

<style scoped>
/* ── Welcome Screen ───────────────────────────────────────────────────────── */
.wizard-welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem;
  position: relative;
  z-index: 10;
  background: rgba(5, 10, 18, 0.45);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.welcome-card {
  max-width: 520px;
  width: 100%;
  text-align: center;
  padding: 3rem 2.5rem;
  border-radius: 20px;
  background: rgba(15, 20, 30, 0.75);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
}

.welcome-logo {
  height: 64px;
  margin-bottom: 1.75rem;
  display: inherit !important;
}

.welcome-card h1 {
  color: var(--color-text-primary);
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.75rem;
}

.welcome-subtitle {
  color: var(--color-text-muted);
  font-size: 1rem;
  line-height: 1.6;
  margin-bottom: 2rem;
}

.welcome-actions {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
  margin-bottom: 0.75rem;
}

.btn-xl {
  padding: 0.875rem 1.75rem;
  font-size: 1.05rem;
  font-weight: 600;
}

.import-hint {
  color: var(--color-text-muted);
  font-size: 0.8rem;
  margin-bottom: 1.5rem;
}

.existing-config-notice {
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 10px;
  padding: 0.875rem 1.25rem;
  color: #e5e7eb;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  justify-content: center;
  flex-wrap: wrap;
}

.go-dashboard-link {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 600;
}

.go-dashboard-link:hover {
  text-decoration: underline;
}

/* ── Wizard Centered Layout ───────────────────────────────────────────────── */
.wizard-centered-screen {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem 1rem;
  position: relative;
  z-index: 10;
  background: rgba(5, 10, 18, 0.45);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.wizard-card {
  width: 100%;
  max-width: 700px;
  max-height: calc(100vh - 4rem);
  display: flex;
  flex-direction: column;
  background: rgba(15, 20, 30, 0.82);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  box-shadow: 0 32px 80px rgba(0, 0, 0, 0.55);
  overflow: hidden;
}

/* Card header */
.wizard-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.1rem 1.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  flex-shrink: 0;
}

.wizard-logo-small {
  height: 26px;
}

.wizard-header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.wizard-step-count {
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.btn-icon {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  color: var(--color-text-muted);
  padding: 0.35rem 0.6rem;
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.2s;
}

.btn-icon:hover {
  background: rgba(255, 255, 255, 0.07);
  color: var(--color-text-primary);
  border-color: rgba(255, 255, 255, 0.22);
}

/* ── Horizontal Stepper ───────────────────────────────────────────────────── */
.wizard-stepper {
  display: flex;
  align-items: center;
  padding: 1rem 1.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  flex-shrink: 0;
}

.stepper-step {
  flex-shrink: 0;
}

.stepper-circle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.06);
  border: 1.5px solid rgba(255, 255, 255, 0.15);
  color: var(--color-text-muted);
  transition: all 0.25s ease;
}

.stepper-step.is-current .stepper-circle {
  background: var(--color-primary);
  border-color: transparent;
  color: white;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.22);
}

.stepper-step.is-current.is-optional .stepper-circle {
  background: #f59e0b;
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.22);
}

.stepper-step.is-completed .stepper-circle {
  background: rgba(16, 185, 129, 0.18);
  border-color: rgba(16, 185, 129, 0.4);
  color: #10b981;
}

.stepper-connector {
  flex: 1;
  height: 2px;
  background: rgba(255, 255, 255, 0.1);
  margin: 0 3px;
  transition: background 0.3s ease;
}

.stepper-connector.is-done {
  background: rgba(16, 185, 129, 0.4);
}

/* ── Step header ──────────────────────────────────────────────────────────── */
.wizard-step-header {
  padding: 1.25rem 1.75rem 0.5rem;
  flex-shrink: 0;
}

.step-title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.3rem;
}

.wizard-step-header h2 {
  color: var(--color-text-primary);
  font-size: 1.3rem;
  font-weight: 700;
  margin: 0;
}

.wizard-step-header p {
  color: var(--color-text-muted);
  font-size: 0.9rem;
  line-height: 1.5;
  margin: 0;
}

.step-badge {
  display: inline-block;
  background: rgba(245, 158, 11, 0.15);
  border: 1px solid rgba(245, 158, 11, 0.35);
  color: #f59e0b;
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 0.18rem 0.55rem;
  border-radius: 20px;
  flex-shrink: 0;
}

/* ── Step section divider (inside combined steps) ────────────────────────── */
.step-section-divider {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 1.5rem 0 1rem;
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

.step-section-divider::before,
.step-section-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
}

/* ── Scrollable card body ─────────────────────────────────────────────────── */
.wizard-card-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: 1.25rem 1.75rem;
}

.wizard-card-body::-webkit-scrollbar { width: 4px; }
.wizard-card-body::-webkit-scrollbar-track { background: transparent; }
.wizard-card-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 2px;
}

/* ── Step hint (why Continue is disabled) ─────────────────────────────────── */
.wizard-step-hint {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1.75rem;
  font-size: 0.82rem;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.08);
  border-top: 1px solid rgba(245, 158, 11, 0.18);
  flex-shrink: 0;
}

.wizard-step-hint i {
  flex-shrink: 0;
  font-size: 0.8rem;
}

/* Optional step counter accent */
.wizard-step-count.is-optional {
  color: #f59e0b;
}

/* ── Card navigation footer ───────────────────────────────────────────────── */
.wizard-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(0, 0, 0, 0.15);
  flex-shrink: 0;
}

.footer-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* ── Shared button styles (supplement dashboardPage.css) ─────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 1.25rem;
  border-radius: 10px;
  font-weight: 500;
  font-size: 0.925rem;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
  text-decoration: none;
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover, #2563eb);
  transform: translateY(-1px);
}

.btn-outline {
  background: rgba(255, 255, 255, 0.05);
  color: var(--color-text-primary);
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.btn-outline:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.3);
}

/* ── Spinner ──────────────────────────────────────────────────────────────── */
.fa-spinner.fa-spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* ── Fade-slide transition for step changes ───────────────────────────────── */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* ── Responsive (mobile) ─────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .wizard-centered-screen {
    padding: 1rem 0.75rem;
    align-items: flex-start;
  }

  .wizard-card {
    max-height: none;
    border-radius: 16px;
  }

  .wizard-card-header {
    padding: 1rem 1.25rem;
  }

  .wizard-stepper {
    padding: 0.875rem 1.25rem;
  }

  .stepper-circle {
    width: 24px;
    height: 24px;
    font-size: 0.65rem;
  }

  .wizard-step-header {
    padding: 1rem 1.25rem 0.5rem;
  }

  .wizard-card-body {
    padding: 1rem 1.25rem;
  }

  .wizard-card-footer {
    padding: 0.875rem 1.25rem;
  }

  .welcome-card {
    padding: 2rem 1.5rem;
  }
}
</style>
