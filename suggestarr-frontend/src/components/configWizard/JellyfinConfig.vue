<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">Step 2: Jellyfin API Details</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">To obtain your Jellyfin API Key, follow these steps: Open the Jellyfin web interface, navigate to the Control Panel, select "API Keys," create a new key, and copy it for use in this configuration.</p>

        <!-- Input for Jellyfin API URL -->
        <label for="JELLYFIN_API_URL" class="block text-xs sm:text-sm font-semibold text-gray-300">Jellyfin URL:</label>
        <input type="text" :value="config.JELLYFIN_API_URL" @input="updateJellyfinUrl($event.target.value)"
            class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
            placeholder="http://your-jellyfin-url">

        <!-- Input for Jellyfin API Token -->
        <label for="JELLYFIN_TOKEN" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Jellyfin API Key:</label>
        <div class="flex flex-col sm:flex-row items-start sm:items-center">
            <input type="text" :value="config.JELLYFIN_TOKEN"
                @input="$emit('update-config', 'JELLYFIN_TOKEN', $event.target.value)"
                class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2 mb-4 sm:mb-0 sm:mr-2"
                placeholder="Your Jellyfin API Key">
            <button type="button" @click="fetchJellyfinLibraries" :disabled="jellyfinTestState.isTesting" :class="{
                'bg-green-500 hover:bg-green-600': jellyfinTestState.status === 'success',
                'bg-red-500 hover:bg-red-600': jellyfinTestState.status === 'fail',
                'bg-blue-500 hover:bg-blue-600': jellyfinTestState.status === null
            }" class="text-white px-4 py-2 rounded-lg shadow-md w-full sm:w-auto">
                <i v-if="jellyfinTestState.isTesting" class="fas fa-spinner fa-spin"></i>
                <i v-else-if="jellyfinTestState.status === 'success'" class="fas fa-check"></i>
                <i v-else-if="jellyfinTestState.status === 'fail'" class="fas fa-times"></i>
                <i v-else class="fas fa-play"></i>
            </button>
        </div>

        <!-- Display Jellyfin Libraries -->
        <div v-if="jellyfinLibraries.length > 0">
            <p class="text-sm text-gray-300 mt-4">Select the Jellyfin libraries you want to include:</p>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
                <div v-for="library in jellyfinLibraries" :key="library.ItemId" @click="toggleLibrarySelection(library)"
                    :class="{
                        'bg-indigo-600 border-indigo-600': isSelected(library.ItemId),
                        'bg-gray-700 border-gray-600': !isSelected(library.ItemId)
                    }" class="cursor-pointer p-4 border rounded-lg text-center text-white hover:bg-indigo-500">
                    {{ library.Name }}
                </div>
            </div>
        </div>

        <!-- Error message on failure -->
        <div v-if="jellyfinTestState.status === 'fail'"
            class="bg-gray-800 border border-red-500 text-red-500 px-4 py-3 rounded-lg mt-4" role="alert">
            <span class="block sm:inline">Failed to validate Jellyfin Key or retrieve libraries.</span>
        </div>

        <!-- Next and Back Buttons -->
        <div class="flex justify-between mt-8 space-x-4">
            <button @click="$emit('previous-step')"
                class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">Back</button>
            <button @click="$emit('next-step', { selectedLibraryIds, selectedLibraryNames })" :disabled="selectedLibraryIds.length === 0"
                class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full"
                :class="{ 'opacity-50 cursor-not-allowed': selectedLibraryIds.length === 0 }">Next Step</button>
        </div>
    </div>
</template>

<script>
import { fetchJellyfinLibraries } from '../../api/api';

export default {
    props: ['config'],
    data() {
        return {
            jellyfinTestState: {
                status: null, // 'success', 'fail', or null (not tested)
                isTesting: false
            },
            jellyfinLibraries: [],      // Contains the retrieved Jellyfin libraries
            selectedLibraryIds: [],     // Contains the IDs of the selected libraries
            selectedLibraryNames: []    // Contains the names of the selected libraries
        };
    },
    methods: {
        fetchJellyfinLibraries() {
            this.jellyfinTestState.isTesting = true;
            this.jellyfinTestState.status = null; // Reset status before the test
            fetchJellyfinLibraries(this.config.JELLYFIN_API_URL, this.config.JELLYFIN_TOKEN)
                .then(response => {
                    this.jellyfinLibraries = response.data.items;
                    this.jellyfinTestState.status = 'success';
                    this.loadSelectedLibraries();
                })
                .catch(() => {
                    this.jellyfinTestState.status = 'fail';
                })
                .finally(() => {
                    this.jellyfinTestState.isTesting = false;
                });
        },
        toggleLibrarySelection(library) {
            const index = this.selectedLibraryIds.indexOf(library.ItemId);
            if (index === -1) {
                // Add the library ID and name if it's not already selected
                this.selectedLibraryIds.push(library.ItemId);
                this.selectedLibraryNames.push(library.Name);
            } else {
                // Remove the library ID and name if it's already selected
                this.selectedLibraryIds.splice(index, 1);
                this.selectedLibraryNames.splice(this.selectedLibraryNames.indexOf(library.Name), 1);
            }
            // Emit both the IDs and names of the selected libraries
            this.$emit('update-jellyfin-libraries', { ids: this.selectedLibraryIds, names: this.selectedLibraryNames });
        },
        isSelected(libraryId) {
            return this.selectedLibraryIds.includes(libraryId);
        },
        loadSelectedLibraries() {
            if (this.config.JELLYFIN_LIBRARIES) {
                this.selectedLibraryIds = this.jellyfinLibraries
                    .filter(library => this.config.JELLYFIN_LIBRARIES.includes(library.ItemId))
                    .map(library => library.ItemId);
                    
            }
        },
        updateJellyfinUrl(url) {
            // Remove trailing slash if it exists
            const trimmedUrl = url.endsWith('/') ? url.slice(0, -1) : url;
            this.$emit('update-config', 'JELLYFIN_API_URL', trimmedUrl);
        },
        autoTestJellyfin() {
            if (this.config.JELLYFIN_API_URL && this.config.JELLYFIN_TOKEN) {
                this.fetchJellyfinLibraries(); // Automatically test Jellyfin API if the details exist
            }
        }
    },
    mounted() {
        this.autoTestJellyfin(); // Auto test Jellyfin API on mount if details are present
    }
};

</script>
