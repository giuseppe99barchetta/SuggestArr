<template>
  <div>
    <div v-if="currentStep <= steps.length" class="wizard-container">
      <div class="wizard-content">
        <h2 class="text-3xl font-bold text-gray-200 mb-6 text-center">SuggestArr Wizard</h2>
        <div class="progress-bar">
          <div class="progress" :style="{ width: progressBarWidth }"></div>
        </div>
        <p class="steps-count">{{ currentStep }} / {{ steps.length }} Steps Complete</p>

        <!-- Use dynamic components for each step -->
        <transition name="fade" mode="out-in">
          <component :is="currentStepComponent" :config="config" 
                     @next-step="handleStepChange(1)" 
                     @previous-step="handleStepChange(-1)"
                     @update-config="updateConfig" />
        </transition>
        <Footer />
      </div>
    </div>

    <div v-if="currentStep === steps.length + 1">
      <ConfigSummary :config="config" @edit-config="editConfig" />
    </div>
  </div>
</template>

<script>
import '@/assets/styles/wizard.css';
import Footer from './AppFooter.vue';

// Import wizard components
import MediaServiceSelection from './configWizard/MediaServiceSelection.vue';
import TmdbConfig from './configWizard/TmdbConfig.vue';
import JellyfinConfig from './configWizard/JellyfinConfig.vue';
import SeerConfig from './configWizard/SeerConfig.vue';
import AdditionalSettings from './configWizard/AdditionalSettings.vue';
import PlexConfig from './configWizard/PlexConfig.vue';
import ConfigSummary from './ConfigSummary.vue';
import axios from 'axios';

export default {
  components: {
    Footer,
    ConfigSummary,
    TmdbConfig,
    JellyfinConfig,
    SeerConfig,
    AdditionalSettings,
    MediaServiceSelection,
    PlexConfig,
  },
  data() {
    return {
      currentStep: 1,  // Current step of the wizard
      config: this.getInitialConfig(),  // Load initial configuration
    };
  },
  computed: {
    // Calculate progress bar width
    progressBarWidth() {
      return `${(this.currentStep / this.steps.length) * 100}%`;
    },
    // Determine steps dynamically based on the selected service
    steps() {
      const serviceSteps = {
        jellyfin: ['MediaServiceSelection', 'TmdbConfig', 'JellyfinConfig', 'SeerConfig', 'AdditionalSettings'],
        plex: ['MediaServiceSelection', 'TmdbConfig', 'PlexConfig', 'SeerConfig', 'AdditionalSettings'],
      };
      return serviceSteps[this.config.SELECTED_SERVICE || 'jellyfin'];
    },
    currentStepComponent() {
      return this.steps[this.currentStep - 1] || 'SaveConfig';
    },
  },
  mounted() {
    // Fetch the saved configuration when component mounts
    this.fetchConfig();
  },
  methods: {
    // Initialize the configuration with default values
    getInitialConfig() {
      return {
        TMDB_API_KEY: '',
        JELLYFIN_API_URL: '',
        JELLYFIN_TOKEN: '',
        SEER_API_URL: '',    // Unified for Jellyseer/Overseer
        SEER_TOKEN: '',      // Unified for Jellyseer/Overseer
        SEER_USER_NAME: '',  // Unified for Jellyseer/Overseer
        SEER_USER_PSW: '',   // Unified for Jellyseer/Overseer
        MAX_SIMILAR_MOVIE: 5,  
        MAX_SIMILAR_TV: 2,    
        MAX_CONTENT_CHECKS: 10,
        CRON_TIMES: '0 0 * * *',
        JELLYFIN_LIBRARIES: [],
        SELECTED_SERVICE: '',
        PLEX_API_URL: '',
        PLEX_TOKEN: '',
        PLEX_LIBRARIES: [],
      };
    },

    // Generic method to update configuration values
    updateConfig(key, value) {
      this.config[key] = value;
    },

    // Fetch the existing configuration from the backend
    async fetchConfig() {
      try {
        const { data } = await axios.get('http://localhost:5000/api/config/fetch');
        if (data) {
          this.config = data;
          if (this.config.TMDB_API_KEY || this.config.JELLYFIN_API_URL || this.config.JELLYFIN_TOKEN) {
            this.currentStep = this.steps.length + 1; // Skip to summary
          }
        }
      } catch (error) {
        console.error('Error fetching configuration:', error);
      }
    },

    // Save the configuration to the backend
    async saveConfig() {
      try {
        await axios.post('http://localhost:5000/api/config/save', this.config);
        this.currentStep = this.steps.length + 1; // Move to summary after saving
      } catch (error) {
        console.error('Error saving configuration:', error);
      }
    },

    // Handle step navigation
    handleStepChange(stepChange) {
      if (this.currentStep + stepChange > 0 && this.currentStep + stepChange <= this.steps.length) {
        this.currentStep += stepChange;
      } else if (this.currentStep + stepChange > this.steps.length) {
        this.saveConfig();  // Save when reaching the last step
      }
    },

    // Method to reset to first step when editing config
    editConfig() {
      this.currentStep = 1;
    },
  },
};
</script>
