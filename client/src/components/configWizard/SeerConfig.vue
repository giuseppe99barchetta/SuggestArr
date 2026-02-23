<template>
    <div class="config-section">
        <h3 class="section-title">Request Service Configuration</h3>
        <p class="section-description">
            Connect to Overseerr or Jellyseerr to manage content requests automatically.
        </p>

        <!-- Connection Settings Card -->
        <div class="settings-card">
            <h4 class="card-title">Connection Settings</h4>

            <!-- Server URL Input -->
            <div class="form-group">
                <label for="SEER_API_URL" class="form-label">
                    Server URL
                </label>
                <input type="url" :value="config[`SEER_API_URL`]" @input="handleUrlInput($event.target.value)"
                    @blur="updateSeerUrl($event.target.value)" class="form-input" id="SEER_API_URL"
                    placeholder="http://overseerr.example.com:5055">
                <p class="form-help">
                    <i class="fas fa-info-circle"></i>
                    Example: http://192.168.1.100:5055 or https://overseerr.example.com
                </p>
            </div>

            <!-- API Key Input with Test Button -->
            <div class="form-group">
                <label for="SEER_TOKEN" class="form-label">
                    API Key
                </label>
                <div class="input-group">
                    <input type="password" :value="config[`SEER_TOKEN`]" @input="handleTokenInput($event.target.value)"
                        :disabled="testState.isTesting" class="form-input" id="SEER_TOKEN"
                        placeholder="Your Overseerr/Jellyseerr API Key">

                    <button type="button" @click="testApi" :disabled="testState.isTesting || !canTest" :class="[
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
                            <span class="hidden sm:inline">Testing</span>
                        </span>
                        <span v-else-if="testState.status === 'success'" class="btn-content">
                            <i class="fas fa-check"></i>
                            <span class="hidden sm:inline">Connected</span>
                        </span>
                        <span v-else-if="testState.status === 'fail'" class="btn-content">
                            <i class="fas fa-times"></i>
                            <span class="hidden sm:inline">Failed</span>
                        </span>
                        <span v-else class="btn-content">
                            <i class="fas fa-plug"></i>
                            <span class="hidden sm:inline">Connect</span>
                        </span>
                    </button>
                </div>

                <div class="help-section">
                    <button type="button" @click="showApiKeyHelp = !showApiKeyHelp" class="help-link">
                        <i class="fas fa-question-circle"></i>
                        How to get your API Key?
                    </button>

                    <div v-if="showApiKeyHelp"
                        class="help-content">
                        <ol class="help-list">
                            <li>Open Overseerr/Jellyseerr web interface</li>
                            <li>Navigate to Settings → General</li>
                            <li>Scroll to "API Key" section</li>
                            <li>Copy the API key and paste it above</li>
                        </ol>
                    </div>
                </div>
            </div>

            <!-- Success Message -->
            <div v-if="testState.status === 'success'"
                class="alert alert-success">
                <i class="fas fa-check-circle"></i>
                <span>Successfully connected! Found {{ users.length }} local user(s).</span>
            </div>

            <!-- Error Message -->
            <div v-if="testState.status === 'fail'"
                class="alert alert-danger"
                role="alert">
                <i class="fas fa-exclamation-circle"></i>
                <span>Failed to connect. Please verify your URL and API Key.</span>
            </div>
        </div>

        <!-- User Authentication Card -->
        <div v-if="testState.status === 'success'" class="settings-card">
            <h4 class="card-title">
                <i class="fas fa-user-shield"></i>
                User Authentication (Optional)
            </h4>
            <p class="section-description">
                Select a local user to make requests on their behalf. This is useful for manual approval workflows.
                If not configured, the administrator account will be used.
            </p>

            <div v-if="users.length > 0">
                <!-- User Selection -->
                <div class="form-group">
                    <label for="SEER_USER_NAME" class="form-label">
                        Select Local User
                    </label>
                    <BaseDropdown
                        v-model="selectedUser"
                        :options="userOptions"
                        placeholder="Select a user..."
                        id="SEER_USER_NAME"
                        @change="updateSeerUser"
                    />
                </div>

                <!-- Password Field -->
                <div class="form-group">
                    <label for="SEER_USER_PSW" class="form-label">
                        Password
                    </label>
                    <input type="password" v-model="userPassword"
                        @input="$emit('update-config', `SEER_USER_PSW`, userPassword)" class="form-input"
                        id="SEER_USER_PSW" placeholder="Enter password" autocomplete="new-password">
                </div>

                <!-- Authenticate Button -->
                <button @click="authenticateUser" :disabled="isAuthenticating || !selectedUser || !userPassword" :class="{
                    'btn-success': authenticated,
                    'btn-primary': !authenticated,
                }" class="btn w-full mt-4">
                    <i v-if="isAuthenticating" class="fas fa-spinner fa-spin"></i>
                    <i v-else-if="authenticated" class="fas fa-check-circle"></i>
                    <i v-else class="fas fa-sign-in-alt"></i>
                    <span v-if="isAuthenticating">Authenticating...</span>
                    <span v-else-if="authenticated">Authenticated Successfully</span>
                    <span v-else>Authenticate User</span>
                </button>
            </div>

            <!-- No Local Users Message -->
            <div v-else class="alert alert-warning">
                <i class="fas fa-exclamation-triangle"></i>
                <div>
                    <p class="font-semibold mb-1">No Local Users Found</p>
                    <p class="text-xs mb-2">
                        The administrator account will be used for requests. You can create a local user if needed.
                    </p>
                    <a :href="`${config[`SEER_API_URL`]}/users`" target="_blank" rel="noopener noreferrer"
                       class="link flex items-center gap-1">
                        <i class="fas fa-external-link-alt"></i>
                        Create a new local user
                    </a>
                </div>
            </div>
        </div>

        <!-- Download Profiles Configuration Card -->
        <div v-if="testState.status === 'success'" class="settings-card">
            <h4 class="card-title">
                <i class="fas fa-download"></i>
                Download Profiles (Optional)
            </h4>
            <p class="section-description">
                Configure download profiles for your content requests.
                Select which Radarr/Sonarr server, quality profile, and root folder to use when requesting content via Overseerr.
                If not configured, Overseerr's default settings will be used.
            </p>

            <!-- Load Servers Button -->
            <button @click="fetchArrServers" :disabled="loadingServers" class="btn btn-primary mb-4">
                <i :class="loadingServers ? 'fas fa-spinner fa-spin' : 'fas fa-server'"></i>
                {{ loadingServers ? 'Loading...' : (radarrServers.length > 0 || sonarrServers.length > 0 ? 'Reload Servers' : 'Load Radarr/Sonarr Servers') }}
            </button>

            <!-- Default Movie Profile (Radarr) -->
            <div v-if="radarrServers.length > 0" class="anime-profile-section">
                <h5 class="subsection-title">
                    <i class="fas fa-film"></i>
                    Movie Profile (Radarr)
                </h5>

                <div class="form-group">
                    <label class="form-label">Radarr Server</label>
                    <BaseDropdown
                        v-model="defaultMovieServerId"
                        :options="radarrServerOptions"
                        placeholder="Select Radarr server..."
                        @change="onDefaultMovieServerChange"
                    />
                </div>

                <div v-if="defaultMovieProfiles.length > 0" class="form-group">
                    <label class="form-label">Quality Profile</label>
                    <BaseDropdown
                        v-model="defaultMovieProfileId"
                        :options="defaultMovieProfiles"
                        placeholder="Select quality profile..."
                        @change="updateProfileConfig"
                    />
                </div>

                <div v-if="defaultMovieRootFolders.length > 0" class="form-group">
                    <label class="form-label">Root Folder</label>
                    <BaseDropdown
                        v-model="defaultMovieRootFolder"
                        :options="defaultMovieRootFolders"
                        placeholder="Select root folder..."
                        @change="updateProfileConfig"
                    />
                </div>
            </div>

            <!-- Default TV Profile (Sonarr) -->
            <div v-if="sonarrServers.length > 0" class="anime-profile-section">
                <h5 class="subsection-title">
                    <i class="fas fa-tv"></i>
                    TV Show Profile (Sonarr)
                </h5>

                <div class="form-group">
                    <label class="form-label">Sonarr Server</label>
                    <BaseDropdown
                        v-model="defaultTvServerId"
                        :options="sonarrServerOptions"
                        placeholder="Select Sonarr server..."
                        @change="onDefaultTvServerChange"
                    />
                </div>

                <div v-if="defaultTvProfiles.length > 0" class="form-group">
                    <label class="form-label">Quality Profile</label>
                    <BaseDropdown
                        v-model="defaultTvProfileId"
                        :options="defaultTvProfiles"
                        placeholder="Select quality profile..."
                        @change="updateProfileConfig"
                    />
                </div>

                <div v-if="defaultTvRootFolders.length > 0" class="form-group">
                    <label class="form-label">Root Folder</label>
                    <BaseDropdown
                        v-model="defaultTvRootFolder"
                        :options="defaultTvRootFolders"
                        placeholder="Select root folder..."
                        @change="updateProfileConfig"
                    />
                </div>
            </div>

            <!-- Anime Movie Profile (Radarr) -->
            <div v-if="radarrServers.length > 0 && hasAnimeLibraries" class="anime-profile-section">
                <h5 class="subsection-title">
                    <i class="fas fa-torii-gate"></i>
                    Anime Movie Profile (Radarr)
                </h5>

                <div class="form-group">
                    <label class="form-label">Radarr Server</label>
                    <BaseDropdown
                        v-model="animeMovieServerId"
                        :options="radarrServerOptions"
                        placeholder="Select Radarr server..."
                        @change="onAnimeMovieServerChange"
                    />
                </div>

                <div v-if="animeMovieProfiles.length > 0" class="form-group">
                    <label class="form-label">Quality Profile</label>
                    <BaseDropdown
                        v-model="animeMovieProfileId"
                        :options="animeMovieProfiles"
                        placeholder="Select quality profile..."
                        @change="updateProfileConfig"
                    />
                </div>

                <div v-if="animeMovieRootFolders.length > 0" class="form-group">
                    <label class="form-label">Root Folder</label>
                    <BaseDropdown
                        v-model="animeMovieRootFolder"
                        :options="animeMovieRootFolders"
                        placeholder="Select root folder..."
                        @change="updateProfileConfig"
                    />
                </div>
            </div>

            <!-- Anime TV Profile (Sonarr) -->
            <div v-if="sonarrServers.length > 0 && hasAnimeLibraries" class="anime-profile-section">
                <h5 class="subsection-title">
                    <i class="fas fa-torii-gate"></i>
                    Anime TV Profile (Sonarr)
                </h5>

                <div class="form-group">
                    <label class="form-label">Sonarr Server</label>
                    <BaseDropdown
                        v-model="animeTvServerId"
                        :options="sonarrServerOptions"
                        placeholder="Select Sonarr server..."
                        @change="onAnimeTvServerChange"
                    />
                </div>

                <div v-if="animeTvProfiles.length > 0" class="form-group">
                    <label class="form-label">Quality Profile</label>
                    <BaseDropdown
                        v-model="animeTvProfileId"
                        :options="animeTvProfiles"
                        placeholder="Select quality profile..."
                        @change="updateProfileConfig"
                    />
                </div>

                <div v-if="animeTvRootFolders.length > 0" class="form-group">
                    <label class="form-label">Root Folder</label>
                    <BaseDropdown
                        v-model="animeTvRootFolder"
                        :options="animeTvRootFolders"
                        placeholder="Select root folder..."
                        @change="updateProfileConfig"
                    />
                </div>
            </div>

            <!-- Info when no servers loaded -->
            <div v-if="!loadingServers && radarrServers.length === 0 && sonarrServers.length === 0 && serversLoaded" class="alert alert-warning">
                <i class="fas fa-exclamation-triangle"></i>
                <span>No Radarr/Sonarr servers found in Overseerr. Make sure they are configured in Overseerr settings.</span>
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

