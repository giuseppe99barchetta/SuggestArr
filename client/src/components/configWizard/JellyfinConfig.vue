<template>
    <div>
        <h3 class="text-xl font-bold text-gray-200 mb-2">{{ serviceName }} Configuration</h3>
        <p class="text-sm text-gray-400 mb-6">
            Connect to your {{ serviceName }} server to import libraries and user preferences.
        </p>

        <!-- Server URL Input -->
        <div class="mb-6">
            <label :for="`JELLYFIN_API_URL`" class="block text-sm font-semibold text-gray-300 mb-2">
                {{ serviceName }} Server URL
            </label>
            <input 
                type="url" 
                :value="config[`JELLYFIN_API_URL`]" 
                @input="handleUrlInput($event.target.value)"
                @blur="updateApiUrl($event.target.value)"
                class="w-full h-12 bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                       transition-all"
                :placeholder="`http://your-${serviceName.toLowerCase()}-server:8096`">
            <p class="text-xs text-gray-500 mt-2">
                <i class="fas fa-info-circle"></i> 
                Example: http://192.168.1.100:8096 or https://{{ serviceName.toLowerCase() }}.example.com
            </p>
        </div>

        <!-- API Key Input with Test Button -->
        <div class="mb-6">
            <label :for="`JELLYFIN_TOKEN`" class="block text-sm font-semibold text-gray-300 mb-2">
                {{ serviceName }} API Key
            </label>
            <div class="flex flex-row items-center gap-2">
                <input 
                    type="password" 
                    :value="config[`JELLYFIN_TOKEN`]"
                    @input="handleTokenInput($event.target.value)"
                    :disabled="testState.isTesting"
                    class="flex-1 h-12 bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 
                           focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                           disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                    :placeholder="`Your ${serviceName} API Key`">
                
                <button 
                    type="button" 
                    @click="fetchLibraries" 
                    :disabled="testState.isTesting || !canTest"
                    :class="{
                        'bg-green-500 hover:bg-green-600': testState.status === 'success',
                        'bg-red-500 hover:bg-red-600': testState.status === 'fail',
                        'bg-blue-500 hover:bg-blue-600': testState.status === null && canTest,
                        'bg-gray-500 cursor-not-allowed': !canTest
                    }"
                    class="text-white px-6 h-12 rounded-lg shadow-md flex items-center justify-center 
                           flex-shrink-0 transition-all duration-200 min-w-[120px]
                           disabled:opacity-50 disabled:cursor-not-allowed">
                    <span v-if="testState.isTesting" class="flex items-center gap-2">
                        <i class="fas fa-spinner fa-spin"></i>
                        <span class="hidden sm:inline">Testing</span>
                    </span>
                    <span v-else-if="testState.status === 'success'" class="flex items-center gap-2">
                        <i class="fas fa-check"></i>
                        <span class="hidden sm:inline">Connected</span>
                    </span>
                    <span v-else-if="testState.status === 'fail'" class="flex items-center gap-2">
                        <i class="fas fa-times"></i>
                        <span class="hidden sm:inline">Failed</span>
                    </span>
                    <span v-else class="flex items-center gap-2">
                        <i class="fas fa-plug"></i>
                        <span class="hidden sm:inline">Connect</span>
                    </span>
                </button>
            </div>
            
            <div class="mt-2">
                <button 
                    type="button"
                    @click="showApiKeyHelp = !showApiKeyHelp"
                    class="help-link text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
                    <i class="fas fa-question-circle"></i>
                    How to get your API Key?
                </button>
                
                <div v-if="showApiKeyHelp" class="mt-3 p-3 bg-gray-800 border border-gray-600 rounded-lg text-xs text-gray-300">
                    <ol class="list-decimal list-inside space-y-1">
                        <li>Open {{ serviceName }} web interface</li>
                        <li>Navigate to Dashboard → API Keys</li>
                        <li>Click "New API Key" and give it a name</li>
                        <li>Copy the generated key and paste it above</li>
                    </ol>
                </div>
            </div>
        </div>

        <!-- Success Message -->
        <div v-if="testState.status === 'success'" 
             class="bg-green-900 bg-opacity-30 border border-green-500 text-green-400 px-4 py-3 rounded-lg mb-6 flex items-center gap-2" 
             role="alert">
            <i class="fas fa-check-circle"></i>
            <span>Successfully connected to {{ serviceName }}! Found {{ libraries.length }} libraries and {{ users.length }} users.</span>
        </div>

        <!-- Error Message -->
        <div v-if="testState.status === 'fail'"
            class="bg-red-900 bg-opacity-30 border border-red-500 text-red-400 px-4 py-3 rounded-lg mb-6 flex items-center gap-2" 
            role="alert">
            <i class="fas fa-exclamation-circle"></i>
            <span>Failed to connect to {{ serviceName }}. Please verify your URL and API Key.</span>
        </div>

        <!-- Libraries Selection -->
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
                    class="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
                    <i class="fas fa-times-circle"></i>
                    Clear Selection
                </button>
            </div>
            
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <div 
                    v-for="library in libraries" 
                    :key="library.ItemId" 
                    @click="toggleLibrarySelection(library)"
                    :class="{
                        'bg-indigo-600 border-indigo-500 shadow-lg': isSelected(library.ItemId),
                        'bg-gray-700 border-gray-600 hover:border-indigo-400': !isSelected(library.ItemId)
                    }" 
                    class="cursor-pointer p-4 border-2 rounded-lg text-center text-white 
                           transition-all duration-200 relative group">
                    
                    <!-- Checkmark for selected items -->
                    <div v-if="isSelected(library.ItemId)" 
                         class="absolute top-2 right-2 bg-white text-indigo-600 rounded-full w-6 h-6 
                                flex items-center justify-center">
                        <i class="fas fa-check text-xs"></i>
                    </div>
                    
                    <!-- Library icon based on type -->
                    <i :class="getLibraryIcon(library.CollectionType)" class="text-2xl mb-2"></i>
                    
                    <p class="font-medium">{{ library.Name }}</p>
                </div>
            </div>
        </div>

        <!-- Users Selection -->
        <div v-if="users.length > 0" class="mb-6">
            <div class="flex items-center justify-between mb-3">
                <div>
                    <h4 class="text-sm font-semibold text-gray-300">Select Users</h4>
                    <p class="text-xs text-gray-500">
                        {{ selectedUserIds.length > 0 ? `${selectedUserIds.length} selected` : 'Select users or leave empty for all' }}
                    </p>
                </div>
                <button 
                    v-if="selectedUserIds.length > 0"
                    @click="clearUserSelection"
                    class="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
                    <i class="fas fa-times-circle"></i>
                    Clear Selection
                </button>
            </div>
            
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                <div 
                    v-for="user in users" 
                    :key="user.id" 
                    @click="toggleUserSelection(user)"
                    :class="{
                        'bg-indigo-600 border-indigo-500 shadow-lg': isUserSelected(user.id),
                        'bg-gray-700 border-gray-600 hover:border-indigo-400': !isUserSelected(user.id)
                    }" 
                    class="cursor-pointer p-3 border-2 rounded-lg text-center text-white 
                           transition-all duration-200 relative">
                    
                    <div v-if="isUserSelected(user.id)" 
                         class="absolute top-2 right-2 bg-white text-indigo-600 rounded-full w-5 h-5 
                                flex items-center justify-center">
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
                @click="handleNext" 
                :disabled="!canProceed"
                class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full
                       transition-colors duration-200"
                :class="{ 'opacity-50 cursor-not-allowed': !canProceed }">
                Next Step<i class="fas fa-arrow-right ml-2"></i>
            </button>
        </div>
    </div>
