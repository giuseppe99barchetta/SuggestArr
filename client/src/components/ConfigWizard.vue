<template>
  <div>
    <div v-if="currentStep <= steps.length" class="wizard-container"
      :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">

      <div class="wizard-content">
        <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank">
          <img src="@/assets/logo.png" alt="SuggestArr Logo" class="attached-logo mb-6 text-center">
        </a>
        <div class="progress-bar">
          <div class="progress" :style="{ width: progressBarWidth }"></div>
        </div>
        <p class="steps-count">{{ currentStep }} / {{ steps.length }} Steps Complete</p>

        <!-- Use dynamic components for each step -->
        <transition name="fade" mode="out-in">
          <component :is="currentStepComponent" :config="config" @next-step="handleStepChange(1)"
            @previous-step="handleStepChange(-1)" @update-config="updateConfig" />
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
import axios from 'axios';
import { fetchRandomMovieImage } from '@/api/tmdbApi';


// Import wizard components
import MediaServiceSelection from './configWizard/MediaServiceSelection.vue';
import TmdbConfig from './configWizard/TmdbConfig.vue';
import JellyfinConfig from './configWizard/JellyfinConfig.vue';
import SeerConfig from './configWizard/SeerConfig.vue';
import AdditionalSettings from './configWizard/AdditionalSettings.vue';
import PlexConfig from './configWizard/PlexConfig.vue';
import ConfigSummary from './ConfigSummary.vue';
import ContentFilterSettings from './configWizard/ContentFilterSettings.vue';

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
    ContentFilterSettings,
  },
  data() {
    return {
      currentStep: 1,
      config: this.getInitialConfig(),
      backgroundImageUrl: '',
      intervalId: null,
      defaultImages: ['/images/default1.jpg', '/images/default2.jpg', '/images/default3.jpg'],
      currentDefaultImageIndex: 0,
    };
  },
  computed: {
    progressBarWidth() {
      return `${(this.currentStep / this.steps.length) * 100}%`;
    },
    steps() {
      const serviceSteps = {
        jellyfin: ['MediaServiceSelection', 'TmdbConfig', 'JellyfinConfig', 'SeerConfig', 'ContentFilterSettings', 'AdditionalSettings'],
        plex: ['MediaServiceSelection', 'TmdbConfig', 'PlexConfig', 'SeerConfig', 'ContentFilterSettings', 'AdditionalSettings'],
        emby: ['MediaServiceSelection', 'TmdbConfig', 'JellyfinConfig', 'SeerConfig', 'ContentFilterSettings', 'AdditionalSettings'],
      };
      return serviceSteps[this.config.SELECTED_SERVICE || 'jellyfin'];
    },
    currentStepComponent() {
      return this.steps[this.currentStep - 1] || 'SaveConfig';
    },
  },
  watch: {
    'config.TMDB_API_KEY': function (newApiKey) {
      if (newApiKey) {
        this.stopBackgroundImageRotation();
        this.startBackgroundImageRotation();
      }
    },
  },
  mounted() {
    this.fetchConfig();
    if (!this.config.TMDB_API_KEY) {
      this.startDefaultImageRotation();
    }
  },
  methods: {
    getInitialConfig() {
      return {
        TMDB_API_KEY: '',
        JELLYFIN_API_URL: '',
        JELLYFIN_TOKEN: '',
        SEER_API_URL: '',
        SEER_TOKEN: '',
        SEER_USER_NAME: '',
        SEER_USER_PSW: '',
        MAX_SIMILAR_MOVIE: 5,
        MAX_SIMILAR_TV: 2,
        MAX_CONTENT_CHECKS: 10,
        SEARCH_SIZE: 20,
        CRON_TIMES: '0 0 * * *',
        JELLYFIN_LIBRARIES: [],
        SELECTED_SERVICE: '',
        PLEX_API_URL: '',
        PLEX_TOKEN: '',
        PLEX_LIBRARIES: [],
        SEER_SESSION_TOKEN: '',
      };
    },
    async fetchConfig() {
      try {
        const { data } = await axios.get('/api/config/fetch');
        if (data) {
          this.config = data;
          if (this.config.TMDB_API_KEY) {
            this.currentStep = this.steps.length + 1;
          }
        }
      } catch (error) {
        console.error('Error fetching configuration:', error);
      }
    },
    async saveConfig() {
      try {
        await axios.post('/api/config/save', this.config);
        this.currentStep = this.steps.length + 1;
      } catch (error) {
        console.error('Error saving configuration:', error);
      }
    },
    updateConfig(key, value) {
      this.config[key] = value;
    },
    editConfig() {
      this.currentStep = 1;
    },
    
    handleStepChange(stepChange) {
      if (this.currentStep + stepChange > 0 && this.currentStep + stepChange <= this.steps.length) {
        this.currentStep += stepChange;
      } else if (this.currentStep + stepChange > this.steps.length) {
        this.saveConfig();
      }
    },

    startDefaultImageRotation() {
      this.backgroundImageUrl = this.defaultImages[this.currentDefaultImageIndex];

      this.intervalId = setInterval(() => {
        this.currentDefaultImageIndex = (this.currentDefaultImageIndex + 1) % this.defaultImages.length;
        this.backgroundImageUrl = this.defaultImages[this.currentDefaultImageIndex];
      }, 10000);
    },
    async fetchRandomMovieImage() {
      const imageUrl = await fetchRandomMovieImage(this.config.TMDB_API_KEY);
      if (imageUrl) {
        const img = new Image();
        img.src = imageUrl;
        img.onload = () => {
          this.backgroundImageUrl = imageUrl;
        };
      }
    },
    startBackgroundImageRotation() {
      this.fetchRandomMovieImage();
      this.intervalId = setInterval(() => {
        this.fetchRandomMovieImage();
      }, 10000);
    },
    stopBackgroundImageRotation() {
      if (this.intervalId) {
        clearInterval(this.intervalId);
      }
    },
  },
  beforeUnmount() {
    this.stopBackgroundImageRotation();
  },
};
</script>

