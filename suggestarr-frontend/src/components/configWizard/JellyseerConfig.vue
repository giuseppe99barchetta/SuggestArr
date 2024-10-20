<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">Step 3: Jellyseer API Details</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">To get your Jellyseer API URL and Key, refer to your Jellyseer settings.</p>

        <label for="JELLYSEER_API_URL" class="block text-xs sm:text-sm font-semibold text-gray-300">Jellyseer URL:</label>
        <input type="text" :value="config.JELLYSEER_API_URL" @input="$emit('update-jellyseer-url', $event.target.value)"
               class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
               id="JELLYSEER_API_URL" placeholder="http://your-jellyseer-url">

        <label for="JELLYSEER_TOKEN" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Jellyseer API Key:</label>
        <div class="flex flex-col sm:flex-row items-start sm:items-center">
            <input type="text" :value="config.JELLYSEER_TOKEN" @input="$emit('update-jellyseer-token', $event.target.value)"
                   class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2 mb-4 sm:mb-0 sm:mr-2"
                   id="JELLYSEER_TOKEN" placeholder="Enter your Jellyseer API Key">
            <button type="button" @click="testJellyseerApi" :disabled="jellyseerTestState.isTesting"
                    :class="{
                        'bg-green-500 hover:bg-green-600': jellyseerTestState.status === 'success',
                        'bg-red-500 hover:bg-red-600': jellyseerTestState.status === 'fail',
                        'bg-blue-500 hover:bg-blue-600': jellyseerTestState.status === null
                    }"
                    class="text-white px-4 py-2 rounded-lg shadow-md w-full sm:w-auto">
                <i v-if="jellyseerTestState.isTesting" class="fas fa-spinner fa-spin"></i>
                <i v-else-if="jellyseerTestState.status === 'success'" class="fas fa-check"></i>
                <i v-else-if="jellyseerTestState.status === 'fail'" class="fas fa-times"></i>
                <i v-else class="fas fa-play"></i>
            </button>
        </div>

        <div v-if="jellyseerTestState.status === 'fail'" class="bg-gray-800 border border-red-500 text-red-500 px-4 py-3 rounded-lg mt-4" role="alert">
            <span class="block sm:inline">Failed to validate Jellyseer Key.</span>
        </div>

        <div v-if="jellyseerTestState.status === 'success'" class="mt-4">
            <label for="JELLYSEER_USER" class="block text-xs sm:text-sm font-semibold text-gray-300">Select User:</label>
            <select v-model="selectedUser" @change="$emit('update-jellyseer-user', selectedUser.name)" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2">
                <option v-for="user in jellyseerUsers" :key="user.id" :value="user">{{ user.name }}</option>
            </select>

            <label for="JELLYSEER_PASSWORD" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Password:</label>
            <input type="password" v-model="userPassword" @input="$emit('update-jellyseer-password', userPassword)" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" id="JELLYSEER_PASSWORD" placeholder="Enter your password">

            <button
                @click="authenticateUser"
                :disabled="isAuthenticating || authenticated"
                :class="{
                    'bg-green-500 hover:bg-green-600': authenticated,
                    'bg-indigo-600 hover:bg-indigo-500': !authenticated,
                    'opacity-50 cursor-not-allowed': isAuthenticating
                }"
                class="text-white font-bold py-4 px-8 rounded-lg w-full mt-4"
            >
                <i v-if="isAuthenticating" class="fas fa-spinner fa-spin"></i>
                <span v-else-if="authenticated">Logged In</span>
                <span v-else>Authenticate</span>
            </button>
        </div>

        <div class="flex justify-between mt-8 space-x-4">
            <button @click="$emit('previous-step')" class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">Back</button>
            <button @click="$emit('next-step')" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full">Next Step</button>
        </div>
    </div>
</template>

<script>
import { testJellyseerApi, authenticateUser } from '../../api/api';

export default {
    props: ['config'],
    data() {
        return {
            jellyseerUsers: [],
            selectedUser: '',
            userPassword: '',
            authenticated: false,
            isAuthenticating: false,
            jellyseerTestState: {
                status: null, // 'success', 'fail', or null (not tested)
                isTesting: false
            }
        };
    },
    methods: {
        testJellyseerApi() {
            this.jellyseerTestState.isTesting = true;
            this.jellyseerTestState.status = null; // Reset status before the test
            testJellyseerApi(this.config.JELLYSEER_API_URL, this.config.JELLYSEER_TOKEN)
                .then(response => {
                    this.jellyseerUsers = response.data.users;
                    this.jellyseerTestState.status = 'success';
                })
                .catch(() => {
                    this.jellyseerTestState.status = 'fail';
                })
                .finally(() => {
                    this.jellyseerTestState.isTesting = false;
                });
        },
        authenticateUser() {
            this.isAuthenticating = true;
            authenticateUser(this.config.JELLYSEER_API_URL, this.config.JELLYSEER_TOKEN, this.selectedUser.name, this.userPassword)
                .then(() => {
                    this.authenticated = true;
                })
                .catch(() => {
                    this.authenticated = false;
                })
                .finally(() => {
                    this.isAuthenticating = false;
                });
        }
    }
};
</script>
