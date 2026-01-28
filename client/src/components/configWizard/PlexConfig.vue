<template>
    <div class="config-section">
        <h3 class="section-title">Plex Configuration</h3>
        <p class="section-description">
            Connect to your Plex account to access your servers and libraries.
        </p>

        <!-- Connection Settings Card -->
        <div class="settings-card">
            <h4 class="card-title">Connection Settings</h4>

            <!-- Login Button -->
            <div v-if="!isLoggedIn" class="form-group">
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
                <p class="form-help text-center">
                    <i class="fas fa-lock"></i>
                    Secure authentication via Plex.tv
                </p>
            </div>

            <!-- Server Selection -->
            <div v-if="servers.length > 0" class="form-group">
                <label for="server-selection" class="form-label">
                    Select Plex Server
                </label>
                <div class="input-group">
                    <div class="flex-1">
                        <BaseDropdown
                            :model-value="selectedServerValue"
                            :options="serverOptions"
                            placeholder="Select a server..."
                            id="server-selection"
                            @change="handleServerChange"
                        />
                    </div>

                    <button
                        v-if="!manualConfiguration"
                        @click="fetchLibraries"
                        :disabled="loadingLibraries"
                        class="btn btn-test">
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
                <p class="form-help">
                    <i class="fas fa-info-circle"></i>
                    🔒 indicates secure HTTPS connection
                </p>
            </div>

            <!-- Manual Configuration -->
            <div v-if="manualConfiguration || selectedServer === 'manual'" class="form-group">
                <h4 class="form-label">Manual Server Configuration</h4>

                <label for="manual-address" class="form-label">
                    Server Address
                </label>

                <div class="input-group">
                    <input
                        type="url"
                        v-model="manualServerAddress"
                        @input="$emit('update-config', 'PLEX_API_URL', $event.target.value)"
                        class="form-input flex-1"
                        id="manual-address"
                        placeholder="http://192.168.1.10:32400">

                    <button
                        @click="fetchLibraries"
                        :disabled="loadingLibraries || !manualServerAddress"
                        class="btn btn-test">
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
                <p class="form-help">
                    <i class="fas fa-info-circle"></i>
                    Example: http://192.168.1.100:32400 or https://plex.example.com
                </p>
            </div>

            <!-- Success Message -->
            <div v-if="libraries.length > 0" class="alert alert-success">
                <i class="fas fa-check-circle"></i>
                <span>Successfully connected! Found {{ libraries.length }} libraries and {{ users.length }} users.</span>
            </div>
        </div>

        <!-- Library Selection Card -->
        <div v-if="libraries.length > 0" class="settings-card">
            <div class="selection-header">
                <div class="selection-info">
                    <h4 class="card-title">Select Libraries</h4>
                    <p class="section-description">
                        {{ selectedLibraries.length > 0 ? `${selectedLibraries.length} selected` : 'Select libraries or leave empty for all' }}
                    </p>
                </div>
                <button
                    v-if="selectedLibraries.length > 0"
                    @click="clearLibrarySelection"
                    class="clear-btn">
                    <i class="fas fa-times-circle"></i>
                    Clear Selection
                </button>
            </div>

            <div class="selection-grid">
                <div
                    v-for="library in libraries"
                    :key="library.key"
                    @click="toggleLibrarySelection(library)"
                    :class="['selection-item', { 'selected': isSelected(library.key) }]">

                    <div v-if="isSelected(library.key)" class="selection-check">
                        <i class="fas fa-check"></i>
                    </div>

                    <i :class="getLibraryIcon(library.type)" class="selection-icon"></i>

                    <p class="selection-name">{{ library.title }}</p>
                </div>
            </div>
        </div>

        <!-- Users Selection Card -->
        <div v-if="users.length > 0" class="settings-card">
            <div class="selection-header">
                <div class="selection-info">
                    <h4 class="card-title">Select Users</h4>
                    <p class="section-description">
                        {{ selectedUsers.length > 0 ? `${selectedUsers.length} selected` : 'Select users or leave empty for all' }}
                    </p>
                </div>
                <button
                    v-if="selectedUsers && selectedUsers.length > 0"
                    @click="clearUserSelection"
                    class="clear-btn">
                    <i class="fas fa-times-circle"></i>
                    Clear Selection
                </button>
            </div>

            <div class="selection-grid users-grid">
                <div
                    v-for="user in users"
                    :key="user.id"
                    @click="toggleUserSelection(user)"
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
        
            <button @click="$emit('next-step')" :disabled="libraries.length <= 0"
              class="btn-primary w-full flex items-center justify-center gap-2 py-4 px-8"
              :class="{ 'opacity-50 cursor-not-allowed': libraries.length <= 0 }">
              Next Step
              <i class="fas fa-arrow-right"></i>
            </button>
        </div>
    </div>
</template>

<script>
import plexApi from '../../api/plexApi';
import BaseDropdown from '../common/BaseDropdown.vue';

export default {
    components: {
        BaseDropdown
    },
    ...plexApi,
    computed: {
        serverOptions() {
            const connections = this.getServerConnections();
            const options = connections.map((connection, index) => ({
                label: `${connection.serverName}${connection.localLabel || ''} - ${connection.address}:${connection.port} (${connection.protocol}) ${connection.secure ? '🔒' : '⚠️'}`,
                value: `${index}` // Uso l'indice come value
            }));

            // Aggiungo l'opzione manuale
            options.push({
                label: '⚙️ Manual Configuration',
                value: 'manual'
            });

            return options;
        },
        selectedServerValue() {
            if (this.selectedServerConnection === 'manual') {
                return 'manual';
            }
            if (this.selectedServerConnection) {
                const connections = this.getServerConnections();
                const index = connections.findIndex(conn =>
                    conn.address === this.selectedServerConnection.address &&
                    conn.port === this.selectedServerConnection.port &&
                    conn.protocol === this.selectedServerConnection.protocol
                );
                return index >= 0 ? `${index}` : null;
            }
            return null;
        }
    },
    methods: {
        ...plexApi.methods,

        handleServerChange(value) {
            if (value === 'manual') {
                this.selectedServerConnection = 'manual';
            } else {
                const connections = this.getServerConnections();
                const index = parseInt(value);
                this.selectedServerConnection = connections[index];
            }
            this.updateSelectedServer();
        },

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
            this.selectedLibraries = [];
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

/* Input Group */
.input-group {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

/* Plex Colors */
.bg-plex {
    background-color: #e5a00d;
}

.bg-plex:hover {
    background-color: #cc8f0b;
}

.bg-plex-dark {
    background-color: #cc8f0b;
}

:root {
    --color-plex: #e5a00d;
    --color-plex-hover: #cc8f0b;
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
  box-shadow: var(--shadow-md);
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