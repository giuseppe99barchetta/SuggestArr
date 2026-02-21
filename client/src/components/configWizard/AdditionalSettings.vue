<template>
    <div class="config-section">
        <h3 class="section-title">Additional Configuration</h3>
        <p class="section-description">
            Suggestarr scans your recent viewing history and finds similar content based on the settings below. Adjust these options to control the number and type of suggestions generated.
        </p>

        <!-- Recommendation Settings Card -->
        <div class="settings-card">
            <h4 class="card-title">Recommendation Settings</h4>

            <div class="form-row">
                <div class="form-group flex-1">
                    <label for="MAX_SIMILAR_MOVIE" class="form-label">Max Similar Movies</label>
                    <input type="number" :value="config.MAX_SIMILAR_MOVIE"
                           @input="handleUpdate('MAX_SIMILAR_MOVIE', $event.target.value)"
                           class="form-input"
                           id="MAX_SIMILAR_MOVIE" placeholder="5" min="0">
                </div>

                <div class="form-group flex-1">
                    <label for="MAX_SIMILAR_TV" class="form-label">Max Similar TV Shows</label>
                    <input type="number" :value="config.MAX_SIMILAR_TV"
                           @input="handleUpdate('MAX_SIMILAR_TV', $event.target.value)"
                           class="form-input"
                           id="MAX_SIMILAR_TV" placeholder="2" min="0">
                </div>
            </div>
            <p class="form-help">
                <i class="fas fa-info-circle"></i>
                Number of similar items to find for each movie or TV show in your viewing history
            </p>

            <div class="form-row">
                <div class="form-group flex-1">
                    <label for="MAX_CONTENT_CHECKS" class="form-label">Max Content Checks</label>
                    <input type="number" :value="config.MAX_CONTENT_CHECKS"
                           @input="handleUpdate('MAX_CONTENT_CHECKS', $event.target.value)"
                           class="form-input"
                           id="MAX_CONTENT_CHECKS" placeholder="10" min="1">
                </div>

                <div class="form-group flex-1">
                    <label for="SEARCH_SIZE" class="form-label">Search Size</label>
                    <input type="number" :value="config.SEARCH_SIZE"
                           @input="handleUpdate('SEARCH_SIZE', $event.target.value)"
                           class="form-input"
                           id="SEARCH_SIZE" placeholder="20" min="1">
                </div>
            </div>
            <p class="form-help">
                <i class="fas fa-info-circle"></i>
                Content Checks: items from recent history to analyze | Search Size: total suggestions to generate
            </p>
        </div>

        <!-- Schedule Settings Card -->
        <div class="settings-card">
            <h4 class="card-title">Schedule Settings</h4>

            <div class="form-group">
                <label for="CRON_TIMES" class="form-label">Cron Schedule</label>
                <input type="text" :value="config.CRON_TIMES"
                       @input="handleCronInput($event.target.value)"
                       class="form-input"
                       :class="{ 'input-error': cronError }"
                       id="CRON_TIMES" placeholder="0 0 * * *">
                <p class="form-help">
                    <i class="fas fa-info-circle"></i>
                    Define when Suggestarr should run using cron syntax (e.g., "0 0 * * *" = daily at midnight)
                </p>

                <div v-if="cronDescription" class="alert alert-success">
                    <i class="fas fa-check-circle"></i>
                    <span>{{ cronDescription }}</span>
                </div>
                <div v-if="cronError" class="alert alert-danger">
                    <i class="fas fa-exclamation-circle"></i>
                    <span>{{ cronError }}</span>
                </div>
            </div>
        </div>

        <!-- Application Settings Card -->
        <div class="settings-card">
            <h4 class="card-title">Application Settings</h4>

            <div class="form-group">
                <label for="SUBPATH" class="form-label">Base URL Subpath</label>
                <input type="text" :value="config.SUBPATH"
                       @input="handleUpdate('SUBPATH', $event.target.value)"
                       class="form-input"
                       id="SUBPATH" placeholder="/suggestarr">
                <p class="form-help">
                    <i class="fas fa-info-circle"></i>
                    Subpath where Suggestarr will be accessible (e.g., "/suggestarr" for yourdomain.com/suggestarr). Leave empty for root path.
                </p>
            </div>
        </div>

        <!-- Navigation Buttons -->
        <div class="flex justify-between mt-8 gap-4">
            <button @click="$emit('previous-step')"
                class="btn-secondary w-full flex items-center justify-center gap-2 py-4 px-8">
                <i class="fas fa-arrow-left"></i>
                Back
            </button>
            <button @click="$emit('next-step')"
                class="btn-primary w-full flex items-center justify-center gap-2 py-4 px-8">
                Save Configuration
                <i class="fas fa-check"></i>
            </button>
        </div>
    </div>
</template>

<script>
import cronParser from 'cron-parser';

export default {
    props: ['config'],
    data() {
        return {
            cronDescription: '',
            cronError: ''
        };
    },
    methods: {
        handleUpdate(key, value) {
            this.$emit('update-config', key, value);
        },
        handleCronInput(value) {
            this.handleUpdate('CRON_TIMES', value);

            const validPresets = ['daily', 'weekly', 'every_12h', 'every_6h', 'every_hour'];
            if (validPresets.includes(value.toLowerCase())) {
                this.cronDescription = `Preset schedule: ${value}`;
                this.cronError = '';
                return;
            }

            try {
                const interval = cronParser.parseExpression(value);
                const nextRun = interval.next().toString();
                this.cronDescription = `Next run: ${nextRun}`;
                this.cronError = '';
            } catch (err) {
                this.cronDescription = '';
                this.cronError = 'Invalid cron expression';
            }
        }
    }
};
</script>

<style scoped>
/* Config Section */
.config-section {
  display: flex;
  flex-direction: column;
}

.section-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 0.5rem;
}

.section-description {
  color: var(--color-text-muted);
  font-size: 0.9rem;
  line-height: 1.5;
  margin-bottom: 1.5rem;
}


/* Form Row */
.form-row {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.form-row .form-group {
  margin-bottom: 0;
}

.form-row + .form-help,
.form-row + .form-row {
  margin-top: 1rem;
}

.flex-1 {
  flex: 1;
}

/* Input Error State */
.input-error {
  border-color: var(--color-error) !important;
}

.input-error:focus {
  border-color: var(--color-error) !important;
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.1) !important;
}

/* Responsive */
@media (max-width: 768px) {
  .form-row {
    flex-direction: column;
    gap: 0;
  }

  .form-row .form-group {
    margin-bottom: 1rem;
  }

  .settings-card {
    padding: 1rem;
  }
}
</style>
