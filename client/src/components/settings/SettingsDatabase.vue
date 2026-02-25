<template>
  <div class="settings-database">
    <div v-if="!wizardMode" class="section-header">
      <h2>Database Configuration</h2>
      <p>Configure your database connection settings</p>
    </div>

    <div class="settings-grid">
      <!-- Database Type Selection -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-database"></i>
          Database Type
        </h3>

        <BaseDropdown
          v-model="localConfig.DB_TYPE"
          :options="databaseOptions"
          label="Database Type"
          placeholder="Select database type"
          :help-text="'SQLite is suitable for most users. PostgreSQL or MySQL recommended for production environments.'"
          :disabled="isLoading"
          id="dbType"
          @change="onDbTypeChange"
        />

        <!-- SQLite Info -->
        <div v-if="localConfig.DB_TYPE === 'sqlite'" class="db-info">
          <div class="info-box">
            <i class="fas fa-info-circle"></i>
            <div>
              <strong>SQLite Configuration</strong>
              <p>
                Using SQLite for database storage. The database file will be stored at
                <code>config/config_files/requests.db</code>
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- PostgreSQL Configuration -->
      <div v-if="localConfig.DB_TYPE === 'postgres'" class="settings-group">
        <h3>
          <i class="fas fa-elephant"></i>
          PostgreSQL Settings
        </h3>

        <div class="form-group">
          <label for="postgresHost">Host</label>
          <input
            id="postgresHost"
            v-model="localConfig.DB_HOST"
            type="text"
            placeholder="localhost"
            class="form-control"
            :disabled="isLoading"
          />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="postgresPort">Port</label>
            <input
              id="postgresPort"
              v-model.number="localConfig.DB_PORT"
              type="number"
              placeholder="5432"
              class="form-control"
              :disabled="isLoading"
            />
          </div>
          <div class="form-group">
            <label for="postgresName">Database Name</label>
            <input
              id="postgresName"
              v-model="localConfig.DB_NAME"
              type="text"
              placeholder="suggestarr"
              class="form-control"
              :disabled="isLoading"
            />
          </div>
        </div>

        <div class="form-group">
          <label for="postgresUser">Username</label>
          <input
            id="postgresUser"
            v-model="localConfig.DB_USER"
            type="text"
            placeholder="postgres"
            class="form-control"
            :disabled="isLoading"
          />
        </div>

        <div class="form-group">
          <label for="postgresPassword">Password</label>
          <div class="input-group">
            <input
              id="postgresPassword"
              v-model="localConfig.DB_PASSWORD"
              :type="showPostgresPassword ? 'text' : 'password'"
              placeholder="Enter password"
              class="form-control"
              :disabled="isLoading"
            />
            <button
              @click="showPostgresPassword = !showPostgresPassword"
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="isLoading"
            >
              <i :class="showPostgresPassword ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
        </div>

        <div class="form-group">
          <button
            @click="testDatabaseConnection"
            class="btn btn-outline"
            :disabled="isLoading || !isPostgresConfigured || isTestingDatabase"
          >
            <i v-if="isTestingDatabase" class="fas fa-spinner fa-spin"></i>
            <i v-else class="fas fa-plug"></i>
            {{ isTestingDatabase ? 'Testing...' : 'Test Connection' }}
          </button>
        </div>
      </div>

      <!-- MySQL Configuration -->
      <div v-if="localConfig.DB_TYPE === 'mysql'" class="settings-group">
        <h3>
          <i class="fas fa-database"></i>
          MySQL/MariaDB Settings
        </h3>

        <div class="form-group">
          <label for="mysqlHost">Host</label>
          <input
            id="mysqlHost"
            v-model="localConfig.DB_HOST"
            type="text"
            placeholder="localhost"
            class="form-control"
            :disabled="isLoading"
          />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="mysqlPort">Port</label>
            <input
              id="mysqlPort"
              v-model.number="localConfig.DB_PORT"
              type="number"
              placeholder="3306"
              class="form-control"
              :disabled="isLoading"
            />
          </div>
          <div class="form-group">
            <label for="mysqlName">Database Name</label>
            <input
              id="mysqlName"
              v-model="localConfig.DB_NAME"
              type="text"
              placeholder="suggestarr"
              class="form-control"
              :disabled="isLoading"
            />
          </div>
        </div>

        <div class="form-group">
          <label for="mysqlUser">Username</label>
          <input
            id="mysqlUser"
            v-model="localConfig.DB_USER"
            type="text"
            placeholder="root"
            class="form-control"
            :disabled="isLoading"
          />
        </div>

        <div class="form-group">
          <label for="mysqlPassword">Password</label>
          <div class="input-group">
            <input
              id="mysqlPassword"
              v-model="localConfig.DB_PASSWORD"
              :type="showMysqlPassword ? 'text' : 'password'"
              placeholder="Enter password"
              class="form-control"
              :disabled="isLoading"
            />
            <button
              @click="showMysqlPassword = !showMysqlPassword"
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="isLoading"
            >
              <i :class="showMysqlPassword ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
        </div>

        <div class="form-group">
          <button
            @click="testDatabaseConnection"
            class="btn btn-outline"
            :disabled="isLoading || !isMysqlConfigured || isTestingDatabase"
          >
            <i v-if="isTestingDatabase" class="fas fa-spinner fa-spin"></i>
            <i v-else class="fas fa-plug"></i>
            {{ isTestingDatabase ? 'Testing...' : 'Test Connection' }}
          </button>
        </div>
      </div>

      <!-- Migration Notice -->
      <div v-if="hasDbTypeChanged && localConfig.DB_TYPE !== 'sqlite'" class="settings-group warning">
        <h3>
          <i class="fas fa-exclamation-triangle"></i>
          Database Migration Notice
        </h3>
        <div class="warning-content">
          <p>
            <strong>Warning:</strong> Changing the database type will require a manual migration of your existing data.
            Please backup your current configuration and data before proceeding.
          </p>
          <p>Recommended steps:</p>
          <ol>
            <li>Export your current configuration</li>
            <li>Backup your SQLite database file</li>
            <li>Create the new database in your chosen DBMS</li>
            <li>Import your configuration</li>
            <li>Test the new connection</li>
          </ol>
        </div>
      </div>
    </div>

    <!-- Save Button (hidden in wizard mode) -->
    <div v-if="!wizardMode" class="settings-actions">
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
import BaseDropdown from '@/components/common/BaseDropdown.vue';

