<template>
    <div>
        <h3 class="text-xl font-bold text-gray-200 mb-2">Request Service Configuration</h3>
        <p class="text-sm text-gray-400 mb-6">
            Connect to Overseerr or Jellyseerr to manage content requests automatically.
        </p>

        <!-- Server URL Input -->
        <div class="mb-6">
            <label for="SEER_API_URL" class="block text-sm font-semibold text-gray-300 mb-2">
                Server URL
            </label>
            <input 
                type="url" 
                :value="config[`SEER_API_URL`]" 
                @input="handleUrlInput($event.target.value)"
                @blur="updateSeerUrl($event.target.value)"
                class="form-input"
                id="SEER_API_URL"
                placeholder="http://overseerr.example.com:5055">
            <p class="text-xs text-gray-500 mt-2">
                <i class="fas fa-info-circle"></i> 
                Example: http://192.168.1.100:5055 or https://overseerr.example.com
            </p>
        </div>

        <!-- API Key Input with Test Button -->
        <div class="mb-6">
            <label for="SEER_TOKEN" class="block text-sm font-semibold text-gray-300 mb-2">
                API Key
            </label>
            <div class="flex flex-row items-center gap-2">
                <input 
                    type="password" 
                    :value="config[`SEER_TOKEN`]"
                    @input="handleTokenInput($event.target.value)"
                    :disabled="testState.isTesting"
                    class="form-input"
                    id="SEER_TOKEN"
                    placeholder="Your Overseerr/Jellyseerr API Key">
                
                <button 
                    type="button" 
                    @click="testApi" 
                    :disabled="testState.isTesting || !canTest"
                    :class="{
                        'bg-green-500 hover:bg-green-600': testState.status === 'success',
                        'bg-red-500 hover:bg-red-600': testState.status === 'fail',
                        'bg-purple-500 hover:bg-purple-600': testState.status === null && canTest,
                        'bg-gray-500 cursor-not-allowed': !canTest
                    }"
                    class="text-white px-6 h-12 rounded-lg shadow-md flex items-center justify-center 
                           flex-shrink-0 transition-all duration-200 min-w-[120px]
                           disabled:opacity-50 disabled:cursor-not-allowed">
                    <span v-if="testState.isTesting" class="flex items-center gap-2">
                        <i class="fas fa-spinner fa-spin"></i>
                        <span class="hidden sm:inline">Testing</span>
                    </span>
                    <span v-else-if="testState.status === 'success'" class="flex items-center gap-2">
                        <i class="fas fa-check"></i>
                        <span class="hidden sm:inline">Connected</span>
                    </span>
                    <span v-else-if="testState.status === 'fail'" class="flex items-center gap-2">
                        <i class="fas fa-times"></i>
                        <span class="hidden sm:inline">Failed</span>
                    </span>
                    <span v-else class="flex items-center gap-2">
                        <i class="fas fa-plug"></i>
                        <span class="hidden sm:inline">Connect</span>
                    </span>
                </button>
            </div>
            
            <div class="mt-2">
                <button 
                    type="button"
                    @click="showApiKeyHelp = !showApiKeyHelp"
                    class="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 
                           bg-transparent border-none p-0 shadow-none font-normal">
                    <i class="fas fa-question-circle"></i>
                    How to get your API Key?
                </button>
                
                <div v-if="showApiKeyHelp" class="mt-3 p-3 bg-gray-800 border border-gray-600 rounded-lg text-xs text-gray-300">
                    <ol class="list-decimal list-inside space-y-1">
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
             class="bg-green-900 bg-opacity-30 border border-green-500 text-green-400 px-4 py-3 rounded-lg mb-6 flex items-center gap-2">
            <i class="fas fa-check-circle"></i>
            <span>Successfully connected! Found {{ users.length }} local user(s).</span>
        </div>

        <!-- Error Message -->
        <div v-if="testState.status === 'fail'"
            class="bg-red-900 bg-opacity-30 border border-red-500 text-red-400 px-4 py-3 rounded-lg mb-6 flex items-center gap-2"
            role="alert">
            <i class="fas fa-exclamation-circle"></i>
            <span>Failed to connect. Please verify your URL and API Key.</span>
        </div>

        <!-- User Authentication Section -->
        <div v-if="testState.status === 'success'" class="mb-6">
            <div class="bg-purple-900 bg-opacity-20 border border-purple-500 rounded-lg p-4 mb-4">
                <h4 class="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
                    <i class="fas fa-user-shield"></i>
                    User Authentication (Optional)
                </h4>
                <p class="text-xs text-gray-400">
                    Select a local user to make requests on their behalf. This is useful for manual approval workflows. 
                    If not configured, the administrator account will be used.
                </p>
            </div>

            <div v-if="users.length > 0">
                <!-- User Selection -->
                <div class="mb-4">
                    <label for="SEER_USER_NAME" class="block text-sm font-semibold text-gray-300 mb-2">
                        Select Local User
                    </label>
                    <select 
                        v-model="selectedUser" 
                        @change="updateSeerUser"
                        class="form-input"
                        id="SEER_USER_NAME">
                        <option :value="null" disabled>Select a user...</option>
                        <option v-for="user in users" :key="user.name" :value="user">
                            {{ user.name }} {{ user.email ? `(${user.email})` : '' }}
                        </option>
                    </select>
                </div>

                <!-- Password Field -->
                <div class="mb-4">
                    <label for="SEER_USER_PSW" class="block text-sm font-semibold text-gray-300 mb-2">
                        Password
                    </label>
                    <input 
                        type="password" 
                        v-model="userPassword" 
                        @input="$emit('update-config', `SEER_USER_PSW`, userPassword)"
                        class="form-input"
                        id="SEER_USER_PSW"
                        placeholder="Enter password"
                        autocomplete="new-password">
                </div>

                <!-- Authenticate Button -->
                <button 
                    @click="authenticateUser" 
                    :disabled="isAuthenticating || !selectedUser || !userPassword"
                    :class="{
                        'bg-green-500 hover:bg-green-600': authenticated,
                        'bg-purple-600 hover:bg-purple-500': !authenticated,
                    }"
                    class="text-white font-bold py-3 px-6 rounded-lg w-full transition-all duration-200
                           disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2">
                    <i v-if="isAuthenticating" class="fas fa-spinner fa-spin"></i>
                    <i v-else-if="authenticated" class="fas fa-check-circle"></i>
                    <i v-else class="fas fa-sign-in-alt"></i>
                    <span v-if="isAuthenticating">Authenticating...</span>
                    <span v-else-if="authenticated">Authenticated Successfully</span>
                    <span v-else>Authenticate User</span>
                </button>
            </div>

            <!-- No Local Users Message -->
            <div v-else class="bg-yellow-900 bg-opacity-20 border border-yellow-500 rounded-lg p-4">
                <div class="flex items-start gap-3">
                    <i class="fas fa-exclamation-triangle text-yellow-500 mt-1"></i>
                    <div>
                        <p class="text-sm text-yellow-400 font-semibold mb-1">No Local Users Found</p>
                        <p class="text-xs text-gray-400 mb-2">
                            The administrator account will be used for requests. You can create a local user if needed.
                        </p>
                        <a 
                            :href="`${config[`SEER_API_URL`]}/users`" 
                            target="_blank" 
                            rel="noopener noreferrer"
                            class="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 
                                   bg-transparent border-none p-0 shadow-none font-normal">
                            <i class="fas fa-external-link-alt"></i>
                            Create a new local user
                        </a>
                    </div>
                </div>
            </div>
        </div>

        <!-- Navigation Buttons -->
        <div class="flex justify-between mt-8 gap-4">
            <button 
                @click="$emit('previous-step')"
                class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full 
                       transition-colors duration-200">
                <i class="fas fa-arrow-left mr-2"></i>Back
            </button>
            <button 
                @click="$emit('next-step')"
                :disabled="testState.status !== 'success'"
                class="bg-purple-600 hover:bg-purple-500 text-white font-bold py-4 px-8 rounded-lg w-full
                       transition-colors duration-200"
                :class="{ 'opacity-50 cursor-not-allowed': testState.status !== 'success' }">
                Next Step<i class="fas fa-arrow-right ml-2"></i>
            </button>
        </div>
    </div>
</template>
<style scoped>
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
  width: 100%;           /* Forza l'input a occupare tutto il contenitore */
  display: block;         /* Si assicura che si comporti come un blocco */
  box-sizing: border-box;
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
</style>
<script>
import { testJellyseerApi, authenticateUser } from '../../api/api';

export default {
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
                this.selectedUser = { name: this.config[`SEER_USER_NAME`] };
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
                const userIdentifier = this.selectedUser.email || this.selectedUser.name;
                this.$emit('update-config', 'SEER_USER_NAME', userIdentifier);
                this.authenticated = false; // Reset auth status when user changes
            }
        },

        updateSeerUrl(url) {
            const trimmedUrl = url.trim().replace(/\/+$/, '');
            this.$emit('update-config', 'SEER_API_URL', trimmedUrl);
        },

        loadSelectedUser() {
            if (this.config.SEER_USER_NAME) {
                this.selectedUser = this.users.find(
                    user => user.name === this.config.SEER_USER_NAME || 
                            user.email === this.config.SEER_USER_NAME
                );
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
