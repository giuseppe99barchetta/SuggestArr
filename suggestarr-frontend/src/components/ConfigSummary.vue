<template>
    <div class="flex items-center justify-center min-h-screen bg-gradient-to-br from-gray-900 to-gray-800">
        <div class="p-10 space-y-8 max-w-4xl mx-auto bg-gray-800 rounded-lg shadow-lg border border-gray-700">
            <h2 class="text-3xl font-bold text-gray-200 mb-6 text-center">Configuration Summary</h2>
            <div class="space-y-6">
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">TMDB API Key:</label>
                    <p class="text-gray-200">{{ config.TMDB_API_KEY }}</p>
                </div>
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Jellyfin URL:</label>
                    <p class="text-gray-200">{{ config.JELLYFIN_API_URL }}</p>
                </div>
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Jellyfin API Key:</label>
                    <p class="text-gray-200">{{ config.JELLYFIN_TOKEN }}</p>
                </div>
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Jellyseer URL:</label>
                    <p class="text-gray-200">{{ config.JELLYSEER_API_URL }}</p>
                </div>
                <div class="bg-gray-700 p-4 rounded-lg shadow-md">
                    <label class="block text-sm font-semibold text-gray-300">Jellyseer API Key:</label>
                    <p class="text-gray-200">{{ config.JELLYSEER_TOKEN }}</p>
                </div>
            </div>
            <button @click="editConfig" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full mt-8 shadow-lg transition-transform transform hover:scale-105">
                Edit Configuration
            </button>
            <!-- New Force Run Button -->
            <button @click="forceRun" class="bg-red-600 hover:bg-red-500 text-white font-bold py-4 px-8 rounded-lg w-full mt-4 shadow-lg transition-transform transform hover:scale-105">
                Force Run Job
            </button>
        </div>
    </div>
</template>

<script>
import axios from 'axios';

export default {
    props: {
        config: {
            type: Object,
            required: true
        }
    },
    mounted() {
        console.log("ConfigSummary component has been loaded.");
        console.log("Current Configuration:", this.config);
    },
    methods: {
        editConfig() {
            this.$emit('edit-config');
        },
        forceRun() {
            // Call backend to force run the job
            axios.post('http://localhost:5000/api/force_run', this.config)
            .then(response => {
                alert(response.data.message);  // Success message from backend
            })
            .catch(error => {
                alert(`Error: ${error.response ? error.response.data.message : error.message}`);  // Handle errors
            });
        }
    }
};
</script>

<style scoped>
</style>
