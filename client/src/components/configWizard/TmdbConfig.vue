<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">TMDB Configuration</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">
            You can get your TMDB API Key by signing up at 
            <a href="https://www.themoviedb.org/" target="_blank" rel="noopener noreferrer" 
               class="text-indigo-400 hover:text-indigo-300 underline transition-colors">The Movie Database</a>.
        </p>

        <!-- TMDB API Key Input -->
        <label for="TMDB_API_KEY" class="block text-xs sm:text-sm font-semibold text-gray-300 mb-2">
            TMDB API Key:
        </label>
        <div class="flex flex-row items-center gap-2">
            <input type="text" 
                   :value="config.TMDB_API_KEY" 
                   @input="handleInput"
                   @keyup.enter="testTmdbApi"
                   :disabled="tmdbTestState.isTesting"
                   class="flex-1 h-10 bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 
                          focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                          disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                   id="TMDB_API_KEY" 
                   placeholder="Enter your TMDB API Key">
            
            <button type="button" 
                    @click="testTmdbApi" 
                    :disabled="tmdbTestState.isTesting || !config.TMDB_API_KEY"
                    :class="{
                        'bg-green-500 hover:bg-green-600': tmdbTestState.status === 'success',
                        'bg-red-500 hover:bg-red-600': tmdbTestState.status === 'fail',
                        'bg-blue-500 hover:bg-blue-600': tmdbTestState.status === null && config.TMDB_API_KEY,
                        'bg-gray-500 cursor-not-allowed': !config.TMDB_API_KEY
                    }"
                    class="text-white px-6 h-10 rounded-lg shadow-md flex items-center justify-center 
                           flex-shrink-0 transition-all duration-200 min-w-[100px]
                           disabled:opacity-50 disabled:cursor-not-allowed">
                <span v-if="tmdbTestState.isTesting" class="flex items-center gap-2">
                    <i class="fas fa-spinner fa-spin"></i>
                    <span class="hidden sm:inline">Testing</span>
                </span>
                <span v-else-if="tmdbTestState.status === 'success'" class="flex items-center gap-2">
                    <i class="fas fa-check"></i>
                    <span class="hidden sm:inline">Valid</span>
                </span>
                <span v-else-if="tmdbTestState.status === 'fail'" class="flex items-center gap-2">
                    <i class="fas fa-times"></i>
                    <span class="hidden sm:inline">Failed</span>
                </span>
                <span v-else class="flex items-center gap-2">
                    <i class="fas fa-play"></i>
                    <span class="hidden sm:inline">Test</span>
                </span>
            </button>
        </div>

        <!-- Success Message -->
        <div v-if="tmdbTestState.status === 'success'" 
             class="bg-green-900 bg-opacity-30 border border-green-500 text-green-400 px-4 py-3 rounded-lg mt-4 flex items-center gap-2" 
             role="alert">
            <i class="fas fa-check-circle"></i>
            <span class="block sm:inline">TMDB API Key validated successfully!</span>
        </div>

        <!-- Error Message -->
        <div v-if="tmdbTestState.status === 'fail'" 
             class="bg-red-900 bg-opacity-30 border border-red-500 text-red-400 px-4 py-3 rounded-lg mt-4 flex items-center gap-2" 
             role="alert">
            <i class="fas fa-exclamation-circle"></i>
            <span class="block sm:inline">Failed to validate TMDB API Key. Please check your key and try again.</span>
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
            this.$emit('update-config', 'TMDB_API_KEY', event.target.value);
            // Reset status when user modifies the key
            if (this.tmdbTestState.status !== null) {
                this.tmdbTestState.status = null;
            }
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
        },
        autoTestTmdbApi() {
            if (this.config.TMDB_API_KEY) {
                this.testTmdbApi();
            }
        }
    },
    mounted() {
        this.autoTestTmdbApi();
    }
};
</script>
