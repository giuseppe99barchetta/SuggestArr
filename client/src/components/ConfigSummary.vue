<template>
    <div class="wizard-container" :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">
        <div class="wizard-content custom-width">
            <h2 class="text-3xl font-bold text-gray-200 mb-6 text-center">SuggestArr Summary</h2>
            <div class="space-y-6">
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Selected service:</label>
                    <p class="text-gray-200">{{ capitalizeFirstLetter(config.SELECTED_SERVICE) }}</p>
                </div>
                <!-- Display Plex or Jellyfin URL based on selected service -->
                <div class="bg-gray-700 p-4 rounded-lg shadow-md" v-if="config.SELECTED_SERVICE === 'plex'">
                    <label class="block text-sm font-semibold text-gray-300">Plex URL:</label>
                    <p class="text-gray-200">{{ config.PLEX_API_URL }}</p>
                </div>
                <div class="bg-gray-700 p-4 rounded-lg shadow-md" v-else>
                    <label class="block text-sm font-semibold text-gray-300">{{ capitalizeFirstLetter(config.SELECTED_SERVICE) }} URL:</label>
                    <p class="text-gray-200">{{ config.JELLYFIN_API_URL }}</p>
                </div>
                <!-- Display Overseer or Jellyseer URL -->
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Jellyseer/Overseer URL:</label>
                    <p class="text-gray-200">{{ config.SEER_API_URL }}</p>
                </div>
                <!-- Display Max Similar Movies -->
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Max Similar Movies:</label>
                    <p class="text-gray-200">{{ config.MAX_SIMILAR_MOVIE }}</p>
                </div>
                <!-- Display Max Similar TV Shows -->
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Max Similar TV Shows:</label>
                    <p class="text-gray-200">{{ config.MAX_SIMILAR_TV }}</p>
                </div>
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Max Content to fetch for each content:</label>
                    <p class="text-gray-200">{{ config.MAX_CONTENT_CHECKS }}</p>
                </div>
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Search Size:</label>
                    <p class="text-gray-200">{{ config.SEARCH_SIZE }}</p>
                </div>
                <!-- Display Next Cron Run Time -->
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Next Cron Run in:</label>
                    <p class="text-gray-200">{{ nextCronRun }}</p>
                </div>
            </div>
            <!-- Edit Configuration and Reset Buttons -->
            <div class="flex space-x-4 mt-8">
                <button @click="editConfig"
                    class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg shadow-lg transition-transform transform hover:scale-105">
                    Edit Configuration
                </button>
                <button @click="showResetPopup = true"
                    class="w-full bg-yellow-600 hover:bg-yellow-500 text-white font-bold py-4 px-8 rounded-lg shadow-lg transition-transform transform hover:scale-105">
                    Reset Configuration
                </button>
            </div>
            <!-- Force Run Button -->
            <button @click="forceRun"
                class="bg-red-600 hover:bg-red-500 text-white font-bold py-4 px-8 rounded-lg w-full mt-4 shadow-lg transition-transform transform hover:scale-105">
                <i v-if="isRunning" class="fas fa-spinner fa-spin"></i>
                <span v-else>Run Now</span>
            </button>

            <!-- Reset Confirmation Modal -->
            <div v-if="showResetPopup" class="fixed inset-0 flex items-center justify-center bg-gray-900 bg-opacity-75 z-50">
                <div class="bg-gray-800 p-6 rounded-lg shadow-lg border border-gray-700 max-w-md w-full">
                    <h3 class="text-xl font-semibold text-gray-200">Confirm Reset</h3>
                    <p class="mt-4 text-gray-400">Are you sure you want to reset the configuration? This action cannot be undone.</p>
                    <div class="flex justify-end mt-6 space-x-4">
                        <button @click="showResetPopup = false" class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-2 px-4 rounded-lg">Cancel</button>
                        <button @click="confirmReset" class="bg-red-600 hover:bg-red-500 text-white font-bold py-2 px-4 rounded-lg">Confirm</button>
                    </div>
                </div>
            </div>
            <Footer />
        </div>
    </div>
</template>


<script>
import axios from 'axios';
import cronParser from 'cron-parser';
import Footer from './AppFooter.vue';
import backgroundManager from '@/api/backgroundManager';
import { fetchRandomMovieImage } from '@/api/tmdbApi';

export default {
    components: {
        Footer,
    },
    mixins: [backgroundManager],
    props: {
        config: {
            type: Object,
            required: true
        }
    },
    data() {
        return {
            isRunning: false, // Track the running state for the 'Run Now' button
            nextCronRun: '',   // To store the time remaining until next cron run
            showResetPopup: false,
            backgroundImageUrl: '',

        };
    },
    mounted() {
        this.calculateNextCronRun();
        if (!this.config.TMDB_API_KEY) {
            this.startDefaultImageRotation();
        } else {
            this.startBackgroundImageRotation(fetchRandomMovieImage, this.config.TMDB_API_KEY);
        }
    },
    methods: {
        capitalizeFirstLetter(text) {
            if (!text) return '';
            return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
        },
        calculateNextCronRun() {
            try {
                const interval = cronParser.parseExpression(this.config.CRON_TIMES);
                const nextRun = interval.next();
                const now = new Date();
                const timeDiff = nextRun.getTime() - now.getTime(); // Get difference in milliseconds

                const hours = Math.floor(timeDiff / (1000 * 60 * 60));
                const minutes = Math.floor((timeDiff % (1000 * 60 * 60)) / (1000 * 60));
                const seconds = Math.floor((timeDiff % (1000 * 60)) / 1000);

                this.nextCronRun = `${hours}h ${minutes}m ${seconds}s`;
            } catch (err) {
                console.error('Error parsing cron expression:', err);
                this.nextCronRun = 'Error calculating next run time';
            }
        },
        editConfig() {
            this.$emit('edit-config');
        },
        forceRun() {
            this.isRunning = true;
            axios.post('/api/automation/force_run', this.config)
                .then(
                    this.$toast.open({
                        message: 'Process started in background!',
                        pauseOnHover: true,
                        duration:5000
                    })
                )
                .catch(error => {
                    alert(`Error: ${error.response ? error.response.data.message : error.message}`); // Handle errors
                })
                .finally(() => {
                    this.isRunning = false; // Reset running state after completion
                });
        },
        confirmReset() {
            this.showResetPopup = false;
            axios.post('/api/config/reset')
                .then(window.location.reload())
                .catch(error => {
                    alert(`Error resetting configuration: ${error.response ? error.response.data.message : error.message}`);
                });
        },
        
    },
    beforeUnmount() {
        this.stopBackgroundImageRotation();
    },
};

</script>

<style scoped>
.custom-width {
    max-width: 600px; /* Puoi modificare questa larghezza in base alle tue esigenze */
    margin: 0 auto;   /* Per centrare il contenuto */
}
</style>
