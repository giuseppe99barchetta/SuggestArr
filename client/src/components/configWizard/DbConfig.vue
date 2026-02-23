<template>
    <div class="config-section">
        <h3 class="section-title">Database Configuration</h3>
        <p class="section-description">
            Configure the database settings below to connect to your preferred database (PostgreSQL, MySQL/MariaDB, or SQLite). By default, SQLite is used for the standard configuration.
        </p>

        <!-- DB Type Selection -->
        <div class="form-group">
            <label for="DB_TYPE" class="form-label">Database Type</label>
            <BaseDropdown
              :model-value="config.DB_TYPE"
              :options="databaseOptions"
              placeholder="Select database type"
              id="DB_TYPE"
              @change="value => handleUpdate('DB_TYPE', value)"
            />
            <p class="form-help">
                <i class="fas fa-info-circle"></i>
                Select the database to store requests made from SuggestArr.
            </p>
        </div>

        <!-- Database Configuration Card -->
        <div v-if="config.DB_TYPE !== 'sqlite'" class="db-config-card">
            <h4 class="card-title">Connection Settings</h4>

            <!-- Host and Port in a row -->
            <div class="form-row">
                <div class="form-group flex-2">
                    <label for="DB_HOST" class="form-label">Host</label>
                    <input type="text" :value="config.DB_HOST"
                           @input="handleUpdate('DB_HOST', $event.target.value)"
                           class="form-input"
                           id="DB_HOST" placeholder="localhost">
                </div>

                <div class="form-group flex-1">
                    <label for="DB_PORT" class="form-label">Port</label>
                    <input type="number" :value="config.DB_PORT"
                           @input="handleUpdate('DB_PORT', $event.target.value)"
                           class="form-input"
                           id="DB_PORT" placeholder="5432">
                </div>
            </div>
            <p class="form-help">
                <i class="fas fa-info-circle"></i>
                Default ports: PostgreSQL (5432), MySQL/MariaDB (3306)
            </p>

            <!-- User and Password in a row -->
            <form @submit.prevent="handleSubmit">
                <div class="form-row">
                    <div class="form-group flex-1">
                        <label for="DB_USER" class="form-label">Username</label>
                        <input type="text" :value="config.DB_USER"
                               @input="handleUpdate('DB_USER', $event.target.value)"
                               class="form-input"
                               id="DB_USER" placeholder="root" autocomplete="username">
                    </div>

                    <div class="form-group flex-1">
                        <label for="DB_PASSWORD" class="form-label">Password</label>
                        <input type="password" :value="config.DB_PASSWORD"
                               @input="handleUpdate('DB_PASSWORD', $event.target.value)"
                               class="form-input"
                               id="DB_PASSWORD" placeholder="••••••••"  autocomplete="new-password">
                    </div>
                </div>
            </form>

            <!-- Database Name -->
            <div class="form-group">
                <label for="DB_NAME" class="form-label">Database Name</label>
                <input type="text" :value="config.DB_NAME"
                       @input="handleUpdate('DB_NAME', $event.target.value)"
                       class="form-input"
                       id="DB_NAME" placeholder="suggestarr">
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle"></i>
                    <span><strong>Important:</strong> The database must be created before connecting.</span>
                </div>
            </div>

            <!-- Error/Success Message -->
            <div v-if="dbError" class="alert alert-danger" role="alert">
                <i class="fas fa-exclamation-circle"></i>
                <span>{{ dbError }}</span>
            </div>
            <div v-if="dbSuccess" class="alert alert-success" role="alert">
                <i class="fas fa-check-circle"></i>
                <span>{{ dbSuccess }}</span>
            </div>

            <!-- Test Connection Button -->
            <button @click="testConnection"
                    :disabled="buttonText === 'Testing...'"
                    :class="[
                        'btn',
                        'btn-test-connection',
                        buttonText === 'Connection Successful!' ? 'btn-success' : 'btn-primary'
                    ]">
                <i v-if="buttonText === 'Testing...'" class="fas fa-spinner fa-spin"></i>
                <i v-else-if="buttonText === 'Connection Successful!'" class="fas fa-check"></i>
                <i v-else class="fas fa-plug"></i>
                {{ buttonText }}
            </button>
        </div>

        <!-- Navigation Buttons -->
        <div class="flex justify-between mt-8 gap-4">
            <button @click="$emit('previous-step')"
              class="btn-secondary w-full flex items-center justify-center gap-2 py-4 px-8">
              <i class="fas fa-arrow-left"></i>
              Back
            </button>

            <button @click="$emit('next-step')" :disabled="!isTestSuccessful"
              class="btn-primary w-full flex items-center justify-center gap-2 py-4 px-8"
              :class="{ 'opacity-50 cursor-not-allowed': !isTestSuccessful }">
              Next Step
              <i class="fas fa-arrow-right"></i>
            </button>
        </div>
    </div>
