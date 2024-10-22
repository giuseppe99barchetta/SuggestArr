<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">Step 3: {{ serviceName }} API Details</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">To obtain your {{ serviceName }} API Key, open the {{ serviceName }} interface,
            navigate to Settings, locate the "API Key" section, and copy your key for use in this configuration.</p>

        <!-- {{ serviceName }} API URL -->
        <label :for="`SEER_API_URL`" class="block text-xs sm:text-sm font-semibold text-gray-300">{{ serviceName }}
            URL:</label>
        <input type="text" :value="config[`SEER_API_URL`]" 
            @input="$emit('update-config', `SEER_API_URL`, $event.target.value)"
            class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" 
            :placeholder="`http://your-${serviceName.toLowerCase()}-url`">

        <!-- {{ serviceName }} API Key -->
        <label :for="`SEER_TOKEN`" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">{{ serviceName }} API
            Key:</label>
        <div class="flex flex-col sm:flex-row items-start sm:items-center">
            <input type="text" :value="config[`SEER_TOKEN`]"
                @input="$emit('update-config', `SEER_TOKEN`, $event.target.value)"
                class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2 mb-4 sm:mb-0 sm:mr-2"
                :placeholder="`Enter your ${serviceName} API Key`">
            <button type="button" @click="testApi" :disabled="testState.isTesting" 
                :class="{
                    'bg-green-500 hover:bg-green-600': testState.status === 'success',
                    'bg-red-500 hover:bg-red-600': testState.status === 'fail',
                    'bg-blue-500 hover:bg-blue-600': testState.status === null
                }" 
                class="text-white px-4 py-2 rounded-lg shadow-md w-full sm:w-auto">
                <i v-if="testState.isTesting" class="fas fa-spinner fa-spin"></i>
                <i v-else-if="testState.status === 'success'" class="fas fa-check"></i>
                <i v-else-if="testState.status === 'fail'" class="fas fa-times"></i>
                <i v-else class="fas fa-play"></i>
            </button>
        </div>

        <!-- Error message for failed validation -->
        <div v-if="testState.status === 'fail'"
            class="bg-gray-800 border border-red-500 text-red-500 px-4 py-3 rounded-lg mt-4" role="alert">
            <span class="block sm:inline">Failed to validate {{ serviceName }} Key.</span>
        </div>

        <!-- {{ serviceName }} user selection -->
        <div v-if="testState.status === 'success'" class="mt-4">
            <label :for="`SEER_USER_NAME`" class="block text-xs sm:text-sm font-semibold text-gray-300">Select a local
                User:</label>

            <p class="text-xs sm:text-sm text-gray-400 mb-2">
                Only local users of {{ serviceName }} can be selected. Selecting a specific user is useful if you want to
                disable automatic approval of requests and manually approve them before automatic downloading.
                This step is optional. If no user is selected, the administrator account will be used to make requests.
            </p>

            <!-- If no local users are available, show a message and disable the select field -->
            <div v-if="users.length > 0">
                <select v-model="selectedUser" @change="updateSeerUser"
                    class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2">
                    <option v-for="user in users" :key="user.id" :value="user">{{ user.name }}</option>
                </select>

                <!-- Password field -->
                <label :for="`SEER_USER_PSW`"
                    class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Password:</label>
                <input type="password" v-model="userPassword" 
                    @input="$emit('update-config', `SEER_USER_PSW`, userPassword)"
                    class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                    :placeholder="`Enter your password`">

                <!-- Authenticate button -->
                <button @click="authenticateUser" :disabled="isAuthenticating || authenticated" :class="{
                    'bg-green-500 hover:bg-green-600': authenticated,
                    'bg-indigo-600 hover:bg-indigo-500': !authenticated,
                    'opacity-50 cursor-not-allowed': isAuthenticating
                }" class="text-white font-bold py-4 px-8 rounded-lg w-full mt-4">
                    <i v-if="isAuthenticating" class="fas fa-spinner fa-spin"></i>
                    <span v-else-if="authenticated">Logged In</span>
                    <span v-else>Authenticate</span>
                </button>

            </div>
            <div v-else>
                <p class="text-xs sm:text-sm text-red-500">
                    No local users available. The administrator account will be used for requests.
                    <a :href="`${config[`SEER_API_URL`]}/users`" target="_blank" class="text-blue-400 underline">
                        Create a new local user here.
                    </a>
                </p>
            </div>

        </div>

        <!-- Navigation buttons -->
        <div class="flex justify-between mt-8 space-x-4">
            <button @click="$emit('previous-step')"
                class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">Back</button>
            <button @click="$emit('next-step')"
                class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full"
                :disabled="testState.status !== 'success'">
                Next Step
            </button>
        </div>
    </div>
</template>

<script>
import { testJellyseerApi, authenticateUser } from '../../api/api';

export default {
    props: ['config'],
    data() {
        return {
            users: [],   // Users list will be filtered for local users
            selectedUser: '',     // Selected user for authentication
            userPassword: '',     // Password for selected user
            authenticated: false, // Authentication state
            isAuthenticating: false, // Authentication loading state
            testState: {
                status: null, // 'success', 'fail', or null (not tested)
                isTesting: false
            }
        };
    },
    computed: {
        serviceName() {
            // Determine if it's Jellyseer or Overseer based on the selected media server
            return this.config.SELECTED_SERVICE === 'plex' ? 'Overseer' : 'Jellyseer';
        }
    },
    methods: {
        // Test Jellyseer or Overseer API and filter local users
        testApi() {
            this.testState.isTesting = true;
            this.testState.status = null; // Reset status before the test
            testJellyseerApi(this.config[`SEER_API_URL`], this.config[`SEER_TOKEN`])
                .then(response => {
                    this.users = response.data.users.filter(user => user.isLocal); // Filter local users
                    this.testState.status = 'success';
                })
                .catch(() => {
                    this.testState.status = 'fail';
                })
                .finally(() => {
                    this.testState.isTesting = false;
                });
        },
        // Authenticate the selected user
        authenticateUser() {
            this.isAuthenticating = true;
            authenticateUser(this.config[`SEER_API_URL`], this.config[`SEER_TOKEN`], this.config[`SEER_USER_NAME`], this.userPassword)
                .then(() => {
                    this.authenticated = true;
                })
                .catch(() => {
                    this.authenticated = false;
                })
                .finally(() => {
                    this.isAuthenticating = false;
                });
        },
        updateSeerUser() {
            const userIdentifier = this.selectedUser.email ? this.selectedUser.email : this.selectedUser.name;
            this.$emit('update-config', 'SEER_USER_NAME', userIdentifier);
        }
    }
};
</script>
