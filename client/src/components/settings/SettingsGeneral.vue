<template>
  <div class="settings-general">
    <div class="section-header">
      <h2>General Settings</h2>
      <p>Configure basic application settings and schedules</p>
    </div>

    <div class="settings-grid">
      <!-- Similar Content Settings -->
      <div class="settings-group">
        <h3>Content Suggestions</h3>

        <div class="form-group">
          <label for="maxSimilarMovie">Max Similar Movies</label>
          <input
            id="maxSimilarMovie"
            v-model.number="localConfig.MAX_SIMILAR_MOVIE"
            type="number"
            min="1"
            max="20"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">Maximum number of similar movies to suggest for each item</small>
        </div>

        <div class="form-group">
          <label for="maxSimilarTv">Max Similar TV Shows</label>
          <input
            id="maxSimilarTv"
            v-model.number="localConfig.MAX_SIMILAR_TV"
            type="number"
            min="1"
            max="20"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">Maximum number of similar TV shows to suggest for each item</small>
        </div>

        <div class="form-group">
          <label for="maxContentChecks">Max Content Checks</label>
          <input
            id="maxContentChecks"
            v-model.number="localConfig.MAX_CONTENT_CHECKS"
            type="number"
            min="1"
            max="50"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">Maximum number of content items to check for suggestions</small>
        </div>

        <div class="form-group">
          <label for="searchSize">Search Size</label>
          <input
            id="searchSize"
            v-model.number="localConfig.SEARCH_SIZE"
            type="number"
            min="1"
            max="100"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">Number of results to fetch from TMDB when searching for similar content</small>
        </div>
      </div>

      <!-- Schedule Settings -->
      <div class="settings-group">
        <h3>Schedule & Automation</h3>

        <div class="form-group">
          <label for="cronTimes">Cron Schedule</label>
          <input
            id="cronTimes"
            v-model="localConfig.CRON_TIMES"
            type="text"
            placeholder="0 0 * * *"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">
            Cron expression for when to run content suggestions (e.g., "0 0 * * *" for daily at midnight)
          </small>
        </div>

        <div class="form-group">
          <button
            @click="validateCron"
            class="btn btn-outline btn-sm"
            :disabled="isLoading || !localConfig.CRON_TIMES"
          >
            <i class="fas fa-check"></i>
            Validate Cron
          </button>
          <span v-if="cronValidationMessage" :class="['cron-message', cronValidationValid ? 'valid' : 'invalid']">
            {{ cronValidationMessage }}
          </span>
        </div>
      </div>

      <!-- Application Settings -->
      <div class="settings-group">
        <h3>Application</h3>

        <div class="form-group">
          <label for="subpath">Subpath</label>
          <input
            id="subpath"
            v-model="localConfig.SUBPATH"
            type="text"
            placeholder="/suggestarr"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">
            Subpath for running SuggestArr under a subdirectory (e.g., "/suggestarr"). Leave empty for root.
          </small>
        </div>
      </div>
    </div>

    <!-- Save Button -->
    <div class="settings-actions">
      <button
        @click="saveSettings"
        class="btn btn-primary"
        :disabled="isLoading || !hasChanges"
      >
        <i class="fas fa-save"></i>
        {{ isLoading ? 'Saving...' : 'Save Changes' }}
      </button>

      <button
        @click="resetToDefaults"
        class="btn btn-outline"
        :disabled="isLoading"
      >
        <i class="fas fa-undo"></i>
        Reset to Defaults
      </button>
    </div>
  </div>
</template>

<script>
import cronParser from 'cron-parser';

