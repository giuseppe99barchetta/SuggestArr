<template>
  <div class="config-section">
    <h3 class="section-title">TMDB Configuration</h3>
    <p class="section-description">
      You can get your TMDB API Key by signing up at 
      <a href="https://www.themoviedb.org/" target="_blank" rel="noopener noreferrer" 
         class="link">The Movie Database</a>.
    </p>

    <!-- TMDB API Key Input -->
    <label for="TMDB_API_KEY" class="form-label">
      TMDB API Key:
    </label>
    <div class="input-group">
      <input 
        type="text" 
        :value="config.TMDB_API_KEY" 
        @input="handleInput"
        @keyup.enter="testTmdbApi"
        :disabled="tmdbTestState.isTesting"
        class="form-input"
        id="TMDB_API_KEY" 
        placeholder="Enter your TMDB API Key"
      >
      
      <button 
        type="button" 
        @click="testTmdbApi" 
        :disabled="tmdbTestState.isTesting || !config.TMDB_API_KEY"
        :class="[
          'btn btn-test',
          {
            'btn-success': tmdbTestState.status === 'success',
            'btn-danger': tmdbTestState.status === 'fail',
            'btn-primary': tmdbTestState.status === null && config.TMDB_API_KEY,
            'btn-disabled': !config.TMDB_API_KEY
          }
        ]"
      >
        <span v-if="tmdbTestState.isTesting" class="btn-content">
          <i class="fas fa-spinner fa-spin"></i>
          <span class="btn-text">Testing</span>
        </span>
        <span v-else-if="tmdbTestState.status === 'success'" class="btn-content">
          <i class="fas fa-check"></i>
          <span class="btn-text">Valid</span>
        </span>
        <span v-else-if="tmdbTestState.status === 'fail'" class="btn-content">
          <i class="fas fa-times"></i>
          <span class="btn-text">Failed</span>
        </span>
        <span v-else class="btn-content">
          <i class="fas fa-play"></i>
          <span class="btn-text">Test</span>
        </span>
      </button>
    </div>

    <!-- Success Message -->
    <div v-if="tmdbTestState.status === 'success'" 
         class="alert alert-success" 
         role="alert">
      <i class="fas fa-check-circle"></i>
      <span>TMDB API Key validated successfully!</span>
    </div>

    <!-- Error Message -->
    <div v-if="tmdbTestState.status === 'fail'" 
         class="alert alert-danger" 
         role="alert">
      <i class="fas fa-exclamation-circle"></i>
      <span>Failed to validate TMDB API Key. Please check your key and try again.</span>
    </div>

    <!-- Navigation Buttons -->
    <div class="flex justify-between mt-8 gap-4">
      <button @click="$emit('previous-step')"
              class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full 
                     transition-colors duration-200">
          <i class="fas fa-arrow-left mr-2"></i>Back
      </button>
      <button @click="$emit('next-step')"
              :disabled="tmdbTestState.status !== 'success'" 
              class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full
                     transition-colors duration-200"
              :class="{ 'opacity-50 cursor-not-allowed': tmdbTestState.status !== 'success' }">
          Next Step<i class="fas fa-arrow-right ml-2"></i>
      </button>
    </div>
  </div>
</template>

<script>
import { testTmdbApi } from '../../api/api';

export default {
  props: ['config'],
  data() {
    return {
      tmdbTestState: {
        status: null,
        isTesting: false
      }
    };
  },
  methods: {
    handleInput(event) {
      const value = event.target.value;
      this.$emit('update-config', 'TMDB_API_KEY', value);
      this.tmdbTestState.status = null;
    },
    testTmdbApi() {
      if (!this.config.TMDB_API_KEY) return;
      
      this.tmdbTestState.isTesting = true;
      this.tmdbTestState.status = null;
      testTmdbApi(this.config.TMDB_API_KEY)
        .then(() => {
          this.tmdbTestState.status = 'success';
        })
        .catch(() => {
          this.tmdbTestState.status = 'fail';
        })
        .finally(() => {
          this.tmdbTestState.isTesting = false;
        });
    }
  },
  mounted() {
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
  margin-bottom: 1rem;
}

.link {
  color: var(--color-primary);
  text-decoration: none;
  border-bottom: 1px dotted var(--color-primary);
  transition: all 0.2s ease;
}

.link:hover {
  color: var(--color-primary-hover);
  border-bottom-style: solid;
}

/* Form Elements */
.form-label {
  display: block;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 0.5rem;
}

.input-group {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.form-input {
  flex: 1;
  min-width: 200px;
  min-height: 40px;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--border-radius-sm);
  padding: 0 1rem;
  color: var(--color-text-primary);
  font-size: 0.9rem;
  transition: var(--transition-base);
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
}

.form-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-input::placeholder {
  color: var(--color-text-muted);
}

/* Buttons */
.btn-test {
  min-width: 100px;
  height: 44px;
  padding: 0 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-weight: 600;
  font-size: 0.9rem;
  border-radius: var(--border-radius-sm);
  transition: var(--transition-base);
  border: none;
  cursor: pointer;
  white-space: nowrap;
  background: grey;
}

.btn-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-text {
  white-space: nowrap;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.btn-success {
  background: var(--color-success);
  color: white;
}

.btn-success:hover:not(:disabled) {
  background: #218838;
}

.btn-danger {
  background: var(--color-danger);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: #dc2626;
}

.btn-secondary {
  background: var(--color-bg-interactive);
  color: var(--color-text-primary);
  border: 2px solid var(--color-border-medium);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-bg-active);
  border-color: var(--color-border-medium);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Alerts */
.alert {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  border-radius: var(--border-radius-sm);
  margin-top: 1rem;
  font-size: 0.9rem;
  line-height: 1.4;
}

.alert-success {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid var(--color-success);
  color: var(--color-success);
}

.alert-danger {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--color-danger);
  color: var(--color-danger);
}

/* Navigation */
.navigation-buttons {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 2rem;
}

.navigation-buttons .btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  font-weight: 600;
  font-size: 0.9rem;
  border-radius: var(--border-radius-sm);
  transition: var(--transition-base);
  border: none;
  cursor: pointer;
  white-space: nowrap;
}

.navigation-buttons .btn:first-child {
  justify-self: flex-start;
}

.navigation-buttons .btn:last-child {
  justify-self: flex-end;
}

/* Responsive */
@media (max-width: 768px) {
  .input-group {
    flex-direction: column;
    align-items: stretch;
  }

  .form-input {
    min-width: auto;
  }

  .btn-test {
    min-width: auto;
  }

  .navigation-buttons {
    flex-direction: column;
    gap: 0.75rem;
  }

  .navigation-buttons .btn {
    width: 100%;
    justify-content: center;
    min-height: 48px;
  }

  .btn-text {
    display: none;
  }

  .section-description {
    font-size: 0.85rem;
  }
}
</style>
