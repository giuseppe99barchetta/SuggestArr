<template>
  <div>
    <div v-if="currentStep <= 5" class="wizard-container">
      <div class="wizard-content">
        <h2 class="text-3xl font-bold text-gray-200 mb-6 text-center">SuggestArr Wizard</h2>
        <div class="progress-bar">
          <div class="progress" :style="{ width: progressBarWidth }"></div>
        </div>
        <p class="steps-count">{{ currentStep }} / 5 Steps Complete</p>

        <!-- Use dynamic components for each step -->
        <transition name="fade" mode="out-in" @after-leave="showNewStep">
          <component :is="currentStepComponent"
            :config="config"
            @next-step="nextStep"
            @previous-step="previousStep"
            @update-tmdb-key="updateTmdbKey"
            @update-jellyfin-url="updateJellyfinUrl"
            @update-jellyfin-token="updateJellyfinToken"
            @update-jellyfin-libraries="updateJellyfinLibraries"
            @update-jellyseer-url="updateJellyseerUrl"
            @update-jellyseer-token="updateJellyseerToken"
            @update-jellyseer-user="updateJellyseerUser"
            @update-jellyseer-password="updateJellyseerPassword"
            @update-max-similar-movies="updateMaxSimilarMovies"
            @update-max-similar-tv="updateMaxSimilarTV"
            @update-cron-times="updateCronTimes"
            @update-max-content-checks="updateMaxContentChecks"
          />
        </transition>
        <Footer />
      </div>
    </div>

    <div v-if="currentStep === 6">
      <ConfigSummary :config="config" @edit-config="editConfig" />
    </div>

  </div>
</template>

<script>
import '@/assets/styles/wizard.css';
import Footer from './AppFooter.vue';

// Import all the wizard configuration components
import TmdbConfig from './configWizard/TmdbConfig.vue';
import JellyfinConfig from './configWizard/JellyfinConfig.vue';
import JellyseerConfig from './configWizard/JellyseerConfig.vue';
import AdditionalSettings from './configWizard/AdditionalSettings.vue';
import SaveConfig from './configWizard/SaveConfig.vue';
import ConfigSummary from './ConfigSummary.vue';
import axios from 'axios';

export default {
  components: {
    Footer,
    ConfigSummary,      // Final configuration summary
    TmdbConfig,         // Step 1: TMDB Configuration
    JellyfinConfig,     // Step 2: Jellyfin Configuration
    JellyseerConfig,    // Step 3: Jellyseer Configuration
    AdditionalSettings, // Step 4: Additional Settings
    SaveConfig          // Step 5: Save configuration
  },
  data() {
    return {
      currentStep: 1,  // Current step of the wizard
      config: {
        TMDB_API_KEY: '',
        JELLYFIN_API_URL: '',
        JELLYFIN_TOKEN: '',
        JELLYSEER_API_URL: '',
        JELLYSEER_TOKEN: '',
        JELLYSEER_USER_NAME: '',
        JELLYSEER_USER_PSW: '',
        MAX_SIMILAR_MOVIE: 5,  // Default values
        MAX_SIMILAR_TV: 2,     // Default values
        MAX_CONTENT_CHECKS: 10,
        CRON_TIMES: '0 0 * * *', // Default value
        JELLYFIN_LIBRARIES: [],
      }
    };
  },
  computed: {
    progressBarWidth() {
      return `${(this.currentStep / 5) * 100}%`;
    },
    currentStepComponent() {
      // Map of components for each step
      const steps = {
        1: 'TmdbConfig',         // Step 1
        2: 'JellyfinConfig',     // Step 2
        3: 'JellyseerConfig',    // Step 3
        4: 'AdditionalSettings', // Step 4
        5: 'SaveConfig'          // Summary and saving step
      };
      return steps[this.currentStep] || 'SaveConfig';
    }
  },
  mounted() {
    // Fetch the saved configuration
    this.fetchConfig();
  },
  methods: {
    // Method to fetch the existing configuration
    fetchConfig() {
      axios.get('http://localhost:5000/api/config')
        .then(response => {
          if (response.data && Object.keys(response.data).length > 0) {
            this.config = response.data; // Load saved configuration
            // Check if any keys are already set in the config, and if so, jump to summary step
            if (this.config.TMDB_API_KEY || this.config.JELLYFIN_API_URL || this.config.JELLYFIN_TOKEN) {
              this.currentStep = 6; // Go directly to the summary if the configuration exists
            }
          }
        })
        .catch(error => {
          console.error('Error fetching configuration:', error);
        })
        .finally(() => {
          this.loading = false; // Remove loading state
        });
    },
    // Method to go to the next step
    nextStep() {
      this.showStep = false;
        if (this.currentStep < 6) {
          this.currentStep++;
        }
        if (this.currentStep == 6) {
          this.saveConfig();
        }
        this.showStep = true;
    },
    // Method to go back to the previous step
    previousStep() {
        this.showStep = false;
        if (this.currentStep > 1) {
          this.currentStep--;
        }
        this.showStep = true;
    },

    // Methods to update configuration from child component props
    updateTmdbKey(newValue) {
      this.config.TMDB_API_KEY = newValue;
    },
    updateJellyfinUrl(newValue) {
      this.config.JELLYFIN_API_URL = newValue.replace(/\/+$/, '');
    },
    updateJellyfinToken(newValue) {
      this.config.JELLYFIN_TOKEN = newValue;
    },
    updateJellyfinLibraries({ ids, names }) {
      this.config.JELLYFIN_LIBRARIES = ids;  // Save only the IDs for persistence
      this.selectedLibraryNames = names;     // Save names for display purposes
    },
    updateJellyseerUrl(newValue) {
      this.config.JELLYSEER_API_URL = newValue.replace(/\/+$/, '');
    },
    updateJellyseerToken(newValue) {
      this.config.JELLYSEER_TOKEN = newValue;
    },
    updateJellyseerUser(newValue) {
      this.config.JELLYSEER_USER_NAME = newValue; // Store Jellyseer user
    },
    updateJellyseerPassword(newValue) {
      this.config.JELLYSEER_USER_PSW = newValue; // Store Jellyseer password
    },
    updateMaxSimilarMovies(newValue) {
      this.config.MAX_SIMILAR_MOVIE = newValue;
    },
    updateMaxSimilarTV(newValue) {
      this.config.MAX_SIMILAR_TV = newValue;
    },
    updateCronTimes(newValue) {
      this.config.CRON_TIMES = newValue;
    },
    updateMaxContentChecks(newValue) {
      this.config.MAX_CONTENT_CHECKS = newValue;
    },

    editConfig() {
      this.currentStep = 1;
    },
    // Method to save the configuration
    saveConfig() {
      axios.post('http://localhost:5000/api/save', this.config)
        .then(response => {
          console.log('Configuration saved:', response);
        })
        .catch(error => {
          console.error('Error saving configuration:', error);
        });
    },
  }
};
</script>
