<template>
    <div class="wizard-container" :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">
        <div class="wizard-content custom-width">
            <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank">
                <img src="@/assets/logo.png" alt="SuggestArr Logo" class="attached-logo mb-6 text-center">
            </a>
            <div class="space-y-6">
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
                <div class="flex flex-col sm:flex-row sm:space-x-4">
                    <!-- Max Similar Movies and TV Shows -->
                    <div class="bg-gray-700 p-4 rounded-lg shadow-md w-full sm:w-1/2">
                        <label class="block text-sm font-semibold text-gray-300">Max Similar Movies:</label>
                        <p class="text-gray-200">{{ config.MAX_SIMILAR_MOVIE }}</p>
                    </div>
                    <div class="bg-gray-700 p-4 rounded-lg shadow-md w-full sm:w-1/2">
                        <label class="block text-sm font-semibold text-gray-300">Max Similar TV Shows:</label>
                        <p class="text-gray-200">{{ config.MAX_SIMILAR_TV }}</p>
                    </div>
                </div>
                <div class="flex flex-col sm:flex-row sm:space-x-4 mt-4">
                    <!-- Max Content to Fetch and Search Size -->
                    <div class="bg-gray-700 p-4 rounded-lg shadow-md w-full sm:w-1/2">
                        <label class="block text-sm font-semibold text-gray-300">Max new Content for each content:</label>
                        <p class="text-gray-200">{{ config.MAX_CONTENT_CHECKS }}</p>
                    </div>
                    <div class="bg-gray-700 p-4 rounded-lg shadow-md w-full sm:w-1/2">
                        <label class="block text-sm font-semibold text-gray-300">Search Size:</label>
                        <p class="text-gray-200">{{ config.SEARCH_SIZE }}</p>
                    </div>
                </div>
                <!-- Display Next Cron Run Time -->
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Next Cron Run in:</label>
                    <p class="text-gray-200">{{ nextCronRun }}</p>
                </div>
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Current SuggestArr Version:</label>
                    <p class="text-gray-200">{{ currentVersion }}</p>
                    <div v-if="isUpdateAvailable" class="update-notification">
                        <span class="text-yellow-400 font-semibold">New Version Available: {{ latestVersion }}</span>
                        <a href="https://github.com/giuseppe99barchetta/SuggestArr/releases/latest" target="_blank"
                           class="text-blue-400 hover:underline ml-2">Update Now</a>
                    </div>
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
import packageInfo from '../../package.json';

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
            currentVersion: packageInfo.version,
            latestVersion: '',
            isUpdateAvailable: false

        };
    },
    mounted() {
        this.checkForUpdates();
        this.calculateNextCronRun();
        if (!this.config.TMDB_API_KEY) {
            this.startDefaultImageRotation();
        } else {
            this.startBackgroundImageRotation(fetchRandomMovieImage, this.config.TMDB_API_KEY);
        }
    },
    methods: {
        async checkForUpdates() {
            try {
                const response = await axios.get('https://api.github.com/repos/giuseppe99barchetta/SuggestArr/releases/latest');
                this.latestVersion = response.data.tag_name;
            
                const [currentMajor, currentMinor, currentPatch] = this.currentVersion.replace('v', '').split('.').map(Number);
                const [latestMajor, latestMinor, latestPatch] = this.latestVersion.replace('v', '').split('.').map(Number);
            
                this.isUpdateAvailable = 
                    latestMajor > currentMajor ||
                    (latestMajor === currentMajor && latestMinor > currentMinor) ||
                    (latestMajor === currentMajor && latestMinor === currentMinor && latestPatch > currentPatch);
            
                if (this.isUpdateAvailable) {
                    this.$toast.open({
                        message: 'New version of SuggestArr available!',
                        pauseOnHover: true,
                        duration: 5000
                    });
                }
            } catch (error) {
                console.error('Failed to check for updates:', error);
            }
        },
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

.attached-logo {
    width: 100px;
    height: auto;
    display: block;
    margin: 0 auto;
    margin-bottom: 30px;
}
</style>
