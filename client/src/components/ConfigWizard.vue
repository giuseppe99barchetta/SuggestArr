<template>
  <!-- The setup screens sit on dark imagery, so they keep the dark palette in either theme. -->
  <div class="theme-dark relative min-h-screen">
    <!-- Background layers -->
    <div class="fixed inset-0 z-0">
      <template v-if="!config.ENABLE_STATIC_BACKGROUND">
          <div
            class="absolute inset-0 bg-cover bg-fixed bg-center transition-opacity duration-1000 will-change-[opacity]"
            :class="activeBg === 'bg1' ? 'opacity-100' : 'opacity-0'"
            :style="{ backgroundImage: 'url(' + bg1Url + ')' }"
          ></div>
          <div
            class="absolute inset-0 bg-cover bg-fixed bg-center transition-opacity duration-1000 will-change-[opacity]"
            :class="activeBg === 'bg2' ? 'opacity-100' : 'opacity-0'"
            :style="{ backgroundImage: 'url(' + bg2Url + ')' }"
          ></div>
      </template>
      <div
        v-if="config.ENABLE_STATIC_BACKGROUND"
        class="absolute inset-0"
        :style="{ backgroundColor: config.STATIC_BACKGROUND_COLOR }"
      ></div>
    </div>

    <!-- WELCOME SCREEN -->
    <div v-if="screen === 'welcome'" :class="screenClass">
      <div class="w-full max-w-[520px] rounded-[20px] border border-white/12 bg-[rgba(15,20,30,0.75)] px-6 py-8 text-center shadow-[0_24px_64px_rgba(0,0,0,0.5)] backdrop-blur-xl md:px-10 md:py-12">
        <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank" rel="noopener noreferrer">
          <img src="@/assets/logo.png" alt="SuggestArr Logo" class="mx-auto mb-7 h-16">
        </a>
        <h1 class="mb-3 text-[2rem] font-bold text-ink">Welcome to SuggestArr!</h1>
        <p class="mb-8 text-base leading-relaxed text-ink-4">
          Let's get you configured. This wizard guides you through the required steps.
          Optional items can be configured later from the dashboard.
        </p>

        <div class="mb-3 flex flex-col gap-3.5">
          <button type="button" @click="startSetup" class="ui-btn-primary h-auto py-3.5 text-[1.05rem] font-semibold">
            <i aria-hidden="true" class="fas fa-rocket"></i>
            Start Setup
          </button>
          <button type="button" @click="importConfig" class="ui-btn" :disabled="isImporting">
            <i aria-hidden="true" :class="isImporting ? 'fas fa-spinner fa-spin' : 'fas fa-file-import'"></i>
            {{ isImporting ? 'Importing...' : 'Import Configuration' }}
          </button>
        </div>
        <p class="mb-6 text-[0.8rem] text-ink-4">Already have a configuration file? Import it to restore all settings.</p>

        <div v-if="hasExistingConfig" class="flex flex-wrap items-center justify-center gap-2 rounded-ctl border border-notice/30 bg-notice/12 px-5 py-3.5 text-[0.9rem] text-ink">
          <i aria-hidden="true" class="fas fa-info-circle"></i>
          Existing configuration detected.
          <router-link to="/" class="font-semibold text-brand-ink no-underline hover:underline">Go to Dashboard →</router-link>
        </div>
      </div>
      <AppFooter />
    </div>

    <!-- WIZARD LAYOUT: centered compact card with top stepper -->
    <div v-else-if="screen === 'wizard'" :class="[screenClass, 'max-md:justify-start max-md:px-3 max-md:py-4']">
      <div class="flex w-full max-w-[700px] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[rgba(15,20,30,0.82)] shadow-[0_32px_80px_rgba(0,0,0,0.55)] backdrop-blur-2xl md:max-h-[calc(100vh-4rem)] md:rounded-[20px]">

        <!-- Card header: logo + step count + logs -->
        <div :class="[sectionClass, 'flex items-center justify-between border-b border-white/7 py-4']">
          <img src="@/assets/logo.png" alt="SuggestArr" class="h-[26px]">
          <div class="flex items-center gap-3">
            <span v-if="!currentStep.optional" class="text-[0.8rem] text-ink-4">
              Step {{ currentRequiredIndex + 1 }} of {{ requiredSteps.length }}
            </span>
            <span v-else class="text-[0.8rem] text-caution">
              Optional {{ currentOptionalIndex + 1 }} of {{ optionalSteps.length }}
            </span>
            <button type="button" @click="showLogs = true" class="cursor-pointer rounded-lg border border-white/12 bg-transparent px-2.5 py-1.5 text-[0.8rem] text-ink-4 transition hover:border-white/22 hover:bg-white/7 hover:text-ink" title="View Logs" aria-label="View Logs">
              <i aria-hidden="true" class="fas fa-clipboard-list"></i>
            </button>
          </div>
        </div>

        <!-- Horizontal stepper -->
        <div :class="[sectionClass, 'flex items-center border-b border-white/7 py-3.5 md:py-4']">
          <template v-for="(step, i) in allSteps" :key="step.id">
            <div
              class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-[1.5px] text-[0.65rem] font-bold transition md:h-7 md:w-7 md:text-[0.72rem]"
              :title="step.optional ? `${step.label} (optional)` : step.label"
              :class="[stepCircleClass(step, i), { 'scale-80 border-dashed': step.optional }]"
            >
              <i aria-hidden="true" v-if="i < currentStepIndex" class="fas fa-check"></i>
              <!-- Only required steps are numbered, matching "Step N of M" in the header. -->
              <span v-else-if="!step.optional">{{ requiredSteps.indexOf(step) + 1 }}</span>
            </div>
            <div
              v-if="i < allSteps.length - 1"
              class="mx-[3px] h-0.5 flex-1 transition-colors duration-300"
              :class="i < currentStepIndex ? 'bg-good/40' : 'bg-white/10'"
            ></div>
          </template>
        </div>

        <!-- Step title & description -->
        <div :class="[sectionClass, 'pt-4 pb-2 md:pt-5']">
          <div class="mb-1 flex items-center gap-3">
            <h2 class="m-0 text-[1.3rem] font-bold text-ink">{{ currentStep.label }}</h2>
            <div v-if="currentStep.optional" class="shrink-0 rounded-full border border-caution/35 bg-caution/15 px-2 py-0.5 text-[0.68rem] font-bold uppercase tracking-[0.08em] text-caution">Optional</div>
          </div>
          <p class="m-0 text-[0.9rem] leading-normal text-ink-4">{{ currentStep.description }}</p>
        </div>

        <!-- Step component (scrollable body) -->
        <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4 md:px-7 md:py-5">
          <transition
            mode="out-in"
            enter-active-class="transition duration-200"
            leave-active-class="transition duration-200"
            enter-from-class="translate-x-5 opacity-0"
            leave-to-class="-translate-x-5 opacity-0"
          >
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
                <div class="mt-6 mb-4 flex items-center gap-3 text-[0.78rem] font-semibold uppercase tracking-[0.07em] text-ink-4 before:h-px before:flex-1 before:bg-white/8 after:h-px after:flex-1 after:bg-white/8">
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
        <transition enter-active-class="transition-opacity duration-300" leave-active-class="transition-opacity duration-300" enter-from-class="opacity-0" leave-to-class="opacity-0">
          <div
            v-if="!isCurrentStepValid && !currentStep.optional && currentStepHint"
            :class="[sectionClass, 'flex items-center gap-2 border-t border-caution/18 bg-caution/8 py-2.5 text-[0.82rem] text-caution']"
          >
            <i aria-hidden="true" class="fas fa-info-circle shrink-0 text-[0.8rem]"></i>
            {{ currentStepHint }}
          </div>
        </transition>

        <!-- Navigation footer -->
        <div :class="[sectionClass, 'flex items-center justify-between border-t border-white/7 bg-black/15 py-3.5 md:py-4']">
          <button type="button" @click="goBack" class="ui-btn">
            <i aria-hidden="true" class="fas fa-arrow-left"></i>
            {{ currentStepIndex === 0 ? 'Welcome' : 'Back' }}
          </button>
          <div class="flex items-center gap-3">
            <button
              v-if="currentStep.optional"
              type="button"
              @click="skipStep"
              class="ui-btn"
            >
              Skip <i aria-hidden="true" class="fas fa-forward"></i>
            </button>
            <button
              type="button"
              @click="goNext"
              class="ui-btn-primary"
              :disabled="!isCurrentStepValid && !isSaving"
            >
              <i aria-hidden="true" v-if="isSaving" class="fas fa-spinner fa-spin"></i>
              <template v-else>
                {{ isLastStep ? 'Complete Setup' : 'Continue' }}
                <i aria-hidden="true" v-if="!isLastStep" class="fas fa-arrow-right"></i>
                <i aria-hidden="true" v-else class="fas fa-check"></i>
              </template>
            </button>
          </div>
        </div>

      </div>
    </div>

    <!-- COMPLETION SCREEN -->
    <div v-else-if="screen === 'complete'" :class="screenClass">
      <WizardCompletion
        @go-settings="goToSettings"
        @go-requests="goToRequests"
      />
      <AppFooter />
    </div>

    <AppDialog v-if="showLogs" width="max-w-6xl" title="Logs" icon="fas fa-file-alt" @close="showLogs = false">
      <LogsComponent embedded />
    </AppDialog>

    <!-- Hidden file input for config import -->
    <input
      ref="fileInput"
      type="file"
      accept=".json,application/json"
      @change="handleFileImport"
      class="hidden"
    />
  </div>
