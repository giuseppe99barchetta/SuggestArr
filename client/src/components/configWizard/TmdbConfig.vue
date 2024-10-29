<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">TMDB Configuration</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">
            You can get your TMDB API Key by signing up at 
            <a href="https://www.themoviedb.org/" class="text-indigo-400">The Movie Database</a>.
        </p>

        <!-- TMDB API Key Input -->
        <label for="TMDB_API_KEY" class="block text-xs sm:text-sm font-semibold text-gray-300">TMDB API Key:</label>
        <div class="flex flex-col sm:flex-row items-start sm:items-center">
            <input type="text" :value="config.TMDB_API_KEY" 
                   @input="$emit('update-config', 'TMDB_API_KEY', $event.target.value)"
                   class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2 mb-4 sm:mb-0 sm:mr-2"
                   id="TMDB_API_KEY" placeholder="Enter your TMDB API Key">
            <button type="button" @click="testTmdbApi" :disabled="tmdbTestState.isTesting"
                    :class="{
                        'bg-green-500 hover:bg-green-600': tmdbTestState.status === 'success',
                        'bg-red-500 hover:bg-red-600': tmdbTestState.status === 'fail',
                        'bg-blue-500 hover:bg-blue-600': tmdbTestState.status === null
                    }"
                    class="text-white px-4 py-2 rounded-lg shadow-md w-full sm:w-auto">
                <i v-if="tmdbTestState.isTesting" class="fas fa-spinner fa-spin"></i>
                <i v-else-if="tmdbTestState.status === 'success'" class="fas fa-check"></i>
                <i v-else-if="tmdbTestState.status === 'fail'" class="fas fa-times"></i>
                <i v-else class="fas fa-play"></i>
            </button>
        </div>

        <!-- Error Message -->
        <div v-if="tmdbTestState.status === 'fail'" class="bg-gray-800 border border-red-500 text-red-500 px-4 py-3 rounded-lg mt-4" role="alert">
            <span class="block sm:inline">Failed to validate TMDB API Key.</span>
        </div>

        <!-- Navigation Buttons -->
        <div class="flex justify-between mt-8 space-x-4">
            <button @click="$emit('previous-step')" 
                    class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">
                Back
            </button>
            <button @click="$emit('next-step')" :disabled="tmdbTestState.status !== 'success'" 
                    class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full"
                    :class="{ 'opacity-50 cursor-not-allowed': tmdbTestState.status !== 'success' }">
                Next Step
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
                status: null, // 'success', 'fail', or null (not tested)
                isTesting: false
            }
        };
    },
    methods: {
        testTmdbApi() {
            this.tmdbTestState.isTesting = true;
            this.tmdbTestState.status = null; // Reset status before the test
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
        },
        autoTestTmdbApi() {
            if (this.config.TMDB_API_KEY) {
                this.testTmdbApi(); // Automatically test the API if the key is present
            }
        }
    },
    mounted() {
        this.autoTestTmdbApi(); // Trigger auto-test on mount if the API key exists
    }
};
</script>