/* Input Group */
.input-group {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.link {
  color: var(--color-primary);
  text-decoration: none;
  border-bottom: 1px dotted var(--color-primary);
  transition: all 0.2s ease;
  font-size: 0.8125rem;
}

.link:hover {
  color: var(--color-primary-hover);
  border-bottom-style: solid;
}

.alert-warning {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid var(--color-warning);
  color: var(--color-warning);
}

/* Anime Profile Sections */
.anime-profile-section {
  padding: 1rem;
  margin-bottom: 1rem;
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  background: var(--color-bg-interactive);
}

.subsection-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--color-border-light);
}

.mb-4 {
  margin-bottom: 1rem;
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
}
</style>

<script>
import { testJellyseerApi, authenticateUser, fetchRadarrServers, fetchSonarrServers } from '../../api/api';
import BaseDropdown from '../common/BaseDropdown.vue';

export default {
    components: {
        BaseDropdown
    },
    props: ['config'],
    data() {
        return {
            users: [],
            selectedUser: null,
            userPassword: '',
            authenticated: false,
            isAuthenticating: false,
            testState: {
                status: null,
                isTesting: false
            },
            showApiKeyHelp: false,
            // Anime profile configuration
            loadingServers: false,
            serversLoaded: false,
            radarrServers: [],
            sonarrServers: [],
            defaultMovieServerId: null,
            defaultMovieProfileId: null,
            defaultMovieRootFolder: null,
            defaultTvServerId: null,
            defaultTvProfileId: null,
            defaultTvRootFolder: null,
            animeMovieServerId: null,
            animeMovieProfileId: null,
            animeMovieRootFolder: null,
            animeTvServerId: null,
            animeTvProfileId: null,
            animeTvRootFolder: null
        };
    },
    computed: {
        canTest() {
            return this.config[`SEER_API_URL`] && this.config[`SEER_TOKEN`];
        },
        userOptions() {
            return this.users.map(user => ({
                label: `${user.name}${user.email ? ` (${user.email})` : ''}`,
                value: user.email || user.name
            }));
        },
        hasAnimeLibraries() {
            const jellyfinLibs = this.config.JELLYFIN_LIBRARIES || [];
            const plexLibs = this.config.PLEX_LIBRARIES || [];
            return [...jellyfinLibs, ...plexLibs].some(lib =>
                typeof lib === 'object' && lib.is_anime
            );
        },
        radarrServerOptions() {
            return this.radarrServers.map(server => ({
                label: server.name || `Radarr (ID: ${server.id})`,
                value: String(server.id)
            }));
        },
        sonarrServerOptions() {
            return this.sonarrServers.map(server => ({
                label: server.name || `Sonarr (ID: ${server.id})`,
                value: String(server.id)
            }));
        },
        defaultMovieProfiles() {
            const server = this.radarrServers.find(s => String(s.id) === String(this.defaultMovieServerId));
            if (!server || !server.profiles) return [];
            return server.profiles.map(p => ({
                label: p.name,
                value: String(p.id)
            }));
        },
        defaultMovieRootFolders() {
            const server = this.radarrServers.find(s => String(s.id) === String(this.defaultMovieServerId));
            if (!server || !server.rootFolders) return [];
            return server.rootFolders.map(rf => ({
                label: rf.path,
                value: rf.path
            }));
        },
        defaultTvProfiles() {
            const server = this.sonarrServers.find(s => String(s.id) === String(this.defaultTvServerId));
            if (!server || !server.profiles) return [];
            return server.profiles.map(p => ({
                label: p.name,
                value: String(p.id)
            }));
        },
        defaultTvRootFolders() {
            const server = this.sonarrServers.find(s => String(s.id) === String(this.defaultTvServerId));
            if (!server || !server.rootFolders) return [];
            return server.rootFolders.map(rf => ({
                label: rf.path,
                value: rf.path
            }));
        },
        animeMovieProfiles() {
            const server = this.radarrServers.find(s => String(s.id) === String(this.animeMovieServerId));
            if (!server || !server.profiles) return [];
            return server.profiles.map(p => ({
                label: p.name,
                value: String(p.id)
            }));
        },
        animeMovieRootFolders() {
            const server = this.radarrServers.find(s => String(s.id) === String(this.animeMovieServerId));
            if (!server || !server.rootFolders) return [];
            return server.rootFolders.map(rf => ({
                label: rf.path,
                value: rf.path
            }));
        },
        animeTvProfiles() {
            const server = this.sonarrServers.find(s => String(s.id) === String(this.animeTvServerId));
            if (!server || !server.profiles) return [];
            return server.profiles.map(p => ({
                label: p.name,
                value: String(p.id)
            }));
        },
        animeTvRootFolders() {
            const server = this.sonarrServers.find(s => String(s.id) === String(this.animeTvServerId));
            if (!server || !server.rootFolders) return [];
            return server.rootFolders.map(rf => ({
                label: rf.path,
                value: rf.path
            }));
        }
    },
    methods: {
        handleUrlInput(_value) {
            if (this.testState.status !== null) {
                this.testState.status = null;
                this.users = [];
                this.authenticated = false;
            }
        },
        
        handleTokenInput(value) {
            this.$emit('update-config', `SEER_TOKEN`, value);
            if (this.testState.status !== null) {
                this.testState.status = null;
                this.users = [];
                this.authenticated = false;
            }
        },

        autoTestAndAuthenticate() {
            if (this.canTest) {
                this.testApi();
            }

            if (this.config[`SEER_USER_NAME`] && this.config[`SEER_USER_PSW`]) {
                this.userPassword = this.config[`SEER_USER_PSW`];
                this.selectedUser = this.config[`SEER_USER_NAME`];
                this.authenticated = true;
            }
        },

        testApi() {
            if (!this.canTest) return;
            
            this.testState.isTesting = true;
            this.testState.status = null;
            
            testJellyseerApi(this.config[`SEER_API_URL`], this.config[`SEER_TOKEN`])
                .then(response => {
                    this.users = response.data.users.filter(user => user.isLocal);
                    this.testState.status = 'success';
                    this.loadSelectedUser();
                })
                .catch(error => {
                    console.error('Error testing API:', error);
                    this.testState.status = 'fail';
                    this.users = [];
                })
                .finally(() => {
                    this.testState.isTesting = false;
                });
        },

        authenticateUser() {
            if (!this.selectedUser || !this.userPassword) return;
            
            this.isAuthenticating = true;
            
            authenticateUser(
                this.config[`SEER_API_URL`], 
                this.config[`SEER_TOKEN`], 
                this.config[`SEER_USER_NAME`], 
                this.userPassword
            )
                .then((response) => {
                    this.authenticated = true;
                    this.$emit('update-config', 'SEER_SESSION_TOKEN', response.data.session_token);
                    this.$toast.open({
                        message: '✅ User authenticated successfully!',
                        type: 'success',
                        duration: 3000,
                        position: 'top-right'
                    });
                })
                .catch(error => {
                    console.error('Authentication error:', error);
                    this.authenticated = false;
                    this.$toast.open({
                        message: '❌ Incorrect username or password',
                        type: 'error',
                        duration: 5000,
                        position: 'top-right'
                    });
                })
                .finally(() => {
                    this.isAuthenticating = false;
                });
        },

        updateSeerUser() {
            if (this.selectedUser) {
                this.$emit('update-config', 'SEER_USER_NAME', this.selectedUser);
                this.authenticated = false; // Reset auth status when user changes
            }
        },

        updateSeerUrl(url) {
            const trimmedUrl = url.trim().replace(/\/+$/, '');
            this.$emit('update-config', 'SEER_API_URL', trimmedUrl);
        },

        loadSelectedUser() {
            if (this.config.SEER_USER_NAME) {
                this.selectedUser = this.config.SEER_USER_NAME;
            }
            if (this.config.SEER_USER_PSW) {
                this.userPassword = this.config.SEER_USER_PSW;
            }
        },

        // Anime profile methods
        async fetchArrServers() {
            this.loadingServers = true;
            this.serversLoaded = false;
            const url = this.config.SEER_API_URL;
            const token = this.config.SEER_TOKEN;
            const sessionToken = this.config.SEER_SESSION_TOKEN;

            try {
                const [radarrRes, sonarrRes] = await Promise.all([
                    fetchRadarrServers(url, token, sessionToken),
                    fetchSonarrServers(url, token, sessionToken)
                ]);
                this.radarrServers = radarrRes.data.servers || [];
                this.sonarrServers = sonarrRes.data.servers || [];
                this.loadSavedProfileConfig();
            } catch (error) {
                console.error('Error fetching Radarr/Sonarr servers:', error);
                this.radarrServers = [];
                this.sonarrServers = [];
            } finally {
                this.loadingServers = false;
                this.serversLoaded = true;
            }
        },

        onDefaultMovieServerChange(value) {
            this.defaultMovieServerId = value;
            this.defaultMovieProfileId = null;
            this.defaultMovieRootFolder = null;
            this.updateProfileConfig();
        },

        onDefaultTvServerChange(value) {
            this.defaultTvServerId = value;
            this.defaultTvProfileId = null;
            this.defaultTvRootFolder = null;
            this.updateProfileConfig();
        },

        onAnimeMovieServerChange(value) {
            this.animeMovieServerId = value;
            this.animeMovieProfileId = null;
            this.animeMovieRootFolder = null;
            this.updateProfileConfig();
        },

        onAnimeTvServerChange(value) {
            this.animeTvServerId = value;
            this.animeTvProfileId = null;
            this.animeTvRootFolder = null;
            this.updateProfileConfig();
        },

        updateProfileConfig() {
            const profileConfig = {};

            if (this.defaultMovieServerId) {
                profileConfig.default_movie = {
                    serverId: parseInt(this.defaultMovieServerId)
                };
                if (this.defaultMovieProfileId) {
                    profileConfig.default_movie.profileId = parseInt(this.defaultMovieProfileId);
                }
                if (this.defaultMovieRootFolder) {
                    profileConfig.default_movie.rootFolder = this.defaultMovieRootFolder;
                }
            }

            if (this.defaultTvServerId) {
                profileConfig.default_tv = {
                    serverId: parseInt(this.defaultTvServerId)
                };
                if (this.defaultTvProfileId) {
                    profileConfig.default_tv.profileId = parseInt(this.defaultTvProfileId);
                }
                if (this.defaultTvRootFolder) {
                    profileConfig.default_tv.rootFolder = this.defaultTvRootFolder;
                }
            }

            if (this.animeMovieServerId) {
                profileConfig.anime_movie = {
                    serverId: parseInt(this.animeMovieServerId)
                };
                if (this.animeMovieProfileId) {
                    profileConfig.anime_movie.profileId = parseInt(this.animeMovieProfileId);
                }
                if (this.animeMovieRootFolder) {
                    profileConfig.anime_movie.rootFolder = this.animeMovieRootFolder;
                }
            }

            if (this.animeTvServerId) {
                profileConfig.anime_tv = {
                    serverId: parseInt(this.animeTvServerId)
                };
                if (this.animeTvProfileId) {
                    profileConfig.anime_tv.profileId = parseInt(this.animeTvProfileId);
                }
                if (this.animeTvRootFolder) {
                    profileConfig.anime_tv.rootFolder = this.animeTvRootFolder;
                }
            }

            this.$emit('update-config', 'SEER_ANIME_PROFILE_CONFIG', profileConfig);
        },

        loadSavedProfileConfig() {
            const saved = this.config.SEER_ANIME_PROFILE_CONFIG;
            if (!saved || typeof saved !== 'object') return;

            if (saved.default_movie) {
                this.defaultMovieServerId = saved.default_movie.serverId != null ? String(saved.default_movie.serverId) : null;
                this.defaultMovieProfileId = saved.default_movie.profileId != null ? String(saved.default_movie.profileId) : null;
                this.defaultMovieRootFolder = saved.default_movie.rootFolder || null;
            }
            if (saved.default_tv) {
                this.defaultTvServerId = saved.default_tv.serverId != null ? String(saved.default_tv.serverId) : null;
                this.defaultTvProfileId = saved.default_tv.profileId != null ? String(saved.default_tv.profileId) : null;
                this.defaultTvRootFolder = saved.default_tv.rootFolder || null;
            }
            if (saved.anime_movie) {
                this.animeMovieServerId = saved.anime_movie.serverId != null ? String(saved.anime_movie.serverId) : null;
                this.animeMovieProfileId = saved.anime_movie.profileId != null ? String(saved.anime_movie.profileId) : null;
                this.animeMovieRootFolder = saved.anime_movie.rootFolder || null;
            }
            if (saved.anime_tv) {
                this.animeTvServerId = saved.anime_tv.serverId != null ? String(saved.anime_tv.serverId) : null;
                this.animeTvProfileId = saved.anime_tv.profileId != null ? String(saved.anime_tv.profileId) : null;
                this.animeTvRootFolder = saved.anime_tv.rootFolder || null;
            }
        }
    },
    mounted() {
        this.autoTestAndAuthenticate();
    }
};
</script>