</template>

<script>
import axios from 'axios';
import BaseDropdown from '@/components/common/BaseDropdown.vue';

/* eslint-disable vue/no-mutating-props */
export default {
    components: {
        BaseDropdown
    },
    props: ['config'],
    data() {
        return {
            dbError: '',
            dbSuccess: '',
            buttonText: 'Test Connection',
            isTestSuccessful: true,
            databaseOptions: [
                { value: 'sqlite', label: 'SQLite (Default)' },
                { value: 'postgres', label: 'PostgreSQL' },
                { value: 'mysql', label: 'MySQL/MariaDB' }
            ]
        };
    },
    created() {
        if (!this.config.DB_TYPE) {
            this.config.DB_TYPE = 'sqlite';
            this.isTestSuccessful = true;
        }
    },
    watch: {
        isTested(newValue) {
            this.isNextDisabled = !newValue && this.config.DB_TYPE !== 'sqlite';
        }
    },
    methods: {
        handleUpdate(key, value) {
            this.$emit('update-config', key, value);
            if (key == 'DB_TYPE' && value == 'sqlite') {
                this.isTestSuccessful = true;
            } else {
                this.isTestSuccessful = false;
            }
        },
        async testConnection() {
            this.dbError = '';
            this.dbSuccess = '';
            this.buttonText = 'Testing...';

            try {
                const response = await axios.post('/api/config/test-db-connection', this.config);
                if (response.data.status == 'success') {
                    this.buttonText = 'Connection Successful!';
                    this.dbSuccess = 'Successfully connected to the database!';
                    this.isTestSuccessful = true;
                } else {
                    this.dbError = 'Failed to connect to the database.';
                    this.buttonText = 'Test Connection';
                    this.isTestSuccessful = false;
                }
            } catch (error) {
                this.dbError = 'Error connecting to the database: ' + error.message;
                this.buttonText = 'Test Connection';
                this.isTestSuccessful = false;
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

/* Database Config Card */
.db-config-card {
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--border-radius-md);
  padding: 1.5rem;
  margin-top: 1rem;
}

.card-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 1.25rem 0;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--color-border-light);
}

/* Form Row for side-by-side fields */
.form-row {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.form-row .form-group {
  margin-bottom: 0;
}

.form-row + .form-help {
  margin-top: 0.5rem;
  margin-bottom: 1rem;
}

.flex-1 {
  flex: 1;
}

.flex-2 {
  flex: 2;
}

/* Test Connection Button */
.btn-test-connection {
  width: 100%;
  margin-top: 0.5rem;
}

/* Alert Warning */
.alert-warning {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(217, 119, 6, 0.1) 100%);
  border-left: 3px solid var(--color-warning);
  border-radius: var(--border-radius-sm);
  font-size: 0.875rem;
  color: var(--color-warning);
  font-weight: 500;
}

.alert-warning i {
  color: var(--color-warning);
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

  .db-config-card {
    padding: 1rem;
  }
}
</style>
