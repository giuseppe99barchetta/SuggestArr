<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">Step 3: Plex Client Details</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">
            Login using your Plex account.
        </p>
        <!-- Error message for failed validation -->
        <div v-if="plexTestState.status === 'fail'"
            class="bg-gray-800 border border-red-500 text-red-500 px-4 py-3 rounded-lg mt-4" role="alert">
            <span class="block sm:inline">Failed to connect to Plex API. Check your URL and token.</span>
        </div>

        <div v-if="!isLoggedIn">
            <button @click="loginWithPlex">Login with Plex</button>
        </div>

        <div v-if="servers.length > 0" class="mt-6">
            <label for="server-selection" class="block text-xs sm:text-sm font-semibold text-gray-300">Select a Plex
                Server and Connection:</label>
            <div class="flex items-center">
                <!-- Select for Plex Server and Connection -->
                <select v-model="selectedServerConnection" @change="updateSelectedServer"
                    class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                    id="server-selection">
                    <option v-for="(connection, index) in getServerConnections()" :key="index"
                        :value="{ address: connection.address, port: connection.port, protocol: connection.protocol }">
                        {{ connection.serverName }} - {{ connection.address }}:{{ connection.port }} ({{
                            connection.protocol }}) {{ connection.secure ? '[Secure]' : '[Insecure]' }}
                    </option>
                    <option value="manual">Manual Configuration</option>
                </select>

                <!-- Button with refresh icon -->
                <button v-if="!manualConfiguration" @click="fetchLibraries"
                    class="ml-2 bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-lg">
                    <i class="fas fa-sync-alt"></i> <!-- Font Awesome icon for refresh -->
                </button>
            </div>
        </div>

        <div v-if="manualConfiguration || selectedServer === 'manual'" class="mt-6">
            <h3 class="text-md text-gray-300 mb-4">Manual Server Configuration</h3>

            <label for="manual-address" class="block text-xs sm:text-sm font-semibold text-gray-300">Server
                Address:</label>

            <!-- Wrapping input and button in a flex container -->
            <div class="flex items-center">
                <!-- Input for manual server address -->
                <input type="text" v-model="manualServerAddress"
                    class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" id="manual-address"
                    placeholder="Enter server address"
                    @input="this.$emit('update-config', 'PLEX_API_URL', $event.target.value)">

                <!-- Button for refreshing libraries next to the input -->
                <button @click="fetchLibraries"
                    class="ml-2 bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-lg">
                    <i class="fas fa-sync-alt"></i> <!-- Font Awesome icon for refresh -->
                </button>
            </div>
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
                :disabled="libraries.length <= 0">
                Next Step
            </button>
        </div>
    </div>
</template>


<script>
import plexClientLogic from '../../api/PlexApi';

export default {
    ...plexClientLogic,
};
</script>
