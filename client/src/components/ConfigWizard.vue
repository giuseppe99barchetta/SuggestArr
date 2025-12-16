<template>
  <div>
    <!-- Welcome Screen -->
    <div v-if="showWelcome" class="wizard-container" :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">
      <div class="wizard-content">
        <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank">
          <img src="@/assets/logo.png" alt="SuggestArr Logo" class="attached-logo mb-6 text-center">
        </a>

        <div class="welcome-card">
          <h1>Welcome to SuggestArr!</h1>
          <p class="welcome-subtitle">
            Let's get you set up with personalized content suggestions from your media server.
          </p>

          <div class="setup-options">
            <button @click="startQuickSetup" class="setup-btn primary">
              <i class="fas fa-rocket"></i>
              <span>Quick Setup</span>
              <small>Recommended for most users</small>
            </button>

            <button @click="startAdvancedSetup" class="setup-btn secondary">
              <i class="fas fa-cogs"></i>
              <span>Advanced Setup</span>
              <small>Configure all settings now</small>
            </button>
          </div>

          <div class="existing-config" v-if="hasExistingConfig">
            <p>
              <i class="fas fa-info-circle"></i>
              Existing configuration detected. You can also go directly to
              <router-link to="/settings" class="settings-link">Settings</router-link>.
            </p>
          </div>
        </div>

        <Footer />
      </div>
    </div>

    <!-- Setup Wizard -->
    <div v-else-if="currentStep <= steps.length" class="wizard-container"
      :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">

      <div class="wizard-content">
        <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank">
          <img src="@/assets/logo.png" alt="SuggestArr Logo" class="attached-logo mb-6 text-center">
        </a>

        <div class="setup-header">
          <button @click="goBack" class="back-btn" v-if="currentStep > 1">
            <i class="fas fa-arrow-left"></i>
            Back
          </button>
          <button @click="showWelcome = true" class="back-btn" v-else>
            <i class="fas fa-arrow-left"></i>
            Back to Setup Options
          </button>
        </div>

        <div class="progress-bar">
          <div class="progress" :style="{ width: progressBarWidth }"></div>
        </div>
        <p class="steps-count">
          {{ setupMode === 'quick' ? 'Quick Setup' : 'Advanced Setup' }} - Step {{ currentStep }} of {{ steps.length }}
        </p>

        <!-- Use dynamic components for each step -->
        <div class="wizard-step-container">
          <transition name="fade" mode="out-in">
            <component
              :is="currentStepComponent"
              :config="config"
              :isQuickSetup="setupMode === 'quick'"
              @next-step="handleStepChange(1)"
              @previous-step="handleStepChange(-1)"
              @update-config="updateConfig"
              @skip-step="skipStep" />
          </transition>
        </div>

        <Footer />
      </div>
    </div>

    <!-- Completion Screen -->
    <div v-else-if="currentStep === steps.length + 1" class="wizard-container" :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">
      <div class="wizard-content">
        <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank">
          <img src="@/assets/logo.png" alt="SuggestArr Logo" class="attached-logo mb-6 text-center">
        </a>

        <div class="completion-card">
          <div class="success-icon">
            <i class="fas fa-check-circle"></i>
          </div>

          <h1>Setup Complete!</h1>
          <p class="completion-subtitle">
            SuggestArr is now configured and ready to suggest content from your media server.
          </p>

          <div class="next-steps">
            <h3>What's Next?</h3>
            <ul>
              <li>View and manage your suggestions in the <strong>Requests</strong> page</li>
              <li>Fine-tune your preferences in <strong>Settings</strong></li>
              <li>Run your first content suggestion manually</li>
            </ul>
          </div>

          <div class="completion-actions">
            <button @click="goToSettings" class="action-btn secondary">
              <i class="fas fa-cog"></i>
              Go to Settings
            </button>
            <button @click="goToRequests" class="action-btn primary">
              <i class="fas fa-list-alt"></i>
              View Suggestions
            </button>
          </div>
        </div>

        <Footer />
      </div>
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
import DbConfig from './configWizard/DbConfig.vue';

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
    DbConfig
  },
  data() {
    return {
      showWelcome: true,
      setupMode: 'quick', // 'quick' or 'advanced'
      currentStep: 1,
      config: this.getInitialConfig(),
      backgroundImageUrl: '',
      intervalId: null,
      defaultImages: ['/images/default1.jpg', '/images/default2.jpg', '/images/default3.jpg'],
      currentDefaultImageIndex: 0,
      hasExistingConfig: false,
    };
  },
  computed: {
    progressBarWidth() {
      return `${(this.currentStep / this.steps.length) * 100}%`;
    },
    steps() {
      const quickSteps = {
        jellyfin: ['MediaServiceSelection', 'TmdbConfig', 'JellyfinConfig', 'SeerConfig'],
        plex: ['MediaServiceSelection', 'TmdbConfig', 'PlexConfig', 'SeerConfig'],
        emby: ['MediaServiceSelection', 'TmdbConfig', 'JellyfinConfig', 'SeerConfig'],
      };

      const advancedSteps = {
        jellyfin: ['MediaServiceSelection', 'TmdbConfig', 'JellyfinConfig', 'SeerConfig', 'DbConfig', 'ContentFilterSettings', 'AdditionalSettings'],
        plex: ['MediaServiceSelection', 'TmdbConfig', 'PlexConfig', 'SeerConfig', 'DbConfig', 'ContentFilterSettings', 'AdditionalSettings'],
        emby: ['MediaServiceSelection', 'TmdbConfig', 'JellyfinConfig', 'SeerConfig', 'DbConfig', 'ContentFilterSettings', 'AdditionalSettings'],
      };

      const steps = this.setupMode === 'quick' ? quickSteps : advancedSteps;
      return steps[this.config.SELECTED_SERVICE || 'jellyfin'];
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
  async mounted() {
    await this.fetchConfig();
    if (!this.config.TMDB_API_KEY) {
      this.startDefaultImageRotation();
    } else {
      this.hasExistingConfig = true;
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
        SUBPATH: '',
      };
    },
    async fetchConfig() {
      try {
        const { data } = await axios.get('/api/config/fetch');
        if (data) {
          this.config = { ...this.getInitialConfig(), ...data };
          this.hasExistingConfig = !!(data.TMDB_API_KEY && data.SELECTED_SERVICE);
        }
      } catch (error) {
        console.error('Error fetching configuration:', error);
      }
    },
    async saveConfig() {
      try {
        // Set default values for quick setup if they weren't configured
        if (this.setupMode === 'quick') {
          const defaults = {
            DB_TYPE: 'sqlite',
            MAX_SIMILAR_MOVIE: 5,
            MAX_SIMILAR_TV: 2,
            MAX_CONTENT_CHECKS: 10,
            SEARCH_SIZE: 20,
            CRON_TIMES: '0 0 * * *',
            EXCLUDE_DOWNLOADED: true,
            EXCLUDE_REQUESTED: true,
          };
          this.config = { ...defaults, ...this.config };
        }

        await axios.post('/api/config/save', this.config);

        // Mark setup as completed
        await axios.post('/api/config/complete-setup');

        this.$toast.open({
          message: 'Setup completed successfully!',
          type: 'success',
          duration: 3000,
          position: 'top-right',
        });

        this.currentStep = this.steps.length + 1;

      } catch (error) {
        this.$toast.open({
          message: 'Error saving configuration. Please try again!',
          type: 'error',
          duration: 5000,
          position: 'top-right',
        });
        console.error('Error saving configuration:', error);
      }
    },

    // New setup flow methods
    startQuickSetup() {
      this.setupMode = 'quick';
      this.showWelcome = false;
      this.currentStep = 1;
    },

    startAdvancedSetup() {
      this.setupMode = 'advanced';
      this.showWelcome = false;
      this.currentStep = 1;
    },

    goBack() {
      if (this.currentStep > 1) {
        this.currentStep--;
      }
    },

    skipStep() {
      if (this.currentStep < this.steps.length) {
        this.currentStep++;
      }
    },

    goToSettings() {
      this.$router.push('/dashboard');
    },

    goToRequests() {
      this.$router.push('/requests');
    },
    updateConfig(key, value) {
      this.config[key] = value;
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

<style scoped>
.welcome-card {
  padding: 2rem;
  text-align: center;
  max-width: 600px;
  margin: 0 auto;
}

.welcome-card h1 {
  color: var(--color-text-primary);
  font-size: 2.5rem;
  margin-bottom: 1rem;
  font-weight: bold;
}

.welcome-subtitle {
  color: var(--color-text-muted);
  font-size: 1.2rem;
  margin-bottom: 2rem;
  line-height: 1.6;
}

.setup-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.setup-btn {
  background: var(--color-bg-interactive);
  border: 2px solid var(--color-border-light);
  border-radius: var(--border-radius-lg);
  padding: 2rem 1.5rem;
  cursor: pointer;
  transition: var(--transition-base);
  color: var(--color-text-primary);
  text-align: center;
  backdrop-filter: blur(10px);
}

.setup-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
}

.setup-btn.primary {
  background: linear-gradient(135deg, var(--color-primary), #1d4ed8);
  border-color: var(--color-primary);
}

.setup-btn.primary:hover {
  background: linear-gradient(135deg, var(--color-primary-hover), #1e40af);
}

.setup-btn.secondary {
  background: var(--color-bg-active);
  border-color: var(--color-border-medium);
}

.setup-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.4);
}

.setup-btn i {
  font-size: 2rem;
  margin-bottom: 1rem;
  display: block;
}

.setup-btn span {
  font-size: 1.3rem;
  font-weight: bold;
  display: block;
  margin-bottom: 0.5rem;
}

.setup-btn small {
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.existing-config {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: var(--border-radius-sm);
  padding: 1rem;
  margin-top: 1rem;
}

.existing-config p {
  color: #e5e7eb;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.settings-link {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 500;
}

.settings-link:hover {
  text-decoration: underline;
}

.setup-header {
  margin-bottom: 1rem;
}

.back-btn {
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  color: var(--color-text-primary);
  padding: 0.5rem 1rem;
  border-radius: var(--border-radius-sm);
  cursor: pointer;
  transition: var(--transition-base);
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.completion-card {
  background: rgba(0, 0, 0, 0.8);
  border-radius: var(--border-radius-lg);
  padding: 2rem;
  text-align: center;
  max-width: 600px;
  margin: 0 auto;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.success-icon {
  color: var(--color-success);
  font-size: 4rem;
  margin-bottom: 1rem;
}

.success-icon i {
  animation: checkmark 0.5s ease-in-out;
}

@keyframes checkmark {
  0% { transform: scale(0) rotate(-45deg); }
  50% { transform: scale(1.2) rotate(-45deg); }
  100% { transform: scale(1) rotate(0deg); }
}

.completion-card h1 {
  color: var(--color-text-primary);
  font-size: 2.5rem;
  margin-bottom: 1rem;
  font-weight: bold;
}

.completion-subtitle {
  color: var(--color-text-muted);
  font-size: 1.2rem;
  margin-bottom: 2rem;
  line-height: 1.6;
}

.next-steps {
  text-align: left;
  background: rgba(255, 255, 255, 0.05);
  border-radius: var(--border-radius-sm);
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.next-steps h3 {
  color: var(--color-text-primary);
  margin-bottom: 1rem;
  font-size: 1.2rem;
}

.next-steps ul {
  color: #e5e7eb;
  margin: 0;
  padding-left: 1.5rem;
  line-height: 1.6;
}

.next-steps li {
  margin-bottom: 0.5rem;
}

.completion-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
}

.action-btn {
  padding: 1rem 2rem;
  border-radius: var(--border-radius-sm);
  font-weight: bold;
  cursor: pointer;
  transition: var(--transition-base);
  border: none;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  font-size: 1rem;
  min-width: 150px;
  justify-content: center;
}

.action-btn.primary {
  background: linear-gradient(135deg, var(--color-success), #059669);
  color: white;
}

.action-btn.primary:hover {
  background: linear-gradient(135deg, #059669, #047857);
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(16, 185, 129, 0.3);
}

.action-btn.secondary {
  background: var(--color-bg-interactive);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-medium);
}

.action-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.5);
  transform: translateY(-2px);
}

/* Responsive Design */
@media (max-width: 768px) {
  .welcome-card,
  .completion-card {
    padding: 1.5rem;
    margin: 0 1rem;
  }

  .welcome-card h1,
  .completion-card h1 {
    font-size: 2rem;
  }

  .welcome-subtitle,
  .completion-subtitle {
    font-size: 1rem;
  }

  .setup-options {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .setup-btn {
    padding: 1.5rem 1rem;
  }

  .setup-btn i {
    font-size: 1.5rem;
  }

  .setup-btn span {
    font-size: 1.1rem;
  }

  .completion-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .action-btn {
    min-width: auto;
  }
}
</style>

