<template>
    <div class="config-section">
        <h3 class="section-title">Request Service Configuration</h3>
        <p class="section-description">
            Connect to Overseerr or Jellyseerr to manage content requests automatically.
        </p>

        <!-- Connection Settings Card -->
        <div class="settings-card">
            <h4 class="card-title">Connection Settings</h4>

            <!-- Server URL Input -->
            <div class="form-group">
                <label for="SEER_API_URL" class="form-label">
                    Server URL
                </label>
                <input type="url" :value="config[`SEER_API_URL`]" @input="handleUrlInput($event.target.value)"
                    @blur="updateSeerUrl($event.target.value)" class="form-input" id="SEER_API_URL"
                    placeholder="http://overseerr.example.com:5055">
                <p class="form-help">
                    <i class="fas fa-info-circle"></i>
                    Example: http://192.168.1.100:5055 or https://overseerr.example.com
                </p>
            </div>

            <!-- API Key Input with Test Button -->
            <div class="form-group">
                <label for="SEER_TOKEN" class="form-label">
                    API Key
                </label>
                <div class="input-group">
                    <input type="password" :value="config[`SEER_TOKEN`]" @input="handleTokenInput($event.target.value)"
                        :disabled="testState.isTesting" class="form-input" id="SEER_TOKEN"
                        placeholder="Your Overseerr/Jellyseerr API Key">

                    <button type="button" @click="testApi" :disabled="testState.isTesting || !canTest" :class="[
                          'btn btn-test',
                          {
                            'btn-success': testState.status === 'success',
                            'btn-danger': testState.status === 'fail',
                            'btn-primary': testState.status === null && canTest,
                            'btn-disabled': !canTest
                          }
                        ]">
                        <span v-if="testState.isTesting" class="btn-content">
                            <i class="fas fa-spinner fa-spin"></i>
                            <span class="hidden sm:inline">Testing</span>
                        </span>
                        <span v-else-if="testState.status === 'success'" class="btn-content">
                            <i class="fas fa-check"></i>
                            <span class="hidden sm:inline">Connected</span>
                        </span>
                        <span v-else-if="testState.status === 'fail'" class="btn-content">
                            <i class="fas fa-times"></i>
                            <span class="hidden sm:inline">Failed</span>
                        </span>
                        <span v-else class="btn-content">
                            <i class="fas fa-plug"></i>
                            <span class="hidden sm:inline">Connect</span>
                        </span>
                    </button>
                </div>

                <div class="help-section">
                    <button type="button" @click="showApiKeyHelp = !showApiKeyHelp" class="help-link">
                        <i class="fas fa-question-circle"></i>
                        How to get your API Key?
                    </button>

                    <div v-if="showApiKeyHelp"
                        class="help-content">
                        <ol class="help-list">
                            <li>Open Overseerr/Jellyseerr web interface</li>
                            <li>Navigate to Settings → General</li>
                            <li>Scroll to "API Key" section</li>
                            <li>Copy the API key and paste it above</li>
                        </ol>
                    </div>
                </div>
            </div>

            <!-- Success Message -->
            <div v-if="testState.status === 'success'"
                class="alert alert-success">
                <i class="fas fa-check-circle"></i>
                <span>Successfully connected! Found {{ users.length }} local user(s).</span>
            </div>

            <!-- Error Message -->
            <div v-if="testState.status === 'fail'"
                class="alert alert-danger"
                role="alert">
                <i class="fas fa-exclamation-circle"></i>
                <span>Failed to connect. Please verify your URL and API Key.</span>
            </div>
        </div>

        <!-- User Authentication Card -->
        <div v-if="testState.status === 'success'" class="settings-card">
            <h4 class="card-title">
                <i class="fas fa-user-shield"></i>
                User Authentication (Optional)
            </h4>
            <p class="section-description">
                Select a local user to make requests on their behalf. This is useful for manual approval workflows.
                If not configured, the administrator account will be used.
            </p>

            <div v-if="users.length > 0">
                <!-- User Selection -->
                <div class="form-group">
                    <label for="SEER_USER_NAME" class="form-label">
                        Select Local User
                    </label>
                    <BaseDropdown
                        v-model="selectedUser"
                        :options="userOptions"
                        placeholder="Select a user..."
                        id="SEER_USER_NAME"
                        @change="updateSeerUser"
                    />
                </div>

                <!-- Password Field -->
                <div class="form-group">
                    <label for="SEER_USER_PSW" class="form-label">
                        Password
                    </label>
                    <input type="password" v-model="userPassword"
                        @input="$emit('update-config', `SEER_USER_PSW`, userPassword)" class="form-input"
                        id="SEER_USER_PSW" placeholder="Enter password" autocomplete="new-password">
                </div>

                <!-- Authenticate Button -->
                <button @click="authenticateUser" :disabled="isAuthenticating || !selectedUser || !userPassword" :class="{
                    'btn-success': authenticated,
                    'btn-primary': !authenticated,
                }" class="btn w-full mt-4">
                    <i v-if="isAuthenticating" class="fas fa-spinner fa-spin"></i>
                    <i v-else-if="authenticated" class="fas fa-check-circle"></i>
                    <i v-else class="fas fa-sign-in-alt"></i>
                    <span v-if="isAuthenticating">Authenticating...</span>
                    <span v-else-if="authenticated">Authenticated Successfully</span>
                    <span v-else>Authenticate User</span>
                </button>
            </div>

            <!-- No Local Users Message -->
            <div v-else class="alert alert-warning">
                <i class="fas fa-exclamation-triangle"></i>
                <div>
                    <p class="font-semibold mb-1">No Local Users Found</p>
                    <p class="text-xs mb-2">
                        The administrator account will be used for requests. You can create a local user if needed.
                    </p>
                    <a :href="`${config[`SEER_API_URL`]}/users`" target="_blank" rel="noopener noreferrer"
                       class="link flex items-center gap-1">
                        <i class="fas fa-external-link-alt"></i>
                        Create a new local user
                    </a>
                </div>
            </div>
        </div>

        <!-- Navigation Buttons -->
        <div class="flex justify-between mt-8 gap-4">
            <button @click="$emit('previous-step')"
                class="btn-secondary w-full flex items-center justify-center gap-2 py-4 px-8">
                <i class="fas fa-arrow-left"></i>
                Back
            </button>

            <button @click="$emit('next-step')" :disabled="testState.status !== 'success'"
                class="btn-primary w-full flex items-center justify-center gap-2 py-4 px-8"
                :class="{ 'opacity-50 cursor-not-allowed': testState.status !== 'success' }">
                Next Step
                <i class="fas fa-arrow-right"></i>
            </button>
        </div>

    </div>

