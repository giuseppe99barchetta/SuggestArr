<template>
  <div class="welcome-card">
    <h1>Welcome to SuggestArr!</h1>
    <p class="welcome-subtitle">
      Let's get you set up with personalized content suggestions from your media server.
    </p>

    <div class="setup-options">
      <button @click="$emit('start-quick')" class="setup-btn secondary">
        <i class="fas fa-rocket"></i>
        <span>Quick Setup</span>
        <small>Recommended for most users</small>
      </button>

      <button @click="$emit('start-advanced')" class="setup-btn secondary">
        <i class="fas fa-cogs"></i>
        <span>Advanced Setup</span>
        <small>Configure all settings now</small>
      </button>
    </div>

    <div class="import-config-section">
      <button @click="$emit('import-config')" class="import-btn" :disabled="isImporting">
        <i :class="isImporting ? 'fas fa-spinner fa-spin' : 'fas fa-file-import'"></i>
        <span>{{ isImporting ? 'Importing...' : 'Import Configuration' }}</span>
      </button>
      <p class="import-help">
        Already have a configuration file? Import it to restore your settings.
      </p>
    </div>

    <div class="existing-config" v-if="hasExistingConfig">
      <p>
        <i class="fas fa-info-circle"></i>
        Existing configuration detected. You can also go directly to
        <router-link to="/" class="settings-link">Settings</router-link>.
      </p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'WizardWelcome',
  props: {
    hasExistingConfig: Boolean,
    isImporting: Boolean,
  },
  emits: ['start-quick', 'start-advanced', 'import-config'],
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
  background: linear-gradient(135deg, var(--color-primary), #343435);
  border-color: var(--color-primary);
}

.setup-btn.primary:hover {
  background: linear-gradient(135deg, var(--color-primary-hover), #6a6c72);
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

.import-config-section {
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  text-align: center;
}

.import-btn {
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--border-radius-md);
  padding: 0.75rem 1.5rem;
  cursor: pointer;
  transition: var(--transition-base);
  color: var(--color-text-primary);
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 500;
}

.import-btn:hover:not(:disabled) {
  background: var(--color-bg-active);
  border-color: var(--color-primary);
  transform: translateY(-2px);
}

.import-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.import-btn i {
  font-size: 1.1rem;
}

.import-help {
  color: var(--color-text-muted);
  font-size: 0.875rem;
  margin-top: 0.5rem;
  margin-bottom: 0;
}

.fa-spinner.fa-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
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

@media (max-width: 768px) {
  .welcome-card {
    padding: 1.5rem;
    margin: 0 1rem;
  }

  .welcome-card h1 {
    font-size: 2rem;
  }

  .welcome-subtitle {
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

  .import-config-section {
    margin-top: 1.5rem;
    padding-top: 1.5rem;
  }

  .import-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