export default {
  name: 'SettingsDatabase',
  components: {
    BaseDropdown
  },
  props: {
    config: {
      type: Object,
      required: true,
    },
    isLoading: {
      type: Boolean,
      default: false,
    },
    testingConnections: {
      type: Object,
      default: () => ({
        database: false,
      }),
    },
    // Wizard mode: hides save button and enables config-changed / validation-changed emits
    wizardMode: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['save-section', 'test-connection', 'validation-changed', 'config-changed'],
  data() {
    return {
      localConfig: {},
      originalConfig: {},
      showPostgresPassword: false,
      showMysqlPassword: false,
      databaseOptions: [
        { value: 'sqlite', label: 'SQLite (Default)' },
        { value: 'postgres', label: 'PostgreSQL' },
        { value: 'mysql', label: 'MySQL/MariaDB' }
      ]
    };
  },
  computed: {
    hasChanges() {
      return JSON.stringify(this.localConfig) !== JSON.stringify(this.originalConfig);
    },
    hasDbTypeChanged() {
      return this.localConfig.DB_TYPE !== this.originalConfig.DB_TYPE;
    },
    isPostgresConfigured() {
      return (
        this.localConfig.DB_HOST &&
        this.localConfig.DB_PORT &&
        this.localConfig.DB_NAME &&
        this.localConfig.DB_USER &&
        this.localConfig.DB_PASSWORD
      );
    },
    isMysqlConfigured() {
      return (
        this.localConfig.DB_HOST &&
        this.localConfig.DB_PORT &&
        this.localConfig.DB_NAME &&
        this.localConfig.DB_USER &&
        this.localConfig.DB_PASSWORD
      );
    },
    isTestingDatabase() {
      return this.testingConnections?.database || false;
    },
  },
  watch: {
    config: {
      immediate: true,
      handler(newConfig) {
        this.localConfig = { ...newConfig };
        this.originalConfig = { ...newConfig };
        // SQLite is always valid; emit immediately in wizard mode
        if (this.wizardMode && newConfig.DB_TYPE === 'sqlite') {
          this.$emit('validation-changed', true);
        }
      },
    },
  },
  beforeUnmount() {
    if (this.wizardMode) {
      this.$emit('config-changed', { ...this.localConfig });
    }
  },
  methods: {
    onDbTypeChange() {
      // Clear database-specific fields when switching types
      if (this.localConfig.DB_TYPE === 'sqlite') {
        this.localConfig.DB_HOST = null;
        this.localConfig.DB_PORT = null;
        this.localConfig.DB_NAME = null;
        this.localConfig.DB_USER = null;
        this.localConfig.DB_PASSWORD = null;
        // SQLite is always valid
        if (this.wizardMode) this.$emit('validation-changed', true);
      } else {
        if (this.localConfig.DB_TYPE === 'postgres') {
          this.localConfig.DB_PORT = this.localConfig.DB_PORT || 5432;
        } else if (this.localConfig.DB_TYPE === 'mysql') {
          this.localConfig.DB_PORT = this.localConfig.DB_PORT || 3306;
        }
        // Non-SQLite requires a successful test
        if (this.wizardMode) this.$emit('validation-changed', false);
      }
    },

    async testDatabaseConnection() {
      try {
        if (this.wizardMode) {
          // Self-contained test in wizard mode
          const axios = (await import('axios')).default;
          const res = await axios.post('/api/config/test-db-connection', {
            DB_TYPE: this.localConfig.DB_TYPE,
            DB_HOST: this.localConfig.DB_HOST,
            DB_PORT: this.localConfig.DB_PORT,
            DB_NAME: this.localConfig.DB_NAME,
            DB_USER: this.localConfig.DB_USER,
            DB_PASSWORD: this.localConfig.DB_PASSWORD,
          });
          if (res.status === 200) {
            if (this.$toast) this.$toast.success('Database connection successful!', { position: 'top-right', duration: 3000 });
            this.$emit('validation-changed', true);
          }
        } else {
          await this.$emit('test-connection', 'database', {
            DB_TYPE: this.localConfig.DB_TYPE,
            DB_HOST: this.localConfig.DB_HOST,
            DB_PORT: this.localConfig.DB_PORT,
            DB_NAME: this.localConfig.DB_NAME,
            DB_USER: this.localConfig.DB_USER,
            DB_PASSWORD: this.localConfig.DB_PASSWORD,
          });
        }
      } catch (error) {
        console.error('Error testing database connection:', error);
        if (this.wizardMode) {
          if (this.$toast) this.$toast.error('Database connection failed. Check your settings.', { position: 'top-right', duration: 5000 });
          this.$emit('validation-changed', false);
        }
      }
    },

    async saveSettings() {
      try {
        const dataToSave = {
          DB_TYPE: this.localConfig.DB_TYPE,
        };

        // Only include database-specific fields if not SQLite
        if (this.localConfig.DB_TYPE !== 'sqlite') {
          Object.assign(dataToSave, {
            DB_HOST: this.localConfig.DB_HOST,
            DB_PORT: this.localConfig.DB_PORT,
            DB_NAME: this.localConfig.DB_NAME,
            DB_USER: this.localConfig.DB_USER,
            DB_PASSWORD: this.localConfig.DB_PASSWORD,
          });
        }

        await this.$emit('save-section', {
          section: 'database',
          data: dataToSave,
        });

        this.originalConfig = { ...this.localConfig };
      } catch (error) {
        console.error('Error saving database settings:', error);
      }
    },

    async resetToDefaults() {
      const defaults = {
        DB_TYPE: 'sqlite',
        DB_HOST: null,
        DB_PORT: null,
        DB_USER: null,
        DB_PASSWORD: null,
        DB_NAME: null,
      };

      if (confirm('Are you sure you want to reset all database settings to their defaults?')) {
        this.localConfig = { ...this.localConfig, ...defaults };
        await this.saveSettings();
      }
    },
  },
};
</script>

<style scoped>
.settings-database {
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
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 2rem;
  margin-bottom: 2rem;
}

.settings-group {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--border-radius-md);
  padding: 1.5rem;
}

