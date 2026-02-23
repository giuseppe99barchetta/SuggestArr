<template>
  <div class="config-section">
    <h3 class="section-title">{{ serviceName }} Configuration</h3>
    <p class="section-description">
      Connect to your {{ serviceName }} server to import libraries and user preferences.
    </p>

    <!-- Connection Settings Card -->
    <div class="settings-card">
      <h4 class="card-title">Connection Settings</h4>

      <!-- Server URL Input -->
      <div class="form-group">
        <label :for="`JELLYFIN_API_URL`" class="form-label">
          {{ serviceName }} Server URL
        </label>
        <input type="url" :value="config[`JELLYFIN_API_URL`]" @input="handleUrlInput($event.target.value)"
          @blur="updateApiUrl($event.target.value)" class="form-input"
          :placeholder="`http://your-${serviceName.toLowerCase()}-server:8096`">
        <p class="form-help">
          <i class="fas fa-info-circle"></i>
          Example: http://192.168.1.100:8096 or https://{{ serviceName.toLowerCase() }}.example.com
        </p>
      </div>

      <!-- API Key Input with Test Button -->
      <div class="form-group">
        <label :for="`JELLYFIN_TOKEN`" class="form-label">
          {{ serviceName }} API Key
        </label>
        <div class="input-group">
          <input type="password" :value="config[`JELLYFIN_TOKEN`]" @input="handleTokenInput($event.target.value)"
            :disabled="testState.isTesting" class="form-input" :placeholder="`Your ${serviceName} API Key`">

          <button type="button" @click="fetchLibraries" :disabled="testState.isTesting || !canTest" :class="[
            'btn btn-test',
            {
              'btn-success': testState.status === 'success',
              'btn-danger': testState.status === 'fail',
              'btn-primary': testState.status === null && canTest,
              'btn-disabled': !canTest
            }
          ]">
            <span v-if="testState.isTesting" class="btn-content">
              <i class="fas fa-spinner fa-spin"></i>
              <span class="hidden btn-text">Testing</span>
            </span>
            <span v-else-if="testState.status === 'success'" class="btn-content">
              <i class="fas fa-check"></i>
              <span class="hidden btn-text">Connected</span>
            </span>
            <span v-else-if="testState.status === 'fail'" class="btn-content">
              <i class="fas fa-times"></i>
              <span class="hidden btn-text">Failed</span>
            </span>
            <span v-else class="btn-content">
              <i class="fas fa-plug"></i>
              <span class="hidden btn-text">Connect</span>
            </span>
          </button>
        </div>

        <div class="help-section">
          <button type="button" @click="showApiKeyHelp = !showApiKeyHelp" class="help-link">
            <i class="fas fa-question-circle"></i>
            How to get your API Key?
          </button>

          <div v-if="showApiKeyHelp" class="help-content">
            <ol class="help-list">
              <li>Open {{ serviceName }} web interface</li>
              <li>Navigate to Dashboard → API Keys</li>
              <li>Click "New API Key" and give it a name</li>
              <li>Copy the generated key and paste it above</li>
            </ol>
          </div>
        </div>
      </div>

      <!-- Success Message -->
      <div v-if="testState.status === 'success'" class="alert alert-success" role="alert">
        <i class="fas fa-check-circle"></i>
        <span>Successfully connected to {{ serviceName }}! Found {{ libraries.length }} libraries and {{ users.length }}
          users.</span>
      </div>

      <!-- Error Message -->
      <div v-if="testState.status === 'fail'" class="alert alert-danger" role="alert">
        <i class="fas fa-exclamation-circle"></i>
        <span>Failed to connect to {{ serviceName }}. Please verify your URL and API Key.</span>
      </div>
    </div>

    <!-- Libraries Selection Card -->
    <div v-if="libraries.length > 0" class="settings-card">
      <div class="selection-header">
        <div class="selection-info">
          <h4 class="card-title">Select Libraries</h4>
          <p class="section-description">
            {{ selectedLibraries.length > 0 ? `${selectedLibraries.length} selected` : 'Select libraries or leave empty for all' }}
          </p>
        </div>
        <button v-if="selectedLibraries.length > 0" @click="clearLibrarySelection" class="clear-btn">
          <i class="fas fa-times-circle"></i>
          Clear Selection
        </button>
      </div>

      <div class="selection-grid">
        <div v-for="library in libraries" :key="library.ItemId" @click="toggleLibrarySelection(library)"
          :class="['selection-item', { 'selected': isSelected(library.ItemId) }]">
          <!-- Checkmark for selected items -->
          <div v-if="isSelected(library.ItemId)" class="selection-check">
            <i class="fas fa-check"></i>
          </div>

          <!-- Library icon based on type -->
          <i :class="getLibraryIcon(library.CollectionType)" class="selection-icon"></i>

          <p class="selection-name">{{ library.Name }}</p>

          <!-- Anime toggle badge -->
          <button v-if="isSelected(library.ItemId)"
            @click.stop="toggleAnimeFlag(library.ItemId)"
            :class="['anime-badge', { 'anime-active': isAnimeLibrary(library.ItemId) }]"
            :title="isAnimeLibrary(library.ItemId) ? 'Marked as Anime library' : 'Mark as Anime library'">
            <i class="fas fa-torii-gate"></i>
            <span class="anime-badge-text">Anime</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Users Selection Card -->
    <div v-if="users.length > 0" class="settings-card">
      <div class="selection-header">
        <div class="selection-info">
          <h4 class="card-title">Select Users</h4>
          <p class="section-description">
            {{ selectedUserIds.length > 0 ? `${selectedUserIds.length} selected` : 'Select users or leave empty for all'
            }}
          </p>
        </div>
        <button v-if="selectedUserIds.length > 0" @click="clearUserSelection" class="clear-btn">
          <i class="fas fa-times-circle"></i>
          Clear Selection
        </button>
      </div>

      <div class="selection-grid users-grid">
        <div v-for="user in users" :key="user.id" @click="toggleUserSelection(user)"
          :class="['selection-item', { 'selected': isUserSelected(user.id) }]">
          <div v-if="isUserSelected(user.id)" class="selection-check">
            <i class="fas fa-check"></i>
          </div>

          <i class="fas fa-user-circle selection-icon"></i>
          <p class="selection-name">{{ user.name }}</p>
        </div>
      </div>
    </div>

    <!-- Navigation Buttons -->
    <div class="flex justify-between mt-8 gap-4">
      <button @click="$emit('previous-step')"
        class="btn-secondary w-full flex items-center justify-center gap-2 py-4 px-8">
        <i class="fas fa-arrow-left"></i>
        Back
      </button>

      <button @click="$emit('next-step')" :disabled="testState.status !== 'success'"
        class="btn-primary w-full flex items-center justify-center gap-2 py-4 px-8"
        :class="{ 'opacity-50 cursor-not-allowed': testState.status !== 'success' }">
        Next Step
        <i class="fas fa-arrow-right"></i>
      </button>
    </div>
  </div>
