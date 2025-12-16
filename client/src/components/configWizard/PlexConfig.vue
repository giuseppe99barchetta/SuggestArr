<template>
    <div>
        <h3 class="text-xl font-bold text-gray-200 mb-2">Plex Configuration</h3>
        <p class="text-sm text-gray-400 mb-6">
            Connect to your Plex account to access your servers and libraries.
        </p>

        <!-- Login Button -->
        <div v-if="!isLoggedIn" class="mb-6">
            <button 
                @click="loginWithPlex" 
                :disabled="loading"
                class="w-full bg-plex hover:bg-plex-dark text-white font-bold py-4 px-8 rounded-lg shadow-lg 
                       transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed 
                       flex items-center justify-center gap-3">
                <i v-if="loading" class="fas fa-spinner fa-spin text-xl"></i>
                <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" class="w-6 h-6" fill="currentColor">
                    <path d="M18 18h12v12H18z"/>
                    <path d="M6 6h12v12H6zM30 6h12v12H30zM6 30h12v12H6zM30 30h12v12H30z"/>
                </svg>
                <span class="text-lg">{{ loading ? 'Connecting to Plex...' : 'Sign in with Plex' }}</span>
            </button>
            <p class="text-xs text-gray-500 mt-3 text-center flex items-center justify-center gap-2">
                <i class="fas fa-lock"></i> 
                Secure authentication via Plex.tv
            </p>
        </div>

        <!-- Server Selection -->
        <div v-if="servers.length > 0" class="mb-6">
            <label for="server-selection" class="block text-sm font-semibold text-gray-300 mb-2">
                Select Plex Server
            </label>
            <div class="flex flex-row items-center gap-2">
                <select 
                    v-model="selectedServerConnection" 
                    @change="updateSelectedServer"
                    class="flex-1 h-12 bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4
                           focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent
                           transition-all"
                    id="server-selection">
                    <option v-for="(connection, index) in getServerConnections()" 
                            :key="index"
                            :value="{ address: connection.address, port: connection.port, protocol: connection.protocol }">
                        {{ connection.serverName }} - {{ connection.address }}:{{ connection.port }} 
                        ({{ connection.protocol }}) 
                        {{ connection.secure ? '🔒' : '⚠️' }}
                    </option>
                    <option value="manual">⚙️ Manual Configuration</option>
                </select>

                <button 
                    v-if="!manualConfiguration" 
                    @click="fetchLibraries"
                    :disabled="loadingLibraries"
                    class="bg-orange-500 hover:bg-orange-600 text-white px-6 h-12 rounded-lg shadow-md 
                           flex items-center justify-center flex-shrink-0 transition-all duration-200
                           disabled:opacity-50 disabled:cursor-not-allowed min-w-[120px]">
                    <span v-if="loadingLibraries" class="flex items-center gap-2">
                        <i class="fas fa-spinner fa-spin"></i>
                        <span class="hidden sm:inline">Loading</span>
                    </span>
                    <span v-else class="flex items-center gap-2">
                        <i class="fas fa-sync-alt"></i>
                        <span class="hidden sm:inline">Connect</span>
                    </span>
                </button>
            </div>
            <p class="text-xs text-gray-500 mt-2">
                <i class="fas fa-info-circle"></i> 
                🔒 indicates secure HTTPS connection
            </p>
        </div>

        <!-- Manual Configuration -->
        <div v-if="manualConfiguration || selectedServer === 'manual'" class="mb-6">
            <h4 class="text-sm font-semibold text-gray-300 mb-2">Manual Server Configuration</h4>
            
            <label for="manual-address" class="block text-sm text-gray-400 mb-2">
                Server Address
            </label>

            <div class="flex flex-row items-center gap-2">
                <input 
                    type="url" 
                    v-model="manualServerAddress"
                    @input="$emit('update-config', 'PLEX_API_URL', $event.target.value)"
                    class="flex-1 h-12 bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4
                           focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent
                           transition-all" 
                    id="manual-address"
                    placeholder="http://192.168.1.10:32400">

                <button 
                    @click="fetchLibraries"
                    :disabled="loadingLibraries || !manualServerAddress"
                    class="bg-orange-500 hover:bg-orange-600 text-white px-6 h-12 rounded-lg shadow-md 
                           flex items-center justify-center flex-shrink-0 transition-all duration-200
                           disabled:opacity-50 disabled:cursor-not-allowed min-w-[120px]">
                    <span v-if="loadingLibraries" class="flex items-center gap-2">
                        <i class="fas fa-spinner fa-spin"></i>
                        <span class="hidden sm:inline">Testing</span>
                    </span>
                    <span v-else class="flex items-center gap-2">
                        <i class="fas fa-plug"></i>
                        <span class="hidden sm:inline">Connect</span>
                    </span>
                </button>
            </div>
            <p class="text-xs text-gray-500 mt-2">
                <i class="fas fa-info-circle"></i> 
                Example: http://192.168.1.100:32400 or https://plex.example.com
            </p>
        </div>

        <!-- Success Message -->
        <div v-if="libraries.length > 0" 
             class="bg-green-900 bg-opacity-30 border border-green-500 text-green-400 px-4 py-3 rounded-lg mb-6 flex items-center gap-2">
            <i class="fas fa-check-circle"></i>
            <span>Successfully connected! Found {{ libraries.length }} libraries and {{ users.length }} users.</span>
        </div>

        <!-- Library Selection -->
        <div v-if="libraries.length > 0" class="mb-6">
            <div class="flex items-center justify-between mb-3">
                <div>
                    <h4 class="text-sm font-semibold text-gray-300">Select Libraries</h4>
                    <p class="text-xs text-gray-500">
                        {{ selectedLibraryIds.length > 0 ? `${selectedLibraryIds.length} selected` : 'Select libraries or leave empty for all' }}
                    </p>
                </div>
                <button 
                    v-if="selectedLibraryIds.length > 0"
                    @click="clearLibrarySelection"
                    class="text-xs text-orange-400 hover:text-orange-300 flex items-center gap-1 bg-transparent border-none p-0 shadow-none font-normal">
                    <i class="fas fa-times-circle"></i>
                    Clear Selection
                </button>
            </div>
            
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <div 
                    v-for="library in libraries" 
                    :key="library.key" 
                    @click="toggleLibrarySelection(library)"
                    :class="{
                        'bg-orange-600 border-orange-500 ring-2 ring-orange-400': isSelected(library.key),
                        'bg-gray-700 border-gray-600 hover:border-orange-400': !isSelected(library.key)
                    }" 
                    class="cursor-pointer p-4 border-2 rounded-lg text-center text-white 
                           transition-all duration-200 relative group">
                    
                    <div v-if="isSelected(library.key)" 
                         class="absolute top-2 right-2 bg-white text-orange-600 rounded-full w-6 h-6 
                                flex items-center justify-center shadow-md">
                        <i class="fas fa-check text-xs"></i>
                    </div>
                    
                    <i :class="getLibraryIcon(library.type)" class="text-2xl mb-2"></i>
                    
                    <p class="font-medium">{{ library.title }}</p>
                    <p class="text-xs text-gray-400 mt-1">{{ library.type || 'Media' }}</p>
                </div>
            </div>
        </div>

        <!-- Users Selection -->
        <div v-if="users.length > 0" class="mb-6">
            <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                    <h4 class="text-sm font-semibold text-gray-300">Select Users</h4>
                    <span class="px-2 py-1 bg-yellow-500 text-xs text-white font-bold rounded-full">BETA</span>
                </div>
                <button 
                    v-if="selectedUserIds.length > 0"
                    @click="clearUserSelection"
                    class="text-xs text-orange-400 hover:text-orange-300 flex items-center gap-1 bg-transparent border-none p-0 shadow-none font-normal">
                    <i class="fas fa-times-circle"></i>
                    Clear Selection
                </button>
            </div>
            <p class="text-xs text-gray-500 mb-3">
                {{ selectedUserIds.length > 0 ? `${selectedUserIds.length} selected` : 'Select users or leave empty for all' }}
            </p>
            
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                <div 
                    v-for="user in users" 
                    :key="user.id" 
                    @click="toggleUserSelection(user)"
                    :class="{
                        'bg-orange-600 border-orange-500 ring-2 ring-orange-400': isUserSelected(user.id),
                        'bg-gray-700 border-gray-600 hover:border-orange-400': !isUserSelected(user.id)
                    }" 
                    class="cursor-pointer p-3 border-2 rounded-lg text-center text-white 
                           transition-all duration-200 relative">
                    
                    <div v-if="isUserSelected(user.id)" 
                         class="absolute top-2 right-2 bg-white text-orange-600 rounded-full w-5 h-5 
                                flex items-center justify-center shadow-md">
                        <i class="fas fa-check text-xs"></i>
                    </div>
                    
                    <i class="fas fa-user-circle text-3xl mb-2"></i>
                    <p class="font-medium text-sm truncate">{{ user.name }}</p>
                </div>
            </div>
        </div>

        <!-- Navigation Buttons -->
        <div class="flex justify-between mt-8 gap-4">
            <button 
                @click="$emit('previous-step')"
                class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full 
                       transition-colors duration-200">
                <i class="fas fa-arrow-left mr-2"></i>Back
            </button>
            <button 
                @click="$emit('next-step')"
                :disabled="libraries.length <= 0"
                class="bg-orange-600 hover:bg-orange-500 text-white font-bold py-4 px-8 rounded-lg w-full
                       transition-colors duration-200"
                :class="{ 'opacity-50 cursor-not-allowed': libraries.length <= 0 }">
                Next Step<i class="fas fa-arrow-right ml-2"></i>
            </button>
        </div>
    </div>
</template>

<script>
import plexApi from '../../api/plexApi';

export default {
    ...plexApi,
    methods: {
        ...plexApi.methods,
        
        getLibraryIcon(type) {
            const icons = {
                'movie': 'fas fa-film',
                'show': 'fas fa-tv',
                'artist': 'fas fa-music',
                'photo': 'fas fa-images'
            };
            return icons[type?.toLowerCase()] || 'fas fa-folder';
        },
        
        clearLibrarySelection() {
            this.selectedLibraryIds = [];
            this.selectedLibraryNames = [];
            this.$emit('update-config', 'PLEX_LIBRARIES', []);
        },
        
        clearUserSelection() {
            this.selectedUserIds = [];
            this.selectedUserNames = [];
            this.$emit('update-config', 'SELECTED_USERS', []);
        }
    }
};
</script>

<style scoped>
    .bg-plex {
        background-color: #e5a00d;
    }

    .bg-plex:hover {
        background-color: #cc8f0b;
    }

    .bg-plex-dark {
        background-color: #cc8f0b;
    }

    /* Or using CSS variables */
    :root {
        --color-plex: #e5a00d;
        --color-plex-hover: #cc8f0b;
    }
    
</style>