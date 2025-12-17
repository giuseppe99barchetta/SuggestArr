<template>
  <!-- Floating Log Button -->
  <button v-if="!showWelcome" @click="toggleLogs" class="floating-log-btn" 
          title="View Setup Logs">
    <i class="fas fa-clipboard-list"></i>
  </button>

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
              <router-link to="/" class="settings-link">Settings</router-link>.
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Setup Wizard -->
    <div v-else-if="currentStep <= steps.length" class="wizard-container"
      :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">

      <div class="wizard-content">
        <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank">
          <img src="@/assets/logo.png" alt="SuggestArr Logo" class="attached-logo mb-6 text-center">
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
              @skip-step="skipStep" />
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
          <img src="@/assets/logo.png" alt="SuggestArr Logo" class="attached-logo mb-6 text-center">
        </a>

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

          <Footer />
      </div>
    </div>
  </div>

  <!-- Logs Modal -->
  <Transition name="modal">
    <div v-if="showLogs" class="modal-overlay" @click.self="toggleLogs">
      <div class="modal-container" @click.stop>
        <!-- Modal Header -->
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

        <!-- Modal Body -->
        <div class="modal-body">
          <LogsComponent />
        </div>

        <!-- Modal Footer -->
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
import '@/assets/styles/wizard.css';
import Footer from './AppFooter.vue';
import LogsComponent from './LogsComponent.vue';
import axios from 'axios';
import { fetchRandomMovieImage } from '@/api/tmdbApi';

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
  components: {
    Footer,
    LogsComponent,
    MediaServiceSelection,
    TmdbConfig,
    JellyfinConfig,
    PlexConfig,
    SeerConfig,
    DbConfig,
    ContentFilterSettings,
    AdditionalSettings,
  },
  data() {
    return {
      showWelcome: true,
      showLogs: false,
      setupMode: 'quick',
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

      const mode = stepsByService[this.setupMode];
      const service = this.config.SELECTED_SERVICE || 'jellyfin';
      return mode[service];
    },
    currentStepComponent() {
      return this.steps[this.currentStep - 1];
    },
  },
  watch: {
    'config.TMDB_API_KEY'(newApiKey) {
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
  beforeUnmount() {
    this.stopBackgroundImageRotation();
    if (this.showLogs) {
      document.body.style.overflow = '';
    }
  },
  methods: {
    getInitialConfig() {
      return {
        TMDB_API_KEY: '',
        JELLYFIN_API_URL: '',
        JELLYFIN_TOKEN: '',
        JELLYFIN_LIBRARIES: [],
        PLEX_API_URL: '',
        PLEX_TOKEN: '',
        PLEX_LIBRARIES: [],
        SEER_API_URL: '',
        SEER_TOKEN: '',
        SEER_USER_NAME: '',
        SEER_USER_PSW: '',
        SEER_SESSION_TOKEN: '',
        SELECTED_SERVICE: '',
        MAX_SIMILAR_MOVIE: 5,
        MAX_SIMILAR_TV: 2,
        MAX_CONTENT_CHECKS: 10,
        SEARCH_SIZE: 20,
        CRON_TIMES: '0 0 * * *',
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
        if (this.setupMode === 'quick') {
          this.config = { ...QUICK_SETUP_DEFAULTS, ...this.config };
        }

        await axios.post('/api/config/save', this.config);
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
    goToSettings() {
      this.$router.push('/dashboard');
    },
    goToRequests() {
      this.$router.push('/requests');
    },
    updateConfig(key, value) {
      this.config[key] = value;
    },
    skipStep() {
      if (this.currentStep < this.steps.length) {
        this.currentStep++;
      }
    },
    handleStepChange(stepChange) {
      if (stepChange < 0 && this.currentStep === 1) {
        this.showWelcome = true;
        return;
      }

      if (this.currentStep + stepChange > 0 && this.currentStep + stepChange <= this.steps.length) {
        this.currentStep += stepChange;
      } else if (this.currentStep + stepChange > this.steps.length) {
        this.saveConfig();
      }
    },
    toggleLogs() {
      this.showLogs = !this.showLogs;
      document.body.style.overflow = this.showLogs ? 'hidden' : '';
      
      if (this.showLogs) {
        this.$nextTick(() => {
          const overlay = document.querySelector('.modal-overlay');
          if (overlay) overlay.scrollTop = 0;
        });
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
      this.intervalId = setInterval(() => this.fetchRandomMovieImage(), 10000);
    },
    stopBackgroundImageRotation() {
      if (this.intervalId) {
        clearInterval(this.intervalId);
        this.intervalId = null;
      }
    },
  },
};
</script>

<style scoped>
/* Welcome Card */
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

/* Setup Options */
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

/* Existing Config */
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

/* Completion Card */
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

/* Action Buttons */
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