</template>

<script>
import { fetchJellyfinLibraries, fetchJellyfinUsers } from '../../api/api';

export default {
    props: ['config'],
    data() {
        return {
            testState: {
                status: null,
                isTesting: false
            },
            libraries: [],
            selectedLibraryIds: [],
            selectedLibraryNames: [],
            users: [],
            selectedUserIds: [],
            selectedUserName: [],
            showApiKeyHelp: false,
        };
    },
    computed: {
        serviceName() {
            return this.config.SELECTED_SERVICE === 'emby' ? 'Emby' : 'Jellyfin';
        },
        canTest() {
            return this.config[`JELLYFIN_API_URL`] && this.config[`JELLYFIN_TOKEN`];
        },
        canProceed() {
            return this.testState.status === 'success';
        }
    },
    methods: {
        handleUrlInput(value) {
            // Reset test state when URL changes
            if (this.testState.status !== null) {
                this.testState.status = null;
                this.libraries = [];
                this.users = [];
            }
        },
        
        handleTokenInput(value) {
            this.$emit('update-config', `JELLYFIN_TOKEN`, value);
            // Reset test state when token changes
            if (this.testState.status !== null) {
                this.testState.status = null;
                this.libraries = [];
                this.users = [];
            }
        },

        fetchLibraries() {
            if (!this.canTest) return;
            
            this.testState.isTesting = true;
            this.testState.status = null;
            
            fetchJellyfinLibraries(this.config[`JELLYFIN_API_URL`], this.config[`JELLYFIN_TOKEN`])
                .then(response => {
                    this.libraries = response.data.items;
                    this.testState.status = 'success';
                    this.loadSelectedLibraries();
                    this.fetchUsers();
                })
                .catch(error => {
                    console.error('Error fetching libraries:', error);
                    this.testState.status = 'fail';
                    this.libraries = [];
                    this.users = [];
                })
                .finally(() => {
                    this.testState.isTesting = false;
                });
        },

        fetchUsers() {
            fetchJellyfinUsers(this.config[`JELLYFIN_API_URL`], this.config[`JELLYFIN_TOKEN`])
                .then(response => {
                    this.users = response.data.users;
                    this.loadSelectedUsers();
                })
                .catch(error => {
                    console.error('Error fetching users:', error);
                });
        },

        toggleLibrarySelection(library) {
            const index = this.selectedLibraryIds.indexOf(library.ItemId);
            if (index === -1) {
                this.selectedLibraryIds.push(library.ItemId);
                this.selectedLibraryNames.push(library.Name);
            } else {
                this.selectedLibraryIds.splice(index, 1);
                this.selectedLibraryNames.splice(this.selectedLibraryNames.indexOf(library.Name), 1);
            }
            this.$emit('update-config', `JELLYFIN_LIBRARIES`, this.combineLibraryData(this.selectedLibraryIds, this.selectedLibraryNames));
        },

        toggleUserSelection(user) {
            const index = this.selectedUserIds.indexOf(user.id);
            if (index === -1) {
                this.selectedUserIds.push(user.id);
                this.selectedUserName.push(user.name);
            } else {
                this.selectedUserIds.splice(index, 1);
                this.selectedUserName.splice(index, 1);
            }
        
            const cleanedIds = this.selectedUserIds.filter(id => id);
            const cleanedNames = this.selectedUserName.filter(name => name);
            const cleanSelectedUsers = this.combineLibraryData(cleanedIds, cleanedNames);
        
            this.$emit('update-config', `SELECTED_USERS`, cleanSelectedUsers);
        },

        clearLibrarySelection() {
            this.selectedLibraryIds = [];
            this.selectedLibraryNames = [];
            this.$emit('update-config', `JELLYFIN_LIBRARIES`, []);
        },

        clearUserSelection() {
            this.selectedUserIds = [];
            this.selectedUserName = [];
            this.$emit('update-config', `SELECTED_USERS`, []);
        },

        isUserSelected(userId) {
            return this.selectedUserIds.includes(userId);
        },

        isSelected(libraryId) {
            return this.selectedLibraryIds.includes(libraryId);
        },

        getLibraryIcon(collectionType) {
            const icons = {
                'movies': 'fas fa-film',
                'tvshows': 'fas fa-tv',
                'music': 'fas fa-music',
                'books': 'fas fa-book',
                'photos': 'fas fa-images'
            };
            return icons[collectionType?.toLowerCase()] || 'fas fa-folder';
        },

        loadSelectedLibraries() {
            if (this.config[`JELLYFIN_LIBRARIES`]) {
                this.selectedLibraryIds = this.config[`JELLYFIN_LIBRARIES`].map(lib => lib.id);
                this.selectedLibraryNames = this.config[`JELLYFIN_LIBRARIES`].map(lib => lib.name);
            }
        },

        loadSelectedUsers() {
            if (this.config[`SELECTED_USERS`]) {
                this.selectedUserIds = this.config[`SELECTED_USERS`].map(user => user.id);
                this.selectedUserName = this.config[`SELECTED_USERS`].map(user => user.name);
            }
        },

        combineLibraryData(ids, names) {
            if (ids.length !== names.length) {
                console.error("Mismatch between number of ids and names");
                return [];
            }

            return ids
                .map((id, index) => ({ id: id, name: names[index] }))
                .filter(item => item.id && item.name);
        },

        updateApiUrl(url) {
            const trimmedUrl = url.trim().replace(/\/+$/, ''); // Remove trailing slashes
            this.$emit('update-config', `JELLYFIN_API_URL`, trimmedUrl);
        },

        handleNext() {
            if (this.canProceed) {
                this.$emit('next-step');
            }
        },

        autoTestService() {
            if (this.canTest) {
                this.fetchLibraries();
            }
        }
    },
    mounted() {
        this.autoTestService();
    }
};
</script>