</template>

<style scoped>
/* Config Section */
.config-section {
  display: flex;
  flex-direction: column;
}

.section-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 0.5rem;
}

.section-description {
  color: var(--color-text-muted);
  font-size: 0.9rem;
  line-height: 1.5;
  margin-bottom: 1.5rem;
}


/* Selection Header */
.selection-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--color-border-light);
}

.selection-info {
  flex: 1;
}

.clear-btn {
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: 0.8rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: var(--transition-base);
  padding: 0.25rem 0.5rem;
  border-radius: var(--border-radius-sm);
}

.clear-btn:hover {
  color: var(--color-primary-hover);
  background: var(--color-bg-interactive);
}

/* Selection Grid */
.selection-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}

.users-grid {
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
}

.selection-item {
  cursor: pointer;
  padding: 1rem;
  border: 2px solid var(--color-border-medium);
  border-radius: var(--border-radius-sm);
  text-align: center;
  color: var(--color-text-primary);
  transition: var(--transition-base);
  position: relative;
  background: var(--color-bg-interactive);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.selection-item:hover {
  border-color: var(--color-primary);
  transform: translateY(-2px);
  box-shadow: var(--shadow-base);
}

.selection-item.selected {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
  box-shadow: 0 4px 12px rgba(143, 145, 146, 0.3);
}

.selection-check {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: white;
  color: var(--color-primary);
  border-radius: 50%;
  width: 1.25rem;
  height: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: bold;
}

.selection-icon {
  font-size: 1.5rem;
  opacity: 0.8;
}

.selection-item.selected .selection-icon {
  opacity: 1;
}

.selection-name {
  font-weight: 500;
  font-size: 0.9rem;
  margin: 0;
  line-height: 1.2;
}

/* Anime Badge */
.anime-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.2rem 0.5rem;
  border-radius: 1rem;
  font-size: 0.7rem;
  font-weight: 600;
  border: 1px solid rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: var(--transition-base);
}

.anime-badge:hover {
  background: rgba(255, 255, 255, 0.25);
  color: white;
}

.anime-badge.anime-active {
  background: #e74c9c;
  border-color: #e74c9c;
  color: white;
  box-shadow: 0 2px 8px rgba(231, 76, 156, 0.4);
}

.anime-badge.anime-active:hover {
  background: #d63d8c;
  border-color: #d63d8c;
}

.anime-badge-text {
  line-height: 1;
}

/* Responsive */
@media (max-width: 768px) {
  .settings-card {
    padding: 1rem;
  }

  .input-group {
    flex-direction: column;
    align-items: stretch;
  }

  .selection-grid {
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }

  .users-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .selection-item {
    padding: 0.75rem;
  }

  .selection-header {
    flex-direction: column;
    align-items: stretch;
  }

  .clear-btn {
    align-self: flex-start;
  }
}
</style>

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
      selectedLibraries: [],
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
        handleUrlInput() {
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
            const index = this.selectedLibraries.findIndex(lib => lib.id === library.ItemId);
            if (index === -1) {
                const isAnime = library.Name.toLowerCase().includes('anime');
                this.selectedLibraries.push({
                    id: library.ItemId,
                    name: library.Name,
                    is_anime: isAnime
                });
            } else {
                this.selectedLibraries.splice(index, 1);
            }
            this.emitLibraryConfig();
        },

        toggleAnimeFlag(libraryId) {
            const lib = this.selectedLibraries.find(l => l.id === libraryId);
            if (lib) {
                lib.is_anime = !lib.is_anime;
                this.emitLibraryConfig();
            }
        },

        isAnimeLibrary(libraryId) {
            const lib = this.selectedLibraries.find(l => l.id === libraryId);
            return lib ? lib.is_anime : false;
        },

        emitLibraryConfig() {
            const config = this.selectedLibraries
                .filter(lib => lib.id && lib.name)
                .map(lib => ({ id: lib.id, name: lib.name, is_anime: lib.is_anime }));
            this.$emit('update-config', `JELLYFIN_LIBRARIES`, config);
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
            this.selectedLibraries = [];
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
            return this.selectedLibraries.some(lib => lib.id === libraryId);
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
                this.selectedLibraries = this.config[`JELLYFIN_LIBRARIES`].map(lib => ({
                    id: lib.id,
                    name: lib.name,
                    is_anime: lib.is_anime || false
                }));
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