</template>

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

/* Input Group */
.input-group {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.link {
  color: var(--color-primary);
  text-decoration: none;
  border-bottom: 1px dotted var(--color-primary);
  transition: all 0.2s ease;
  font-size: 0.8125rem;
}

.link:hover {
  color: var(--color-primary-hover);
  border-bottom-style: solid;
}

.alert-warning {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid var(--color-warning);
  color: var(--color-warning);
}

/* Responsive */
@media (max-width: 768px) {
  .settings-card {
    padding: 1rem;
  }

  .input-group {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

<script>
import { testJellyseerApi, authenticateUser } from '../../api/api';
import BaseDropdown from '../common/BaseDropdown.vue';

export default {
    components: {
        BaseDropdown
    },
    props: ['config'],
    data() {
        return {
            users: [],
            selectedUser: null,
            userPassword: '',
            authenticated: false,
            isAuthenticating: false,
            testState: {
                status: null,
                isTesting: false
            },
            showApiKeyHelp: false
        };
    },
    computed: {
        canTest() {
            return this.config[`SEER_API_URL`] && this.config[`SEER_TOKEN`];
        },
        userOptions() {
            return this.users.map(user => ({
                label: `${user.name}${user.email ? ` (${user.email})` : ''}`,
                value: user.email || user.name
            }));
        }
    },
    methods: {
        handleUrlInput(value) {
            if (this.testState.status !== null) {
                this.testState.status = null;
                this.users = [];
                this.authenticated = false;
            }
        },
        
        handleTokenInput(value) {
            this.$emit('update-config', `SEER_TOKEN`, value);
            if (this.testState.status !== null) {
                this.testState.status = null;
                this.users = [];
                this.authenticated = false;
            }
        },

        autoTestAndAuthenticate() {
            if (this.canTest) {
                this.testApi();
            }

            if (this.config[`SEER_USER_NAME`] && this.config[`SEER_USER_PSW`]) {
                this.userPassword = this.config[`SEER_USER_PSW`];
                this.selectedUser = this.config[`SEER_USER_NAME`];
                this.authenticated = true;
            }
        },

        testApi() {
            if (!this.canTest) return;
            
            this.testState.isTesting = true;
            this.testState.status = null;
            
            testJellyseerApi(this.config[`SEER_API_URL`], this.config[`SEER_TOKEN`])
                .then(response => {
                    this.users = response.data.users.filter(user => user.isLocal);
                    this.testState.status = 'success';
                    this.loadSelectedUser();
                })
                .catch(error => {
                    console.error('Error testing API:', error);
                    this.testState.status = 'fail';
                    this.users = [];
                })
                .finally(() => {
                    this.testState.isTesting = false;
                });
        },

        authenticateUser() {
            if (!this.selectedUser || !this.userPassword) return;
            
            this.isAuthenticating = true;
            
            authenticateUser(
                this.config[`SEER_API_URL`], 
                this.config[`SEER_TOKEN`], 
                this.config[`SEER_USER_NAME`], 
                this.userPassword
            )
                .then((response) => {
                    this.authenticated = true;
                    this.$emit('update-config', 'SEER_SESSION_TOKEN', response.data.session_token);
                    this.$toast.open({
                        message: '✅ User authenticated successfully!',
                        type: 'success',
                        duration: 3000,
                        position: 'top-right'
                    });
                })
                .catch(error => {
                    console.error('Authentication error:', error);
                    this.authenticated = false;
                    this.$toast.open({
                        message: '❌ Incorrect username or password',
                        type: 'error',
                        duration: 5000,
                        position: 'top-right'
                    });
                })
                .finally(() => {
                    this.isAuthenticating = false;
                });
        },

        updateSeerUser() {
            if (this.selectedUser) {
                this.$emit('update-config', 'SEER_USER_NAME', this.selectedUser);
                this.authenticated = false; // Reset auth status when user changes
            }
        },

        updateSeerUrl(url) {
            const trimmedUrl = url.trim().replace(/\/+$/, '');
            this.$emit('update-config', 'SEER_API_URL', trimmedUrl);
        },

        loadSelectedUser() {
            if (this.config.SEER_USER_NAME) {
                this.selectedUser = this.config.SEER_USER_NAME;
            }
            if (this.config.SEER_USER_PSW) {
                this.userPassword = this.config.SEER_USER_PSW;
            }
        }
    },
    mounted() {
        this.autoTestAndAuthenticate();
    }
};
</script>
