<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">Step 3: Plex Client Details</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">
            To get your Plex token follow this guide:
            <a href="https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/">
                How to get Plex Token.
            </a>
        </p>

        <!-- Plex Token -->
        <label for="PLEX_TOKEN" class="block text-xs sm:text-sm font-semibold text-gray-300">Plex Token:</label>
        <input type="text" :value="config.PLEX_TOKEN" 
            @input="$emit('update-config', 'PLEX_TOKEN', $event.target.value)"
            class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" 
            id="PLEX_TOKEN" placeholder="Enter your Plex Token">

        <!-- Plex URL + Test Button -->
        <label for="PLEX_API_URL" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Plex URL:</label>
        <div class="flex flex-col sm:flex-row items-start sm:items-center">
            <input type="text" :value="config.PLEX_API_URL" 
                @input="$emit('update-config', 'PLEX_API_URL', $event.target.value)"
                class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2 mb-4 sm:mb-0 sm:mr-2"
                id="PLEX_API_URL" placeholder="http://your-plex-url">
            <button type="button" @click="testPlexApiConnection" :disabled="plexTestState.isTesting" 
                :class="{
                    'bg-green-500 hover:bg-green-600': plexTestState.status === 'success',
                    'bg-red-500 hover:bg-red-600': plexTestState.status === 'fail',
                    'bg-blue-500 hover:bg-blue-600': plexTestState.status === null
                }" 
                class="text-white px-4 py-2 rounded-lg shadow-md w-full sm:w-auto">
                <i v-if="plexTestState.isTesting" class="fas fa-spinner fa-spin"></i>
                <i v-else-if="plexTestState.status === 'success'" class="fas fa-check"></i>
                <i v-else-if="plexTestState.status === 'fail'" class="fas fa-times"></i>
                <i v-else class="fas fa-play"></i>
            </button>
        </div>

        <!-- Error message for failed validation -->
        <div v-if="plexTestState.status === 'fail'"
            class="bg-gray-800 border border-red-500 text-red-500 px-4 py-3 rounded-lg mt-4" role="alert">
            <span class="block sm:inline">Failed to connect to Plex API. Check your URL and token.</span>
        </div>

        <!-- Library Selection -->
        <div v-if="libraries.length > 0">
            <p class="text-sm text-gray-300 mt-4">Select the Plex libraries you want to include:</p>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
                <div v-for="library in libraries" :key="library.uuid" @click="toggleLibrarySelection(library)" :class="{
                    'bg-indigo-600 border-indigo-600': isSelected(library.uuid),
                    'bg-gray-700 border-gray-600': !isSelected(library.uuid)
                }" class="cursor-pointer p-4 border rounded-lg text-center text-white hover:bg-indigo-500">
                    {{ library.title }}
                </div>
            </div>
        </div>

        <!-- Navigation buttons -->
        <div class="flex justify-between mt-8 space-x-4">
            <button @click="$emit('previous-step')"
                class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">
                Back
            </button>
            <button @click="$emit('next-step')"
                class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full"
                :disabled="plexTestState.status !== 'success'">
                Next Step
            </button>
        </div>
    </div>
</template>


<script>
import { getPlexLibraries } from '../../api/api';

export default {
    props: ['config'],
    data() {
        return {
            plexTestState: {
                status: null, // 'success', 'fail', or null (non testato)
                isTesting: false
            },
            libraries: [],
            selectedLibraries: []
        };
    },
    methods: {
        testPlexApiConnection() {
        this.plexTestState.isTesting = true; // Correct the assignment
        this.plexTestState.status = null; // Reset the status before starting the test
        getPlexLibraries(this.config.PLEX_API_URL, this.config.PLEX_TOKEN)
            .then(response => {
                if (response && response.items) {
                    this.libraries = response.items;
                    this.loadSelectedLibraries();
                    this.plexTestState.status = 'success'; // Mark success
                } else {
                    this.libraries = [];
                    this.plexTestState.status = 'fail'; // Mark failure
                }
            })
            .catch(() => {
                this.libraries = [];
                this.plexTestState.status = 'fail'; // Mark failure
            })
            .finally(() => {
                this.plexTestState.isTesting = false; // Set isTesting to false once finished
            });
    },
        toggleLibrarySelection(library) {
            const index = this.selectedLibraries.findIndex(l => l.uuid === library.uuid);
            if (index > -1) {
                this.selectedLibraries.splice(index, 1);
            } else {
                this.selectedLibraries.push(library);
            }

            this.updateSelectedLibraries();
        },
        isSelected(libraryId) {
            return this.selectedLibraries.some(library => library.uuid === libraryId);
        },
        updateSelectedLibraries() {
            const libraryIds = this.selectedLibraries.map(library => library.uuid);
            this.$emit('update-plex-libraries', libraryIds);  // Emetti l'array degli ID delle librerie selezionate
        },
        loadSelectedLibraries() {
            if (this.config.PLEX_LIBRARIES) {
                console.log(this.config.PLEX_LIBRARIES)
                this.selectedLibraries = this.libraries.filter(library => 
                    this.config.PLEX_LIBRARIES.includes(library.uuid)
                );
            }
        }
    },
    mounted() {
        if (this.config.PLEX_LIBRARIES) {
            this.selectedLibraries = this.libraries.filter(library =>
                this.config.PLEX_LIBRARIES.includes(library.uuid)
            );
        }
    }
};
</script>
