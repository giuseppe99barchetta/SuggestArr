<template>
  <div class="settings-database">
    <div class="section-header">
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

        <div class="form-group">
          <label for="dbType">Database Type</label>
          <select
            id="dbType"
            v-model="localConfig.DB_TYPE"
            class="form-control"
            :disabled="isLoading"
            @change="onDbTypeChange"
          >
            <option value="sqlite">SQLite (Default)</option>
            <option value="postgres">PostgreSQL</option>
            <option value="mysql">MySQL/MariaDB</option>
          </select>
          <small class="form-help">
            SQLite is suitable for most users. PostgreSQL or MySQL recommended for production environments.
          </small>
        </div>

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
export default {
  name: 'SettingsDatabase',
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
  },
  emits: ['save-section', 'test-connection'],
  data() {
    return {
      localConfig: {},
      originalConfig: {},
      showPostgresPassword: false,
      showMysqlPassword: false,
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
      },
    },
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
      } else if (this.localConfig.DB_TYPE === 'postgres') {
        this.localConfig.DB_PORT = this.localConfig.DB_PORT || 5432;
      } else if (this.localConfig.DB_TYPE === 'mysql') {
        this.localConfig.DB_PORT = this.localConfig.DB_PORT || 3306;
      }
    },

    async testDatabaseConnection() {
      try {
        await this.$emit('test-connection', 'database', {
          DB_TYPE: this.localConfig.DB_TYPE,
          DB_HOST: this.localConfig.DB_HOST,
          DB_PORT: this.localConfig.DB_PORT,
          DB_NAME: this.localConfig.DB_NAME,
          DB_USER: this.localConfig.DB_USER,
          DB_PASSWORD: this.localConfig.DB_PASSWORD,
        });
      } catch (error) {
        console.error('Error testing database connection:', error);
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
  color: #fff;
}

.section-header {
  margin-bottom: 2rem;
}

.section-header h2 {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
  color: #fff;
}

.section-header p {
  color: #9ca3af;
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
  border-radius: 0.75rem;
  padding: 1.5rem;
}

.settings-group.warning {
  border-color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
}

.settings-group h3 {
  font-size: 1.2rem;
  margin-bottom: 1rem;
  color: #fff;
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
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #e5e7eb;
}

.form-control {
  width: 100%;
  padding: 0.75rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 0.5rem;
  color: #fff;
  font-size: 1rem;
  transition: all 0.3s ease;
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  background: rgba(255, 255, 255, 0.15);
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

.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: #9ca3af;
  line-height: 1.4;
}

.db-info {
  margin-top: 1rem;
}

.info-box {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 0.5rem;
  padding: 1rem;
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}

.info-box i {
  color: #3b82f6;
  margin-top: 0.25rem;
}

.info-box strong {
  color: #3b82f6;
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
  border-radius: 0.5rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
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
  background: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-outline {
  background: transparent;
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.btn-outline:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
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