</template>

<script>
import { ref, computed, watch } from 'vue';
import axios from 'axios';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toast-notification';
import { TOAST_OPTIONS } from '@/toastOptions';

import AppFooter from './AppFooter.vue';
import LogsComponent from './LogsComponent.vue';
import AppDialog from './ui/AppDialog.vue';
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
  REQUEST_FIRST_SEASON_ONLY: false,
};

export default {
  name: 'ConfigWizard',
  components: {
    AppDialog,
    AppFooter,
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
    const toast = useToast(TOAST_OPTIONS);

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
    const { bg1Url, bg2Url, activeBg, startBackgroundImageRotation, stopBackgroundImageRotation } = useBackgroundImage();

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
          label: 'Seer',
          description: 'Connect your media request manager to submit suggestions.',
          component: SettingsServices,
          wizardSection: 'seer',
          optional: false,
        },
        {
          id: 'trakt',
          label: 'Trakt',
          description: 'Augment recommendations with your Trakt watch history.',
          component: SettingsServices,
          wizardSection: 'trakt',
          optional: true,
        },
        {
          id: 'simkl',
          label: 'Simkl',
          description: 'Augment recommendations with your Simkl watch history.',
          component: SettingsServices,
          wizardSection: 'simkl',
          optional: true,
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
        if (!stepValidity.value['media-server']) {
            return 'Connect your media server to continue.';
          }
      }
      if (step.id === 'tmdb') return 'Test your TMDB connection above to continue.';
      if (step.id === 'seer') return 'Test your Seer connection above to continue.';
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
    watch(() => config.value.ENABLE_STATIC_BACKGROUND, (enabled) => {
      if (enabled) {
        stopBackgroundImageRotation();
      } else {
        startBackgroundImageRotation();
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
        }
      }
      if (cfg.TRAKT_CLIENT_ID) stepValidity.value.trakt = true;
      if (cfg.SIMKL_CLIENT_ID) stepValidity.value.simkl = true;
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

    // ─── Initialization ───────────────────────────────────────────────────────
    fetchConfig().then(() => {
      if (!config.value.ENABLE_STATIC_BACKGROUND) {
        startBackgroundImageRotation();
      }
      preValidateFromConfig();
    });

    // Layout classes shared by the three screens and the card's horizontal bands.
    const screenClass = 'relative z-10 flex min-h-screen flex-col items-center justify-center bg-[rgba(5,10,18,0.45)] px-4 py-8 backdrop-blur-sm';
    const sectionClass = 'shrink-0 px-5 md:px-7';

    const stepCircleClass = (step, i) => {
      if (i < currentStepIndex.value) return 'border-good/40 bg-good/18 text-good';
      if (i === currentStepIndex.value) {
        return step.optional
          ? 'border-transparent bg-caution text-white shadow-[0_0_0_4px] shadow-caution/20'
          : 'border-transparent bg-brand text-white shadow-[0_0_0_4px] shadow-brand/22';
      }
      return 'border-white/15 bg-white/6 text-ink-4';
    };

    return {
      screenClass,
      sectionClass,
      stepCircleClass,
      screen,
      showLogs,
      isSaving,
      currentStepIndex,
      config,
      hasExistingConfig,
      isImporting,
      fileInput,
      bg1Url,
      bg2Url,
      activeBg,
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
    };
  },
};
</script>