export default {
  name: 'SettingsGeneral',
  props: {
    config: {
      type: Object,
      required: true,
    },
    isLoading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['save-section'],
  data() {
    return {
      localConfig: {},
      originalConfig: {},
      cronValidationMessage: '',
      cronValidationValid: false,
    };
  },
  computed: {
    hasChanges() {
      return JSON.stringify(this.localConfig) !== JSON.stringify(this.originalConfig);
    },
  },
  watch: {
    config: {
      immediate: true,
      handler(newConfig) {
        this.localConfig = { ...newConfig };
        this.originalConfig = { ...newConfig };
      },
    },
  },
  methods: {
    validateCron() {
      if (!this.localConfig.CRON_TIMES) {
        this.cronValidationMessage = 'Please enter a cron expression';
        this.cronValidationValid = false;
        return;
      }

      try {
        cronParser.parseExpression(this.localConfig.CRON_TIMES);

        // Calculate next run time
        const interval = cronParser.parseExpression(this.localConfig.CRON_TIMES);
        const nextRun = interval.next();
        const now = new Date();
        const timeDiff = nextRun.getTime() - now.getTime();
        const hours = Math.floor(timeDiff / (1000 * 60 * 60));
        const minutes = Math.floor((timeDiff % (1000 * 60 * 60)) / (1000 * 60));

        this.cronValidationMessage = `Valid! Next run: in ${hours}h ${minutes}m`;
        this.cronValidationValid = true;
      } catch (error) {
        this.cronValidationMessage = `Invalid cron expression: ${error.message}`;
        this.cronValidationValid = false;
      }
    },

    async saveSettings() {
      try {
        await this.$emit('save-section', {
          section: 'general',
          data: {
            MAX_SIMILAR_MOVIE: this.localConfig.MAX_SIMILAR_MOVIE,
            MAX_SIMILAR_TV: this.localConfig.MAX_SIMILAR_TV,
            MAX_CONTENT_CHECKS: this.localConfig.MAX_CONTENT_CHECKS,
            SEARCH_SIZE: this.localConfig.SEARCH_SIZE,
            CRON_TIMES: this.localConfig.CRON_TIMES,
            SUBPATH: this.localConfig.SUBPATH || null,
          },
        });

        this.originalConfig = { ...this.localConfig };
      } catch (error) {
        console.error('Error saving general settings:', error);
      }
    },

    async resetToDefaults() {
      const defaults = {
        MAX_SIMILAR_MOVIE: '5',
        MAX_SIMILAR_TV: '2',
        MAX_CONTENT_CHECKS: '10',
        SEARCH_SIZE: '20',
        CRON_TIMES: '0 0 * * *',
        SUBPATH: null,
      };

      if (confirm('Are you sure you want to reset all general settings to their defaults?')) {
        this.localConfig = { ...this.localConfig, ...defaults };
        await this.saveSettings();
      }
    },
  },
};
</script>

<style scoped>
.settings-general {
  color: var(--color-text-primary);
}

.section-header {
  margin-bottom: 2rem;
}

.section-header h2 {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
  color: var(--color-text-primary);
}

.section-header p {
  color: var(--color-text-muted);
  font-size: 1rem;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 2rem;
  margin-bottom: 2rem;
}

.settings-group {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--border-radius-md);
  padding: 1.5rem;
}

.settings-group h3 {
  font-size: 1.2rem;
  margin-bottom: 1rem;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  margin-top: 0.5rem;
  font-weight: 500;
  color: #e5e7eb;
}

.form-control {
  width: 100%;
  padding: 0.75rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-primary);
  font-size: 1rem;
  transition: var(--transition-base);
  min-height: 44px;
}

.form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  background: var(--color-bg-active);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: var(--color-text-muted);
  line-height: 1.4;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: var(--border-radius-sm);
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition-base);
  border: none;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  font-size: 0.875rem;
  min-height: 44px;
  min-width: 44px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.btn-outline {
  background: var(--color-bg-interactive);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-medium);
}

.btn-outline:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.5);
}

.btn-sm {
  padding: 0.375rem 0.75rem;
  font-size: 0.8125rem;
  min-height: 44px;
  min-width: 44px;
}

.cron-message {
  margin-left: 1rem;
  font-size: 0.875rem;
  font-weight: 500;
}

/* Mobile Responsive */
@media (max-width: 768px) {
  .settings-grid {
    grid-template-columns: 1fr;
    gap: 1.5rem;
  }

  .settings-group {
    padding: 1rem;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-control {
    padding: 0.875rem;
    font-size: 16px; /* Prevents zoom on iOS */
  }

  .btn {
    width: 100%;
    justify-content: center;
    padding: 0.875rem 1rem;
    font-size: 1rem;
  }

  .btn-sm {
    width: auto;
    min-width: 44px;
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
  }

  .cron-message {
    margin-left: 0;
    margin-top: 0.5rem;
    display: block;
  }

  .section-header h2 {
    font-size: 1.5rem;
  }

  .settings-group h3 {
    font-size: 1.1rem;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
  }
}

@media (max-width: 480px) {
  .settings-grid {
    gap: 1rem;
  }

  .settings-group {
    padding: 0.75rem;
  }

  .form-control {
    padding: 0.75rem;
  }

  .btn {
    padding: 0.75rem;
  }
}

.cron-message.valid {
  color: var(--color-success);
}

.cron-message.invalid {
  color: var(--color-danger);
}

.settings-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  padding-top: 2rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

@media (max-width: 768px) {
  .settings-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .settings-group {
    padding: 1rem;
  }

  .settings-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .cron-message {
    display: block;
    margin-left: 0;
    margin-top: 0.5rem;
  }
}
</style>