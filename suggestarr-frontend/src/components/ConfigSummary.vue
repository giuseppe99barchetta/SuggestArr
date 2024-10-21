<template>
    <div class="flex items-center justify-center min-h-screen bg-gradient-to-br from-gray-900 to-gray-800">
        <div class="p-10 space-y-8 max-w-4xl mx-auto bg-gray-800 rounded-lg shadow-lg border border-gray-700">
            <h2 class="text-3xl font-bold text-gray-200 mb-6 text-center">SuggestArr Summary</h2>
            <div class="space-y-6">
                <!-- Display Jellyfin URL -->
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Jellyfin URL:</label>
                    <p class="text-gray-200">{{ config.JELLYFIN_API_URL }}</p>
                </div>
                <!-- Display Jellyseer URL -->
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Jellyseer URL:</label>
                    <p class="text-gray-200">{{ config.JELLYSEER_API_URL }}</p>
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
                <!-- Display Next Cron Run Time -->
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Next Cron Run in:</label>
                    <p class="text-gray-200">{{ nextCronRun }}</p>
                </div>
            </div>
            <!-- Edit Configuration Button -->
            <button @click="editConfig" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full mt-8 shadow-lg transition-transform transform hover:scale-105">
                Edit Configuration
            </button>
            <!-- Force Run Button -->
            <button @click="forceRun" class="bg-red-600 hover:bg-red-500 text-white font-bold py-4 px-8 rounded-lg w-full mt-4 shadow-lg transition-transform transform hover:scale-105">
                <i v-if="isRunning" class="fas fa-spinner fa-spin"></i>
                <span v-else>Run Now</span>
            </button>

            <Footer />
            
        </div>
    </div>
</template>

<script>
import axios from 'axios';
import cronParser from 'cron-parser';
import Footer from './AppFooter.vue';

export default {
    components: {
        Footer,
    },
    props: {
        config: {
            type: Object,
            required: true
        }
    },
    data() {
        return {
            isRunning: false, // Track the running state for the 'Run Now' button
            nextCronRun: ''   // To store the time remaining until next cron run
        };
    },
    mounted() {
        this.calculateNextCronRun();
    },
    methods: {
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
            axios.post('http://localhost:5000/api/force_run', this.config)
            .then(response => {
                console.log(response.data.message); // Success message from backend
            })
            .catch(error => {
                alert(`Error: ${error.response ? error.response.data.message : error.message}`); // Handle errors
            })
            .finally(() => {
                this.isRunning = false; // Reset running state after completion
            });
        }
    }
};

</script>

<style scoped>
</style>