.settings-group.warning {
  border-color: var(--color-warning);
  background: rgba(245, 158, 11, 0.1);
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

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
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

.input-group {
  display: flex;
  gap: 0.5rem;
}

.input-group .form-control {
  flex: 1;
}

.select-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.select-wrapper .form-control {
  padding-right: 2.5rem;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
}

.chevron-indicator {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--color-text-muted);
  font-size: 0.75rem;
  transition: transform 0.2s ease;
}

.select-wrapper:focus-within .chevron-indicator {
  transform: translateY(-50%) rotate(180deg);
  color: var(--color-primary);
}

.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: var(--color-text-muted);
  line-height: 1.4;
}

.db-info {
  margin-top: 1rem;
}

.info-box {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: var(--border-radius-sm);
  padding: 1rem;
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}

.info-box i {
  color: var(--color-primary);
  margin-top: 0.25rem;
}

.info-box strong {
  color: var(--color-primary);
  margin-bottom: 0.5rem;
  display: block;
}

.info-box p {
  color: #e5e7eb;
  margin: 0;
  line-height: 1.5;
}

.info-box code {
  background: rgba(0, 0, 0, 0.3);
  padding: 0.2rem 0.4rem;
  border-radius: 0.25rem;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
}

.warning-content {
  color: #e5e7eb;
}

.warning-content p {
  margin-bottom: 1rem;
}

.warning-content ol {
  margin: 0;
  padding-left: 1.5rem;
}

.warning-content li {
  margin-bottom: 0.5rem;
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

  .form-row {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .input-group {
    flex-direction: column;
  }

  .info-box {
    flex-direction: column;
    text-align: center;
  }

  .settings-actions {
    flex-direction: column;
    align-items: stretch;
  }
}

/* Spinner animation */
.fa-spinner.fa-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Testing state button styling */
.btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.btn:disabled .fa-spinner {
  animation: spin 1s linear infinite;
}
</style>