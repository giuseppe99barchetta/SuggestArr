<template>
  <div class="settings-services">
    <!-- Section header hidden in wizard mode (wizard shell provides its own header) -->
    <div v-if="!wizardMode" class="section-header">
      <h2>Service Configuration</h2>
      <p>Configure external service connections</p>
    </div>

    <div class="services-stack">
      <!-- TMDB + OMDb: side by side in dashboard, single card in wizard -->
      <div v-if="showSection('tmdb') || showSection('omdb')" :class="!wizardMode ? 'rating-apis-row' : ''">
        <!-- TMDB -->
        <div v-if="showSection('tmdb')" :class="wizardMode ? '' : 'service-card'">
          <div v-if="!wizardMode" class="service-header">
            <h3><i class="fas fa-film"></i> TMDB API</h3>
            <span class="status-badge" :class="getTmdbStatus">
              <span class="status-dot"></span>
              {{ getTmdbStatusText }}
            </span>
          </div>

          <div class="form-group">
            <label for="tmdbApiKey">API Key</label>
            <div class="input-group">
              <input
                id="tmdbApiKey"
                v-model="localConfig.TMDB_API_KEY"
                :type="showTmdbKey ? 'text' : 'password'"
                placeholder="Enter your TMDB API key"
                class="form-control"
                :disabled="isLoading"
              />
              <button @click="showTmdbKey = !showTmdbKey" type="button" class="btn btn-outline btn-sm" :disabled="isLoading">
                <i :class="showTmdbKey ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
              </button>
            </div>
            <small class="form-help">
              Get one from <a href="https://www.themoviedb.org/settings/api" target="_blank" class="link">TMDB Settings</a>
            </small>
          </div>

          <button
            @click="testTmdbConnection"
            class="btn btn-outline btn-block"
            :disabled="isLoading || !localConfig.TMDB_API_KEY || isTmdbTesting"
          >
            <i v-if="isTmdbTesting" class="fas fa-spinner fa-spin"></i>
            <i v-else-if="wizardMode && wizardTmdbConnected" class="fas fa-check"></i>
            <i v-else class="fas fa-plug"></i>
            {{ isTmdbTesting ? 'Testing...' : (wizardMode && wizardTmdbConnected ? 'Connected ✓' : 'Test Connection') }}
          </button>
        </div>

        <!-- OMDb (IMDB ratings) -->
        <div v-if="showSection('omdb')" :class="wizardMode ? '' : 'service-card'">
          <div v-if="!wizardMode" class="service-header">
            <h3><i class="fas fa-star"></i> IMDB (via OMDb)</h3>
            <span class="status-badge" :class="getOmdbStatus">
              <span class="status-dot"></span>
              {{ getOmdbStatusText }}
            </span>
          </div>

          <div class="form-group">
            <label for="omdbApiKey">API Key</label>
            <div class="input-group">
              <input
                id="omdbApiKey"
                v-model="localConfig.OMDB_API_KEY"
                :type="showOmdbKey ? 'text' : 'password'"
                placeholder="Enter your OMDb API key (optional)"
                class="form-control"
                :disabled="isLoading"
              />
              <button @click="showOmdbKey = !showOmdbKey" type="button" class="btn btn-outline btn-sm" :disabled="isLoading">
                <i :class="showOmdbKey ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
              </button>
            </div>
            <small class="form-help">
              Optional — needed only when rating source is set to IMDB or Both.
              Free key (1,000 req/day) at <a href="https://www.omdbapi.com/apikey.aspx" target="_blank" class="link">omdbapi.com</a>
            </small>
          </div>

          <button
            @click="testOmdbConnection"
            class="btn btn-outline btn-block"
            :disabled="isLoading || !localConfig.OMDB_API_KEY || omdbTesting"
          >
            <i v-if="omdbTesting" class="fas fa-spinner fa-spin"></i>
            <i v-else-if="omdbConnected" class="fas fa-check"></i>
            <i v-else class="fas fa-plug"></i>
            {{ omdbTesting ? 'Testing...' : (omdbConnected ? 'Connected' : 'Test Connection') }}
          </button>

          <!-- About IMDB Filtering -->
          <div class="omdb-info-section">
            <button class="collapsible-toggle" @click="omdbInfoExpanded = !omdbInfoExpanded">
              <i class="fas fa-chevron-right toggle-arrow" :class="{ expanded: omdbInfoExpanded }"></i>
              <span>What is IMDB filtering?</span>
            </button>
            <div class="collapsible-content" v-show="omdbInfoExpanded">
              <div class="omdb-info-body">
                <p class="omdb-info-lead">
                  IMDB filtering uses the <a href="https://www.omdbapi.com/" target="_blank" class="link">OMDb API</a>
                  to fetch IMDB community ratings for each recommendation candidate, letting you reject content
                  that falls below your IMDB threshold.
                </p>
                <div class="omdb-pros-cons">
                  <div class="pros-block">
                    <div class="pros-cons-title pros"><i class="fas fa-check-circle"></i> Pros</div>
                    <ul>
                      <li>Widely trusted ratings from a large, diverse voter base</li>
                      <li>Cross-validates quality when used alongside TMDB ("Both" mode)</li>
                      <li>IMDB IDs are already stored by Jellyfin, Emby, and Plex</li>
                    </ul>
                  </div>
                  <div class="cons-block">
                    <div class="pros-cons-title cons"><i class="fas fa-exclamation-circle"></i> Cons</div>
                    <ul>
                      <li>Adds 1–2 extra API calls per recommendation (slight slowdown)</li>
                      <li>Free tier limited to 1,000 requests/day</li>
                      <li>Items missing an IMDB ID are skipped or passed through</li>
                    </ul>
                  </div>
                </div>
                <p class="omdb-info-footer">
                  <i class="fas fa-cog"></i>
                  Configure the rating source and thresholds in
                  <strong>Content Filters → Rating & Popularity</strong>.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Media Server -->
      <div v-if="showSection('media-server')" :class="wizardMode ? '' : 'service-card'">
        <div v-if="!wizardMode" class="service-header">
          <h3><i class="fas fa-server"></i> Media Server</h3>
          <span class="status-badge" :class="getMediaServerStatus">
            <span class="status-dot"></span>
            {{ getMediaServerStatusText }}
          </span>
        </div>

        <BaseDropdown
          v-if="!wizardMode"
          v-model="localConfig.SELECTED_SERVICE"
          :options="serviceOptions"
          label="Service"
          placeholder="Select a service"
          :disabled="isLoading"
          id="selectedService"
        />

        <!-- Plex: OAuth flow (both wizard and dashboard) -->
        <template v-if="localConfig.SELECTED_SERVICE === 'plex'">
          <!-- Step 1: not yet logged in → show Sign in button -->
          <div v-if="!plexOAuthLoggedIn" class="form-group">
            <button
              @click="loginWithPlexOAuth"
              class="btn btn-plex btn-block"
              :disabled="plexOAuthLoading"
            >
              <i v-if="plexOAuthLoading" class="fas fa-spinner fa-spin"></i>
              <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" style="width:18px;height:18px;fill:currentColor;flex-shrink:0">
                <path d="M18 18h12v12H18z"/><path d="M6 6h12v12H6zM30 6h12v12H30zM6 30h12v12H6zM30 30h12v12H30z"/>
              </svg>
              {{ plexOAuthLoading ? 'Waiting for Plex authorisation…' : 'Sign in with Plex' }}
            </button>
            <small class="form-help" style="text-align:center;display:block">
              <i class="fas fa-lock"></i> Opens Plex.tv in a new window for secure authentication.
            </small>
            <!-- Manual token fallback toggle -->
            <button
              @click="plexOAuthManualMode = !plexOAuthManualMode"
              class="text-btn"
              style="margin-top:0.5rem"
            >
              <i class="fas fa-keyboard"></i>
              {{ plexOAuthManualMode ? 'Use Plex login instead' : 'Enter token manually' }}
            </button>
          </div>

          <!-- Manual token fallback (also shown when user toggles it) -->
          <template v-if="plexOAuthManualMode">
            <div class="form-group">
              <label for="plexTokenWizard">Plex Token</label>
              <div class="input-group">
                <input
                  id="plexTokenManual"
                  v-model="localConfig.PLEX_TOKEN"
                  :type="showPlexToken ? 'text' : 'password'"
                  placeholder="Enter your Plex token"
                  class="form-control"
                  :disabled="isLoading"
                />
                <button @click="showPlexToken = !showPlexToken" type="button" class="btn btn-outline btn-sm" :disabled="isLoading">
                  <i :class="showPlexToken ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
                </button>
              </div>
            </div>
            <div class="form-group">
              <label for="plexApiUrlManual">API URL</label>
              <input id="plexApiUrlManual" v-model="localConfig.PLEX_API_URL" type="url" placeholder="http://localhost:32400" class="form-control" :disabled="isLoading" />
            </div>
            <button
              @click="testAndFetchPlex"
              class="btn btn-outline btn-block"
              :disabled="!localConfig.PLEX_TOKEN || !localConfig.PLEX_API_URL || plexFetching"
            >
              <i v-if="plexFetching" class="fas fa-spinner fa-spin"></i>
              <i v-else-if="plexConnected" class="fas fa-check"></i>
              <i v-else class="fas fa-plug"></i>
              {{ plexFetching ? 'Connecting...' : (plexConnected ? 'Connected' : 'Test & Load') }}
            </button>
          </template>

          <!-- Step 2: logged in via OAuth → server selection -->
          <template v-if="plexOAuthLoggedIn && !plexOAuthManualMode">
            <div class="form-group">
              <div class="oauth-success">
                <i class="fas fa-check-circle"></i> Authenticated with Plex
              </div>
            </div>
            <!-- Multiple servers: dropdown -->
            <div v-if="plexOAuthConnectionOptions.length > 1" class="form-group">
              <label>Select Server Connection</label>
              <BaseDropdown
                v-model="plexOAuthSelectedConnIdx"
                :options="plexOAuthConnectionOptions"
                placeholder="Choose a server connection…"
                @update:modelValue="onPlexOAuthServerSelect"
              />
            </div>
            <div class="form-group">
              <label>Or enter URL manually</label>
              <div class="input-group">
                <input v-model="localConfig.PLEX_API_URL" type="url" placeholder="http://localhost:32400" class="form-control" />
                <button
                  @click="testAndFetchPlex"
                  class="btn btn-outline btn-sm"
                  :disabled="!localConfig.PLEX_API_URL || plexFetching"
                >
                  <i v-if="plexFetching" class="fas fa-spinner fa-spin"></i>
                  <i v-else class="fas fa-plug"></i>
                </button>
              </div>
            </div>
          </template>
        </template>


        <!-- Jellyfin / Emby fields -->
        <template v-if="localConfig.SELECTED_SERVICE === 'jellyfin' || localConfig.SELECTED_SERVICE === 'emby'">
          <div class="form-group">
            <label for="jellyfinApiUrl">{{ localConfig.SELECTED_SERVICE === 'emby' ? 'Emby' : 'Jellyfin' }} URL</label>
            <input id="jellyfinApiUrl" v-model="localConfig.JELLYFIN_API_URL" type="url" placeholder="http://localhost:8096" class="form-control" :disabled="isLoading" />
          </div>
          <div class="form-group">
            <label for="jellyfinToken">API Token</label>
            <div class="input-group">
              <input
                id="jellyfinToken"
                v-model="localConfig.JELLYFIN_TOKEN"
                :type="showJellyfinToken ? 'text' : 'password'"
                placeholder="Enter your API token"
                class="form-control"
                :disabled="isLoading"
              />
              <button @click="showJellyfinToken = !showJellyfinToken" type="button" class="btn btn-outline btn-sm" :disabled="isLoading">
                <i :class="showJellyfinToken ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
              </button>
            </div>
          </div>
          <button
            @click="testAndFetchJellyfin"
            class="btn btn-outline btn-block"
            :disabled="isLoading || !localConfig.JELLYFIN_API_URL || !localConfig.JELLYFIN_TOKEN || jellyfinFetching"
          >
            <i v-if="jellyfinFetching" class="fas fa-spinner fa-spin"></i>
            <i v-else-if="jellyfinConnected" class="fas fa-check"></i>
            <i v-else class="fas fa-plug"></i>
            {{ jellyfinFetching ? 'Connecting...' : (jellyfinConnected ? 'Connected' : 'Test & Load') }}
          </button>
        </template>

        <!-- Libraries & Users (collapsible advanced section) -->
        <div v-if="mediaServerConnected" class="collapsible-section">
          <button class="collapsible-toggle" @click="mediaServerAdvancedExpanded = !mediaServerAdvancedExpanded">
            <i class="fas fa-chevron-right toggle-arrow" :class="{ expanded: mediaServerAdvancedExpanded }"></i>
            <span>Advanced Options</span>
            <span class="toggle-summary" v-if="!mediaServerAdvancedExpanded">
              {{ currentSelectedLibraries.length }} libraries, {{ currentSelectedUsers.length }} users
            </span>
          </button>
          <div class="collapsible-content" v-show="mediaServerAdvancedExpanded">
            <!-- Libraries -->
            <div class="advanced-block">
              <div class="advanced-block-header">
                <span class="advanced-block-title"><i class="fas fa-photo-video"></i> Libraries</span>
                <button v-if="currentSelectedLibraries.length > 0" @click="clearCurrentLibraries" class="text-btn">Clear all</button>
              </div>
              <p class="advanced-block-desc">Select libraries to monitor. Click <span class="inline-badge">A</span> to mark as anime.</p>
              <div v-if="currentLibraries.length > 0" class="chip-list">
                <div
                  v-for="lib in currentLibraries"
                  :key="lib._id"
                  class="chip"
                  :class="{ active: isLibSelected(lib._id) }"
                  @click="toggleLibrary(lib)"
                >
                  <i :class="getLibraryIcon(lib._type)"></i>
                  <span>{{ lib._name }}</span>
                  <button
                    v-if="isLibSelected(lib._id)"
                    class="chip-badge"
                    :class="{ 'badge-active': isAnimeLibrary(localConfig.SELECTED_SERVICE, lib._id) }"
                    @click.stop="toggleAnimeFlag(localConfig.SELECTED_SERVICE, lib._id)"
                    title="Toggle anime"
                  >A</button>
                </div>
              </div>
              <p v-else class="no-items">No libraries found</p>
            </div>

            <!-- Users -->
            <div class="advanced-block">
              <div class="advanced-block-header">
                <span class="advanced-block-title"><i class="fas fa-users"></i> Users</span>
                <button v-if="currentSelectedUsers.length > 0" @click="clearCurrentUsers" class="text-btn">Clear all</button>
              </div>
              <p class="advanced-block-desc">Select users whose watch history will drive recommendations.</p>
              <div v-if="currentUsers.length > 0" class="chip-list">
                <div
                  v-for="user in currentUsers"
                  :key="user.id"
                  class="chip"
                  :class="{ active: isUserSelected(user.id) }"
                  @click="toggleUser(user)"
                >
                  <span class="chip-avatar">{{ (user.name || 'U').charAt(0).toUpperCase() }}</span>
                  <span>{{ user.name }}</span>
                </div>
              </div>
              <p v-else class="no-items">No users found</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Overseerr -->
      <div v-if="showSection('seer')" :class="wizardMode ? '' : 'service-card'">
        <div v-if="!wizardMode" class="service-header">
          <h3><i class="fas fa-list-alt"></i> Overseerr</h3>
          <span class="status-badge" :class="getSeerStatus">
            <span class="status-dot"></span>
            {{ getSeerStatusText }}
          </span>
        </div>

        <div class="form-group">
          <label for="seerApiUrl">API URL</label>
          <input id="seerApiUrl" v-model="localConfig.SEER_API_URL" type="url" placeholder="http://localhost:5055" class="form-control" :disabled="isLoading" @input="onSeerConfigChange" />
        </div>

        <div class="form-group">
          <label for="seerToken">API Token</label>
          <div class="input-group">
            <input
              id="seerToken"
              v-model="localConfig.SEER_TOKEN"
              :type="showSeerToken ? 'text' : 'password'"
              placeholder="Enter your API token"
              class="form-control"
              :disabled="isLoading"
              @input="onSeerConfigChange"
            />
            <button @click="showSeerToken = !showSeerToken" type="button" class="btn btn-outline btn-sm" :disabled="isLoading">
              <i :class="showSeerToken ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
        </div>

        <button
          @click="testSeerAndFetchUsers"
          class="btn btn-outline btn-block"
          :disabled="isLoading || !localConfig.SEER_API_URL || !localConfig.SEER_TOKEN || seerTesting"
        >
          <i v-if="seerTesting" class="fas fa-spinner fa-spin"></i>
          <i v-else-if="seerConnected" class="fas fa-check"></i>
          <i v-else class="fas fa-plug"></i>
          {{ seerTesting ? 'Testing...' : (seerConnected ? 'Connected' : 'Test Connection') }}
        </button>

        <!-- User Auth & Download Profiles (collapsible advanced section) -->
        <div v-if="seerConnected" class="collapsible-section">
          <button class="collapsible-toggle" @click="seerAdvancedExpanded = !seerAdvancedExpanded">
            <i class="fas fa-chevron-right toggle-arrow" :class="{ expanded: seerAdvancedExpanded }"></i>
            <span>Advanced Options</span>
            <span class="toggle-summary" v-if="!seerAdvancedExpanded">
              {{ seerAuthenticated ? 'User authenticated' : 'Using admin account' }}
            </span>
          </button>
          <div class="collapsible-content" v-show="seerAdvancedExpanded">
            <!-- Request delay -->
            <div class="advanced-block">
              <div class="advanced-block-header">
                <span class="advanced-block-title"><i class="fas fa-user-shield"></i> Request Delay</span>
              </div>
              <p class="advanced-block-desc">Wait time between consecutive Overseerr/Jellyseerr requests. Increase if you receive notification rate-limit errors (0 = send all requests simultaneously)</p>
              <div class="form-group" style="margin-top: 1.25rem;">
                <input
                  id="seerRequestDelay"
                  v-model.number="localConfig.SEER_REQUEST_DELAY"
                  type="number"
                  min="0"
                  max="60"
                  class="form-control"
                  :disabled="isLoading"
                />
              </div>
            </div>
            <!-- User Authentication -->
            <div class="advanced-block">
              <div class="advanced-block-header">
                <span class="advanced-block-title"><i class="fas fa-user-shield"></i> User Authentication</span>
              </div>
              <p class="advanced-block-desc">Authenticate as a local user to make requests on their behalf.</p>

              <template v-if="seerUsers.length > 0">
                <div class="inline-form">
                  <BaseDropdown
                    v-model="selectedSeerUser"
                    :options="seerUserOptions"
                    placeholder="Select user..."
                    id="seerLocalUser"
                    :disabled="isLoading"
                    @change="onSeerUserChange"
                    class="flex-1"
                  />
                  <input
                    v-model="seerUserPassword"
                    type="password"
                    placeholder="Password"
                    class="form-control flex-1"
                    :disabled="isLoading"
                    autocomplete="new-password"
                  />
                  <button
                    @click="authenticateSeerUser"
                    :class="['btn', seerAuthenticated ? 'btn-success' : 'btn-primary']"
                    :disabled="isLoading || seerAuthenticating || !selectedSeerUser || !seerUserPassword"
                  >
                    <i v-if="seerAuthenticating" class="fas fa-spinner fa-spin"></i>
                    <i v-else-if="seerAuthenticated" class="fas fa-check"></i>
                    <i v-else class="fas fa-sign-in-alt"></i>
                  </button>
                </div>
              </template>
              <p v-else class="no-items"><i class="fas fa-info-circle"></i> No local users found. Admin account will be used.</p>
            </div>

            <!-- Download Profiles -->
            <div class="advanced-block">
              <div class="advanced-block-header">
                <span class="advanced-block-title"><i class="fas fa-download"></i> Download Profiles</span>
                <button @click="fetchArrServers" class="text-btn" :disabled="loadingServers">
                  <i :class="loadingServers ? 'fas fa-spinner fa-spin' : 'fas fa-sync-alt'"></i>
                  {{ loadingServers ? 'Loading...' : 'Load Servers' }}
                </button>
              </div>
              <p class="advanced-block-desc">Configure Radarr/Sonarr servers, quality profiles, and root folders.</p>

              <div v-if="radarrServers.length > 0 || sonarrServers.length > 0" class="profiles-grid">
                <!-- Movie (Radarr) -->
                <div v-if="radarrServers.length > 0" class="profile-card">
                  <div class="profile-card-header"><i class="fas fa-film"></i> Movies</div>
                  <BaseDropdown v-model="defaultMovieServerId" :options="radarrServerOptions" placeholder="Server" :disabled="isLoading" @change="onDefaultMovieServerChange" />
                  <BaseDropdown v-if="defaultMovieProfiles.length > 0" v-model="defaultMovieProfileId" :options="defaultMovieProfiles" placeholder="Quality" :disabled="isLoading" @change="updateProfileConfig" />
                  <BaseDropdown v-if="defaultMovieRootFolders.length > 0" v-model="defaultMovieRootFolder" :options="defaultMovieRootFolders" placeholder="Root folder" :disabled="isLoading" @change="updateProfileConfig" />
                </div>

                <!-- TV (Sonarr) -->
                <div v-if="sonarrServers.length > 0" class="profile-card">
                  <div class="profile-card-header"><i class="fas fa-tv"></i> TV Shows</div>
                  <BaseDropdown v-model="defaultTvServerId" :options="sonarrServerOptions" placeholder="Server" :disabled="isLoading" @change="onDefaultTvServerChange" />
                  <BaseDropdown v-if="defaultTvProfiles.length > 0" v-model="defaultTvProfileId" :options="defaultTvProfiles" placeholder="Quality" :disabled="isLoading" @change="updateProfileConfig" />
                  <BaseDropdown v-if="defaultTvRootFolders.length > 0" v-model="defaultTvRootFolder" :options="defaultTvRootFolders" placeholder="Root folder" :disabled="isLoading" @change="updateProfileConfig" />
                </div>

                <!-- Anime Movie (Radarr) -->
                <div v-if="radarrServers.length > 0 && hasAnimeLibraries" class="profile-card anime">
                  <div class="profile-card-header"><i class="fas fa-torii-gate"></i> Anime Movies</div>
                  <BaseDropdown v-model="animeMovieServerId" :options="radarrServerOptions" placeholder="Server" :disabled="isLoading" @change="onAnimeMovieServerChange" />
                  <BaseDropdown v-if="animeMovieProfiles.length > 0" v-model="animeMovieProfileId" :options="animeMovieProfiles" placeholder="Quality" :disabled="isLoading" @change="updateProfileConfig" />
                  <BaseDropdown v-if="animeMovieRootFolders.length > 0" v-model="animeMovieRootFolder" :options="animeMovieRootFolders" placeholder="Root folder" :disabled="isLoading" @change="updateProfileConfig" />
                </div>

                <!-- Anime TV (Sonarr) -->
                <div v-if="sonarrServers.length > 0 && hasAnimeLibraries" class="profile-card anime">
                  <div class="profile-card-header"><i class="fas fa-torii-gate"></i> Anime TV</div>
                  <BaseDropdown v-model="animeTvServerId" :options="sonarrServerOptions" placeholder="Server" :disabled="isLoading" @change="onAnimeTvServerChange" />
                  <BaseDropdown v-if="animeTvProfiles.length > 0" v-model="animeTvProfileId" :options="animeTvProfiles" placeholder="Quality" :disabled="isLoading" @change="updateProfileConfig" />
                  <BaseDropdown v-if="animeTvRootFolders.length > 0" v-model="animeTvRootFolder" :options="animeTvRootFolders" placeholder="Root folder" :disabled="isLoading" @change="updateProfileConfig" />
                </div>
              </div>

              <p v-else-if="serversLoaded" class="no-items"><i class="fas fa-exclamation-triangle"></i> No Radarr/Sonarr servers found in Overseerr.</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Save Button (hidden in wizard mode — wizard shell handles saving) -->
    <div v-if="!wizardMode" class="settings-actions">
      <button
        @click="saveSettings"
        class="btn btn-primary"
        :disabled="isLoading || !hasChanges"
      >
        <i class="fas fa-save"></i>
        {{ isLoading ? 'Saving...' : 'Save Changes' }}
      </button>

      <button
        @click="resetToDefaults"
        class="btn btn-outline"
        :disabled="isLoading"
      >
        <i class="fas fa-undo"></i>
        Reset
      </button>
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import BaseDropdown from '@/components/common/BaseDropdown.vue';
import {
  testJellyseerApi, authenticateUser, fetchRadarrServers, fetchSonarrServers,
  fetchJellyfinLibraries, fetchJellyfinUsers, fetchPlexLibraries, fetchPlexUsers,
  testOmdbApi, testTmdbApi
} from '@/api/api';

export default {
  name: 'SettingsServices',
  components: {
    BaseDropdown
  },
  props: {
    config: {
      type: Object,
      required: true,
    },
    isLoading: {
      type: Boolean,
      default: false,
    },
    testingConnections: {
      type: Object,
      default: () => ({}),
    },
    // Wizard mode: hides save button and enables config-changed / validation-changed emits
    wizardMode: {
      type: Boolean,
      default: false,
    },
    // When set, only the matching section is rendered (used by the wizard)
    // Values: 'tmdb' | 'omdb' | 'media-server' | 'seer' | null (show all)
    wizardSection: {
      type: String,
      default: null,
    },
  },
  emits: ['save-section', 'test-connection', 'validation-changed', 'config-changed'],
  data() {
    return {
      localConfig: {},
      originalConfig: {},
      showTmdbKey: false,
      showOmdbKey: false,
      showPlexToken: false,
      showJellyfinToken: false,
      showSeerToken: false,
      // Wizard-mode self-contained TMDB test state
      wizardTmdbTesting: false,
      wizardTmdbConnected: false,
      // OMDb connection test
      omdbTesting: false,
      omdbConnected: false,
      omdbInfoExpanded: false,
      // Collapsible sections
      mediaServerAdvancedExpanded: false,
      seerAdvancedExpanded: false,
      serviceOptions: [
        { value: 'plex', label: 'Plex' },
        { value: 'jellyfin', label: 'Jellyfin' },
        { value: 'emby', label: 'Emby' }
      ],
      // Seer user authentication
      seerTesting: false,
      seerConnected: false,
      seerUsers: [],
      selectedSeerUser: null,
      seerUserPassword: '',
      seerAuthenticated: false,
      seerAuthenticating: false,
      // Download profiles
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
      animeTvRootFolder: null,
      // Media server libraries & users
      jellyfinFetching: false,
      jellyfinConnected: false,
      jellyfinLibraries: [],
      jellyfinUsers: [],
      selectedJellyfinLibraries: [],
      selectedJellyfinUsers: [],
      plexFetching: false,
      plexConnected: false,
      plexLibraries: [],
      plexUsers: [],
      selectedPlexLibraries: [],
      selectedPlexUsers: [],
      // Plex OAuth (wizard mode)
      plexOAuthLoading: false,
      plexOAuthLoggedIn: false,
      plexOAuthServers: [],
      plexOAuthSelectedConnIdx: null,
      plexOAuthManualMode: false,
      plexOAuthPollTimer: null,
    };
  },
  computed: {
    hasChanges() {
      return JSON.stringify(this.localConfig) !== JSON.stringify(this.originalConfig);
    },
    mediaServerConnected() {
      return this.plexConnected || this.jellyfinConnected;
    },
    // Unified accessors for current service's libraries/users
    currentLibraries() {
      if (this.localConfig.SELECTED_SERVICE === 'plex') {
        return this.plexLibraries.map(lib => ({ _id: lib.key, _name: lib.title, _type: lib.type, _raw: lib }));
      }
      return this.jellyfinLibraries.map(lib => ({ _id: lib.ItemId, _name: lib.Name, _type: lib.CollectionType, _raw: lib }));
    },
    currentUsers() {
      if (this.localConfig.SELECTED_SERVICE === 'plex') return this.plexUsers;
      return this.jellyfinUsers;
    },
    currentSelectedLibraries() {
      if (this.localConfig.SELECTED_SERVICE === 'plex') return this.selectedPlexLibraries;
      return this.selectedJellyfinLibraries;
    },
    currentSelectedUsers() {
      if (this.localConfig.SELECTED_SERVICE === 'plex') return this.selectedPlexUsers;
      return this.selectedJellyfinUsers;
    },
    // Plex OAuth: flattened list of server connections for the dropdown
    plexOAuthConnectionOptions() {
      const opts = [];
      this.plexOAuthServers.forEach(server => {
        (server.connections || [])
          .filter(c => !c.relay)
          .sort((a, b) => {
            const aL = a.local === true || a.local === 1;
            const bL = b.local === true || b.local === 1;
            if (aL !== bL) return bL - aL;
            return (b.protocol === 'https' ? 1 : 0) - (a.protocol === 'https' ? 1 : 0);
          })
          .slice(0, 3)
          .forEach(c => {
            opts.push({
              label: `${server.name}${(c.local === true || c.local === 1) ? ' [Local]' : ' [Remote]'} — ${c.protocol}://${c.address}:${c.port}`,
              value: `${c.protocol}://${c.address}:${c.port}`,
            });
          });
      });
      return opts;
    },
    // Wizard-mode TMDB test state
    isTmdbTesting() {
      return this.wizardMode ? this.wizardTmdbTesting : (this.testingConnections?.tmdb || false);
    },
    isTmdbConnected() {
      return this.wizardMode ? this.wizardTmdbConnected : !!this.localConfig.TMDB_API_KEY;
    },
    getTmdbStatus() {
      if (this.wizardMode) {
        if (this.wizardTmdbConnected) return 'status-connected';
        return this.localConfig.TMDB_API_KEY ? 'status-warning' : 'status-disconnected';
      }
      return this.localConfig.TMDB_API_KEY ? 'status-connected' : 'status-disconnected';
    },
    getTmdbStatusText() {
      if (this.wizardMode) {
        if (this.wizardTmdbConnected) return 'Connected';
        return this.localConfig.TMDB_API_KEY ? 'Not Tested' : 'Not Set';
      }
      return this.localConfig.TMDB_API_KEY ? 'Connected' : 'Not Set';
    },
    getOmdbStatus() {
      if (this.omdbConnected) return 'status-connected';
      if (this.localConfig.OMDB_API_KEY) return 'status-warning';
      return 'status-disconnected';
    },
    getOmdbStatusText() {
      if (this.omdbConnected) return 'Connected';
      if (this.localConfig.OMDB_API_KEY) return 'Not Tested';
      return 'Not Set';
    },
    getMediaServerStatus() {
      const service = this.localConfig.SELECTED_SERVICE;
      if (!service) return 'status-disconnected';
      if (this.mediaServerConnected) return 'status-connected';
      if (service === 'plex' && this.localConfig.PLEX_TOKEN && this.localConfig.PLEX_API_URL) return 'status-warning';
      if ((service === 'jellyfin' || service === 'emby') && this.localConfig.JELLYFIN_TOKEN && this.localConfig.JELLYFIN_API_URL) return 'status-warning';
      return 'status-warning';
    },
    getMediaServerStatusText() {
      const service = this.localConfig.SELECTED_SERVICE;
      if (!service) return 'No Service';
      if (this.mediaServerConnected) return 'Connected';
      return 'Not Tested';
    },
    getSeerStatus() {
      if (this.seerConnected) return 'status-connected';
      return (this.localConfig.SEER_API_URL && this.localConfig.SEER_TOKEN)
        ? 'status-warning'
        : 'status-disconnected';
    },
    getSeerStatusText() {
      if (this.seerConnected) return 'Connected';
      return (this.localConfig.SEER_API_URL && this.localConfig.SEER_TOKEN)
        ? 'Not Tested'
        : 'Not Set';
    },
    seerUserOptions() {
      return this.seerUsers.map(user => ({
        label: `${user.name}${user.email ? ` (${user.email})` : ''}`,
        value: user.email || user.name
      }));
    },
    hasAnimeLibraries() {
      const jellyfinLibs = this.localConfig.JELLYFIN_LIBRARIES || [];
      const plexLibs = this.localConfig.PLEX_LIBRARIES || [];
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
      return server.profiles.map(p => ({ label: p.name, value: String(p.id) }));
    },
    defaultMovieRootFolders() {
      const server = this.radarrServers.find(s => String(s.id) === String(this.defaultMovieServerId));
      if (!server || !server.rootFolders) return [];
      return server.rootFolders.map(rf => ({ label: rf.path, value: rf.path }));
    },
    defaultTvProfiles() {
      const server = this.sonarrServers.find(s => String(s.id) === String(this.defaultTvServerId));
      if (!server || !server.profiles) return [];
      return server.profiles.map(p => ({ label: p.name, value: String(p.id) }));
    },
    defaultTvRootFolders() {
      const server = this.sonarrServers.find(s => String(s.id) === String(this.defaultTvServerId));
      if (!server || !server.rootFolders) return [];
      return server.rootFolders.map(rf => ({ label: rf.path, value: rf.path }));
    },
    animeMovieProfiles() {
      const server = this.radarrServers.find(s => String(s.id) === String(this.animeMovieServerId));
      if (!server || !server.profiles) return [];
      return server.profiles.map(p => ({ label: p.name, value: String(p.id) }));
    },
    animeMovieRootFolders() {
      const server = this.radarrServers.find(s => String(s.id) === String(this.animeMovieServerId));
      if (!server || !server.rootFolders) return [];
      return server.rootFolders.map(rf => ({ label: rf.path, value: rf.path }));
    },
    animeTvProfiles() {
      const server = this.sonarrServers.find(s => String(s.id) === String(this.animeTvServerId));
      if (!server || !server.profiles) return [];
      return server.profiles.map(p => ({ label: p.name, value: String(p.id) }));
    },
    animeTvRootFolders() {
      const server = this.sonarrServers.find(s => String(s.id) === String(this.animeTvServerId));
      if (!server || !server.rootFolders) return [];
      return server.rootFolders.map(rf => ({ label: rf.path, value: rf.path }));
    },
  },
  watch: {
    config: {
      immediate: true,
      handler(newConfig) {
        this.localConfig = { ...newConfig };
        this.originalConfig = { ...newConfig };
        this.loadSavedSeerState();
      },
    },
    // Wizard-mode validation signals
    jellyfinConnected(val) {
      if (this.wizardMode && this.wizardSection === 'media-server') {
        this.$emit('validation-changed', val);
      }
    },
    plexConnected(val) {
      if (this.wizardMode && this.wizardSection === 'media-server') {
        this.$emit('validation-changed', val);
      }
    },
    seerConnected(val) {
      if (this.wizardMode && this.wizardSection === 'seer') {
        this.$emit('validation-changed', val);
      }
    },
  },
  beforeUnmount() {
    // Clean up Plex OAuth poll timer if active
    if (this.plexOAuthPollTimer) {
      clearInterval(this.plexOAuthPollTimer);
    }
    // Snapshot local config back to the wizard when unmounting a wizard step
    if (this.wizardMode) {
      this.$emit('config-changed', { ...this.localConfig });
    }
  },
  async mounted() {
    const service = this.localConfig.SELECTED_SERVICE;
    if (service === 'plex' && this.localConfig.PLEX_TOKEN && this.localConfig.PLEX_API_URL) {
      await this.testAndFetchPlex(true);
      if (this.plexConnected) {
        this.plexOAuthLoggedIn = true;
      }
    } else if ((service === 'jellyfin' || service === 'emby') &&
               this.localConfig.JELLYFIN_TOKEN && this.localConfig.JELLYFIN_API_URL) {
      await this.testAndFetchJellyfin(true);
    }

    if (this.localConfig.SEER_API_URL && this.localConfig.SEER_TOKEN) {
      await this.testSeerAndFetchUsers(true);
      if (this.seerConnected && this.localConfig.SEER_SESSION_TOKEN) {
        await this.fetchArrServers();
      }
    }

    if (this.localConfig.OMDB_API_KEY) {
      await this.testOmdbConnection(true);
    }
  },
  methods: {
    // Returns true when this section should be visible.
    // In dashboard mode (wizardSection null): always true.
    // In wizard mode: only the matching section is visible.
    showSection(section) {
      return !this.wizardSection || this.wizardSection === section;
    },

    // ── Plex OAuth ────────────────────────────────────────────────────────
    async loginWithPlexOAuth() {
      this.plexOAuthLoading = true;
      try {
        const res = await axios.post('/api/plex/auth');
        const { pin_id, auth_url } = res.data;
        window.open(auth_url, '_blank', 'width=800,height=600');
        this.plexOAuthPollTimer = setInterval(() => this.pollPlexOAuth(pin_id), 3000);
      } catch {
        this.$toast.error('Error starting Plex login.');
        this.plexOAuthLoading = false;
      }
    },
    async pollPlexOAuth(pinId) {
      try {
        const res = await axios.get(`/api/plex/check-auth/${pinId}`);
        if (res.data.auth_token) {
          clearInterval(this.plexOAuthPollTimer);
          this.plexOAuthPollTimer = null;
          this.localConfig.PLEX_TOKEN = res.data.auth_token;
          this.plexOAuthLoggedIn = true;
          await this.fetchPlexOAuthServers(res.data.auth_token);
        }
      } catch (e) {
        console.error('Plex auth poll error:', e);
      } finally {
        this.plexOAuthLoading = false;
      }
    },
    async fetchPlexOAuthServers(authToken) {
      try {
        const res = await axios.post('/api/plex/servers', { auth_token: authToken });
        this.plexOAuthServers = res.data.servers || [];
        // Auto-connect if only one connection option
        if (this.plexOAuthConnectionOptions.length === 1) {
          const url = this.plexOAuthConnectionOptions[0].value;
          this.plexOAuthSelectedConnIdx = url;
          await this.onPlexOAuthServerSelect(url);
        }
      } catch {
        this.$toast.error('Error fetching Plex servers.');
      }
    },
    async onPlexOAuthServerSelect(url) {
      this.localConfig.PLEX_API_URL = url;
      await this.testAndFetchPlex();
    },

    // Unified library/user helpers for the template
    isLibSelected(id) {
      return this.currentSelectedLibraries.some(l => l.id === id);
    },
    isUserSelected(id) {
      return this.currentSelectedUsers.some(u => u.id === id);
    },
    toggleLibrary(lib) {
      if (this.localConfig.SELECTED_SERVICE === 'plex') {
        this.togglePlexLibrary(lib._raw);
      } else {
        this.toggleJellyfinLibrary(lib._raw);
      }
    },
    toggleUser(user) {
      if (this.localConfig.SELECTED_SERVICE === 'plex') {
        this.togglePlexUser(user);
      } else {
        this.toggleJellyfinUser(user);
      }
    },
    clearCurrentLibraries() {
      if (this.localConfig.SELECTED_SERVICE === 'plex') {
        this.clearPlexLibraries();
      } else {
        this.clearJellyfinLibraries();
      }
    },
    clearCurrentUsers() {
      if (this.localConfig.SELECTED_SERVICE === 'plex') {
        this.clearPlexUsers();
      } else {
        this.clearJellyfinUsers();
      }
    },

    async testTmdbConnection() {
      if (!this.localConfig.TMDB_API_KEY) return;

      if (this.wizardMode) {
        // Self-contained test in wizard mode (no parent delegation needed)
        this.wizardTmdbTesting = true;
        this.wizardTmdbConnected = false;
        try {
          await testTmdbApi(this.localConfig.TMDB_API_KEY.trim());
          this.wizardTmdbConnected = true;
          if (this.$toast) this.$toast.success('TMDB API key validated!', { position: 'top-right', duration: 3000 });
          this.$emit('validation-changed', true);
        } catch (error) {
          this.wizardTmdbConnected = false;
          if (this.$toast) this.$toast.error('Invalid TMDB API key. Please check and try again.', { position: 'top-right', duration: 5000 });
          this.$emit('validation-changed', false);
        } finally {
          this.wizardTmdbTesting = false;
        }
      } else {
        await this.$emit('test-connection', 'tmdb', {
          api_key: this.localConfig.TMDB_API_KEY.trim(),
        });
      }
    },

    async testOmdbConnection(silent = false) {
      if (!this.localConfig.OMDB_API_KEY) return;
      this.omdbTesting = true;
      this.omdbConnected = false;
      try {
        await testOmdbApi(this.localConfig.OMDB_API_KEY.trim());
        this.omdbConnected = true;
        if (!silent && this.$toast) this.$toast.success('OMDb API key validated!', { position: 'top-right', duration: 3000 });
      } catch (error) {
        this.omdbConnected = false;
        if (!silent && this.$toast) this.$toast.error('Invalid OMDb API key. Please check and try again.', { position: 'top-right', duration: 5000 });
      } finally {
        this.omdbTesting = false;
      }
    },

    async testJellyfinConnection() {
      if (!this.localConfig.JELLYFIN_API_URL || !this.localConfig.JELLYFIN_TOKEN) return;
      try {
        const url = this.localConfig.JELLYFIN_API_URL.trim();
        const testUrl = url.startsWith('http') ? url : `http://${url}`;
        new URL(testUrl);
      } catch (e) {
        if (this.$toast) this.$toast.error('Invalid URL format.', { position: 'top-right', duration: 4000 });
        return;
      }
      await this.$emit('test-connection', 'jellyfin', {
        api_url: this.localConfig.JELLYFIN_API_URL.trim(),
        token: this.localConfig.JELLYFIN_TOKEN.trim(),
      });
    },

    async testPlexConnection() {
      if (!this.localConfig.PLEX_API_URL || !this.localConfig.PLEX_TOKEN) return;
      try {
        const url = this.localConfig.PLEX_API_URL.trim();
        const testUrl = url.startsWith('http') ? url : `http://${url}`;
        new URL(testUrl);
      } catch (e) {
        if (this.$toast) this.$toast.error('Invalid URL format.', { position: 'top-right', duration: 4000 });
        return;
      }
      await this.$emit('test-connection', 'plex', {
        token: this.localConfig.PLEX_TOKEN.trim(),
        api_url: this.localConfig.PLEX_API_URL.trim(),
      });
    },

    async testAndFetchJellyfin(silent = false) {
      if (!this.localConfig.JELLYFIN_API_URL || !this.localConfig.JELLYFIN_TOKEN) return;
      try {
        const url = this.localConfig.JELLYFIN_API_URL.trim();
        new URL(url.startsWith('http') ? url : `http://${url}`);
      } catch (e) {
        if (!silent && this.$toast) this.$toast.error('Invalid URL format.', { position: 'top-right', duration: 4000 });
        return;
      }
      this.jellyfinFetching = true;
      this.jellyfinConnected = false;
      try {
        const libRes = await fetchJellyfinLibraries(this.localConfig.JELLYFIN_API_URL.trim(), this.localConfig.JELLYFIN_TOKEN.trim());
        this.jellyfinLibraries = libRes.data.items || [];
        this.jellyfinConnected = true;
        this.loadSavedJellyfinLibraries();
        try {
          const userRes = await fetchJellyfinUsers(this.localConfig.JELLYFIN_API_URL.trim(), this.localConfig.JELLYFIN_TOKEN.trim());
          this.jellyfinUsers = userRes.data.users || [];
          this.loadSavedJellyfinUsers();
        } catch (e) { console.error('Error fetching Jellyfin users:', e); }
        if (!silent && this.$toast) this.$toast.success(`Connected! Found ${this.jellyfinLibraries.length} libraries.`, { position: 'top-right', duration: 3000 });
      } catch (error) {
        console.error('Jellyfin connection failed:', error);
        this.jellyfinConnected = false;
        this.jellyfinLibraries = [];
        this.jellyfinUsers = [];
        if (!silent && this.$toast) this.$toast.error('Failed to connect. Check your URL and token.', { position: 'top-right', duration: 5000 });
      } finally {
        this.jellyfinFetching = false;
      }
    },

    async testAndFetchPlex(silent = false) {
      if (!this.localConfig.PLEX_API_URL || !this.localConfig.PLEX_TOKEN) return;
      try {
        const url = this.localConfig.PLEX_API_URL.trim();
        new URL(url.startsWith('http') ? url : `http://${url}`);
      } catch (e) {
        if (!silent && this.$toast) this.$toast.error('Invalid URL format.', { position: 'top-right', duration: 4000 });
        return;
      }
      this.plexFetching = true;
      this.plexConnected = false;
      try {
        const libRes = await fetchPlexLibraries(this.localConfig.PLEX_API_URL.trim(), this.localConfig.PLEX_TOKEN.trim());
        this.plexLibraries = libRes.data.items || [];
        this.plexConnected = true;
        this.loadSavedPlexLibraries();
        try {
          const userRes = await fetchPlexUsers(this.localConfig.PLEX_API_URL.trim(), this.localConfig.PLEX_TOKEN.trim());
          this.plexUsers = userRes.data.users || [];
          this.loadSavedPlexUsers();
        } catch (e) { console.error('Error fetching Plex users:', e); }
        if (!silent && this.$toast) this.$toast.success(`Connected! Found ${this.plexLibraries.length} libraries.`, { position: 'top-right', duration: 3000 });
      } catch (error) {
        console.error('Plex connection failed:', error);
        this.plexConnected = false;
        this.plexLibraries = [];
        this.plexUsers = [];
        if (!silent && this.$toast) this.$toast.error('Failed to connect. Check your URL and token.', { position: 'top-right', duration: 5000 });
      } finally {
        this.plexFetching = false;
      }
    },

    // Jellyfin library/user selection
    toggleJellyfinLibrary(lib) {
      const idx = this.selectedJellyfinLibraries.findIndex(l => l.id === lib.ItemId);
      if (idx >= 0) {
        this.selectedJellyfinLibraries.splice(idx, 1);
      } else {
        const isAnime = lib.Name.toLowerCase().includes('anime');
        this.selectedJellyfinLibraries.push({ id: lib.ItemId, name: lib.Name, is_anime: isAnime });
      }
      this.localConfig.JELLYFIN_LIBRARIES = [...this.selectedJellyfinLibraries];
    },
    toggleJellyfinUser(user) {
      const idx = this.selectedJellyfinUsers.findIndex(u => u.id === user.id);
      if (idx >= 0) { this.selectedJellyfinUsers.splice(idx, 1); }
      else { this.selectedJellyfinUsers.push({ id: user.id, name: user.name }); }
      this.localConfig.SELECTED_USERS = [...this.selectedJellyfinUsers];
    },
    isJellyfinLibSelected(id) { return this.selectedJellyfinLibraries.some(l => l.id === id); },
    isJellyfinUserSelected(id) { return this.selectedJellyfinUsers.some(u => u.id === id); },
    clearJellyfinLibraries() { this.selectedJellyfinLibraries = []; this.localConfig.JELLYFIN_LIBRARIES = []; },
    clearJellyfinUsers() { this.selectedJellyfinUsers = []; this.localConfig.SELECTED_USERS = []; },
    loadSavedJellyfinLibraries() {
      const saved = this.localConfig.JELLYFIN_LIBRARIES || [];
      this.selectedJellyfinLibraries = saved.filter(lib => typeof lib === 'object' && lib.id).map(lib => ({ id: lib.id, name: lib.name, is_anime: lib.is_anime || false }));
    },
    loadSavedJellyfinUsers() {
      const saved = this.localConfig.SELECTED_USERS || [];
      this.selectedJellyfinUsers = saved.filter(u => typeof u === 'object' && u.id).map(u => ({ id: u.id, name: u.name }));
    },

    // Plex library/user selection
    togglePlexLibrary(lib) {
      const idx = this.selectedPlexLibraries.findIndex(l => l.id === lib.key);
      if (idx >= 0) {
        this.selectedPlexLibraries.splice(idx, 1);
      } else {
        const isAnime = lib.title.toLowerCase().includes('anime');
        this.selectedPlexLibraries.push({ id: lib.key, name: lib.title, is_anime: isAnime });
      }
      this.localConfig.PLEX_LIBRARIES = [...this.selectedPlexLibraries];
    },
    togglePlexUser(user) {
      const idx = this.selectedPlexUsers.findIndex(u => u.id === user.id);
      if (idx >= 0) { this.selectedPlexUsers.splice(idx, 1); }
      else { this.selectedPlexUsers.push({ id: user.id, name: user.name }); }
      this.localConfig.SELECTED_USERS = [...this.selectedPlexUsers];
    },
    isPlexLibSelected(key) { return this.selectedPlexLibraries.some(l => l.id === key); },
    isPlexUserSelected(id) { return this.selectedPlexUsers.some(u => u.id === id); },
    clearPlexLibraries() { this.selectedPlexLibraries = []; this.localConfig.PLEX_LIBRARIES = []; },
    clearPlexUsers() { this.selectedPlexUsers = []; this.localConfig.SELECTED_USERS = []; },
    loadSavedPlexLibraries() {
      const saved = this.localConfig.PLEX_LIBRARIES || [];
      this.selectedPlexLibraries = saved.filter(lib => typeof lib === 'object' && lib.id).map(lib => ({ id: lib.id, name: lib.name, is_anime: lib.is_anime || false }));
    },
    loadSavedPlexUsers() {
      const saved = this.localConfig.SELECTED_USERS || [];
      this.selectedPlexUsers = saved.filter(u => typeof u === 'object' && u.id).map(u => ({ id: u.id, name: u.name }));
    },

    // Shared helpers
    toggleAnimeFlag(service, libId) {
      const list = service === 'plex' ? this.selectedPlexLibraries : this.selectedJellyfinLibraries;
      const lib = list.find(l => l.id === libId);
      if (lib) {
        lib.is_anime = !lib.is_anime;
        const configKey = service === 'plex' ? 'PLEX_LIBRARIES' : 'JELLYFIN_LIBRARIES';
        this.localConfig[configKey] = [...list];
      }
    },
    isAnimeLibrary(service, libId) {
      const list = service === 'plex' ? this.selectedPlexLibraries : this.selectedJellyfinLibraries;
      const lib = list.find(l => l.id === libId);
      return lib ? lib.is_anime : false;
    },
    getLibraryIcon(type) {
      const icons = { movies: 'fas fa-film', movie: 'fas fa-film', tvshows: 'fas fa-tv', show: 'fas fa-tv', music: 'fas fa-music', artist: 'fas fa-music', books: 'fas fa-book', photo: 'fas fa-images', photos: 'fas fa-images' };
      return icons[type] || 'fas fa-folder';
    },

    // Seer connection test + user fetch
    async testSeerAndFetchUsers(silent = false) {
      if (!this.localConfig.SEER_API_URL || !this.localConfig.SEER_TOKEN) return;
      try {
        const url = this.localConfig.SEER_API_URL.trim();
        new URL(url.startsWith('http') ? url : `http://${url}`);
      } catch (e) {
        if (!silent && this.$toast) this.$toast.error('Invalid URL format.', { position: 'top-right', duration: 4000 });
        return;
      }
      this.seerTesting = true;
      this.seerConnected = false;
      this.seerUsers = [];
      try {
        const response = await testJellyseerApi(this.localConfig.SEER_API_URL.trim(), this.localConfig.SEER_TOKEN.trim());
        this.seerUsers = (response.data.users || []).filter(user => user.isLocal);
        this.seerConnected = true;
        this.loadSavedSeerUser();
        if (!silent && this.$toast) this.$toast.success(`Connected! Found ${this.seerUsers.length} local user(s).`, { position: 'top-right', duration: 3000 });
      } catch (error) {
        console.error('Seer connection test failed:', error);
        this.seerConnected = false;
        if (!silent && this.$toast) this.$toast.error('Failed to connect. Verify URL and API Key.', { position: 'top-right', duration: 5000 });
      } finally {
        this.seerTesting = false;
      }
    },
    onSeerConfigChange() { this.seerConnected = false; this.seerUsers = []; this.seerAuthenticated = false; },
    onSeerUserChange(value) { this.selectedSeerUser = value; this.localConfig.SEER_USER_NAME = value; this.seerAuthenticated = false; },
    async authenticateSeerUser() {
      if (!this.selectedSeerUser || !this.seerUserPassword) return;
      this.seerAuthenticating = true;
      try {
        const response = await authenticateUser(this.localConfig.SEER_API_URL, this.localConfig.SEER_TOKEN, this.selectedSeerUser, this.seerUserPassword);
        this.seerAuthenticated = true;
        this.localConfig.SEER_SESSION_TOKEN = response.data.session_token;
        this.localConfig.SEER_USER_NAME = this.selectedSeerUser;
        this.localConfig.SEER_USER_PSW = this.seerUserPassword;
        if (this.$toast) this.$toast.success('User authenticated!', { position: 'top-right', duration: 3000 });
      } catch (error) {
        console.error('Authentication error:', error);
        this.seerAuthenticated = false;
        if (this.$toast) this.$toast.error('Incorrect username or password', { position: 'top-right', duration: 5000 });
      } finally {
        this.seerAuthenticating = false;
      }
    },
    loadSavedSeerState() { if (this.localConfig.SEER_USER_NAME && this.localConfig.SEER_SESSION_TOKEN) this.seerAuthenticated = true; },
    loadSavedSeerUser() {
      if (this.localConfig.SEER_USER_NAME) this.selectedSeerUser = this.localConfig.SEER_USER_NAME;
      if (this.localConfig.SEER_USER_PSW) this.seerUserPassword = this.localConfig.SEER_USER_PSW;
    },

    // Download profile methods
    async fetchArrServers() {
      this.loadingServers = true;
      this.serversLoaded = false;
      try {
        const [radarrRes, sonarrRes] = await Promise.all([
          fetchRadarrServers(this.localConfig.SEER_API_URL, this.localConfig.SEER_TOKEN, this.localConfig.SEER_SESSION_TOKEN),
          fetchSonarrServers(this.localConfig.SEER_API_URL, this.localConfig.SEER_TOKEN, this.localConfig.SEER_SESSION_TOKEN)
        ]);
        this.radarrServers = radarrRes.data.servers || [];
        this.sonarrServers = sonarrRes.data.servers || [];
        this.loadSavedProfileConfig();
      } catch (error) {
        console.error('Error fetching Radarr/Sonarr servers:', error);
        this.radarrServers = [];
        this.sonarrServers = [];
        if (this.$toast) this.$toast.error('Failed to fetch servers.', { position: 'top-right', duration: 5000 });
      } finally {
        this.loadingServers = false;
        this.serversLoaded = true;
      }
    },
    onDefaultMovieServerChange(value) { this.defaultMovieServerId = value; this.defaultMovieProfileId = null; this.defaultMovieRootFolder = null; this.updateProfileConfig(); },
    onDefaultTvServerChange(value) { this.defaultTvServerId = value; this.defaultTvProfileId = null; this.defaultTvRootFolder = null; this.updateProfileConfig(); },
    onAnimeMovieServerChange(value) { this.animeMovieServerId = value; this.animeMovieProfileId = null; this.animeMovieRootFolder = null; this.updateProfileConfig(); },
    onAnimeTvServerChange(value) { this.animeTvServerId = value; this.animeTvProfileId = null; this.animeTvRootFolder = null; this.updateProfileConfig(); },
    updateProfileConfig() {
      const profileConfig = {};
      if (this.defaultMovieServerId) { profileConfig.default_movie = { serverId: parseInt(this.defaultMovieServerId) }; if (this.defaultMovieProfileId) profileConfig.default_movie.profileId = parseInt(this.defaultMovieProfileId); if (this.defaultMovieRootFolder) profileConfig.default_movie.rootFolder = this.defaultMovieRootFolder; }
      if (this.defaultTvServerId) { profileConfig.default_tv = { serverId: parseInt(this.defaultTvServerId) }; if (this.defaultTvProfileId) profileConfig.default_tv.profileId = parseInt(this.defaultTvProfileId); if (this.defaultTvRootFolder) profileConfig.default_tv.rootFolder = this.defaultTvRootFolder; }
      if (this.animeMovieServerId) { profileConfig.anime_movie = { serverId: parseInt(this.animeMovieServerId) }; if (this.animeMovieProfileId) profileConfig.anime_movie.profileId = parseInt(this.animeMovieProfileId); if (this.animeMovieRootFolder) profileConfig.anime_movie.rootFolder = this.animeMovieRootFolder; }
      if (this.animeTvServerId) { profileConfig.anime_tv = { serverId: parseInt(this.animeTvServerId) }; if (this.animeTvProfileId) profileConfig.anime_tv.profileId = parseInt(this.animeTvProfileId); if (this.animeTvRootFolder) profileConfig.anime_tv.rootFolder = this.animeTvRootFolder; }
      this.localConfig.SEER_ANIME_PROFILE_CONFIG = profileConfig;
    },
    loadSavedProfileConfig() {
      const saved = this.localConfig.SEER_ANIME_PROFILE_CONFIG;
      if (!saved || typeof saved !== 'object') return;
      if (saved.default_movie) { this.defaultMovieServerId = saved.default_movie.serverId != null ? String(saved.default_movie.serverId) : null; this.defaultMovieProfileId = saved.default_movie.profileId != null ? String(saved.default_movie.profileId) : null; this.defaultMovieRootFolder = saved.default_movie.rootFolder || null; }
      if (saved.default_tv) { this.defaultTvServerId = saved.default_tv.serverId != null ? String(saved.default_tv.serverId) : null; this.defaultTvProfileId = saved.default_tv.profileId != null ? String(saved.default_tv.profileId) : null; this.defaultTvRootFolder = saved.default_tv.rootFolder || null; }
      if (saved.anime_movie) { this.animeMovieServerId = saved.anime_movie.serverId != null ? String(saved.anime_movie.serverId) : null; this.animeMovieProfileId = saved.anime_movie.profileId != null ? String(saved.anime_movie.profileId) : null; this.animeMovieRootFolder = saved.anime_movie.rootFolder || null; }
      if (saved.anime_tv) { this.animeTvServerId = saved.anime_tv.serverId != null ? String(saved.anime_tv.serverId) : null; this.animeTvProfileId = saved.anime_tv.profileId != null ? String(saved.anime_tv.profileId) : null; this.animeTvRootFolder = saved.anime_tv.rootFolder || null; }
    },

    async saveSettings() {
      try {
        const dataToSave = { TMDB_API_KEY: this.localConfig.TMDB_API_KEY, OMDB_API_KEY: this.localConfig.OMDB_API_KEY || '', SELECTED_SERVICE: this.localConfig.SELECTED_SERVICE };
        if (this.localConfig.SELECTED_SERVICE === 'plex') {
          Object.assign(dataToSave, { PLEX_TOKEN: this.localConfig.PLEX_TOKEN, PLEX_API_URL: this.localConfig.PLEX_API_URL, PLEX_LIBRARIES: this.localConfig.PLEX_LIBRARIES || [] });
        } else if (this.localConfig.SELECTED_SERVICE === 'jellyfin' || this.localConfig.SELECTED_SERVICE === 'emby') {
          Object.assign(dataToSave, { JELLYFIN_API_URL: this.localConfig.JELLYFIN_API_URL, JELLYFIN_TOKEN: this.localConfig.JELLYFIN_TOKEN, JELLYFIN_LIBRARIES: this.localConfig.JELLYFIN_LIBRARIES || [] });
        }
        Object.assign(dataToSave, {
          SEER_API_URL: this.localConfig.SEER_API_URL, SEER_TOKEN: this.localConfig.SEER_TOKEN,
          SEER_USER_NAME: this.localConfig.SEER_USER_NAME || null, SEER_USER_PSW: this.localConfig.SEER_USER_PSW || null,
          SEER_SESSION_TOKEN: this.localConfig.SEER_SESSION_TOKEN || null,
          SEER_ANIME_PROFILE_CONFIG: this.localConfig.SEER_ANIME_PROFILE_CONFIG || {},
          SEER_REQUEST_DELAY: this.localConfig.SEER_REQUEST_DELAY ?? 2,
          SELECTED_USERS: this.localConfig.SELECTED_USERS || [],
        });
        await this.$emit('save-section', { section: 'services', data: dataToSave });
        this.originalConfig = { ...this.localConfig };
      } catch (error) {
        console.error('Error saving service settings:', error);
      }
    },

    async resetToDefaults() {
      const defaults = {
        TMDB_API_KEY: '', OMDB_API_KEY: '', SELECTED_SERVICE: '', PLEX_TOKEN: '', PLEX_API_URL: '', PLEX_LIBRARIES: [],
        JELLYFIN_API_URL: '', JELLYFIN_TOKEN: '', JELLYFIN_LIBRARIES: [],
        SEER_API_URL: '', SEER_TOKEN: '', SEER_USER_NAME: null, SEER_USER_PSW: null,
        SEER_SESSION_TOKEN: null, SEER_ANIME_PROFILE_CONFIG: {}, SEER_REQUEST_DELAY: 2, SELECTED_USERS: [],
      };
      if (confirm('Are you sure you want to reset all service settings to their defaults?')) {
        this.localConfig = { ...this.localConfig, ...defaults };
        this.seerConnected = false; this.seerAuthenticated = false; this.seerUsers = [];
        this.omdbConnected = false;
        this.radarrServers = []; this.sonarrServers = [];
        this.jellyfinConnected = false; this.jellyfinLibraries = []; this.jellyfinUsers = [];
        this.selectedJellyfinLibraries = []; this.selectedJellyfinUsers = [];
        this.plexConnected = false; this.plexLibraries = []; this.plexUsers = [];
        this.selectedPlexLibraries = []; this.selectedPlexUsers = [];
        await this.saveSettings();
      }
    },
  },
};
</script>

<style scoped>
.settings-services {
  color: var(--color-text-primary);
}

/* Section Header */
.section-header {
  margin-bottom: 2rem;
}
.section-header h2 {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
  color: var(--color-text-primary);
}
.section-header p {
  color: var(--color-text-muted);
  font-size: 1rem;
}

/* Vertical stack layout */
.services-stack {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  margin-bottom: 2rem;
}

/* TMDB + OMDb side by side */
.rating-apis-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

/* Service card */
.service-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--border-radius-md);
  padding: 1.5rem;
}

/* Card header with status badge */
.service-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.service-card h3 {
  font-size: 1.2rem;
  margin: 0;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Status Badge */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.55rem;
  border-radius: 20px;
  font-size: 0.65rem;
  font-weight: 600;
  border: 1.5px solid;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  white-space: nowrap;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.status-connected { background-color: rgba(16, 185, 129, 0.12); border-color: #10b981; color: #10b981; }
.status-connected .status-dot { background-color: #10b981; }
.status-disconnected { background-color: rgba(239, 68, 68, 0.12); border-color: #ef4444; color: #ef4444; }
.status-disconnected .status-dot { background-color: #ef4444; }
.status-warning { background-color: rgba(245, 158, 11, 0.12); border-color: #f59e0b; color: #f59e0b; }
.status-warning .status-dot { background-color: #f59e0b; }

/* Collapsible section */
.collapsible-section {
  margin-top: 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 1rem;
}

.collapsible-toggle {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-primary);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.collapsible-toggle:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.15);
}

.toggle-arrow {
  font-size: 0.75rem;
  transition: transform 0.2s ease;
  color: var(--color-text-muted);
}

.toggle-arrow.expanded {
  transform: rotate(90deg);
}

.toggle-summary {
  margin-left: auto;
  font-size: 0.8rem;
  font-weight: 400;
  color: var(--color-text-muted);
}

.collapsible-content {
  padding-top: 1rem;
}

/* Advanced blocks */
.advanced-block {
  padding: 1rem;
  margin-bottom: 1rem;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--border-radius-sm);
}
.advanced-block:last-child {
  margin-bottom: 0;
}
.advanced-block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}
.advanced-block-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.advanced-block-title i {
  opacity: 0.7;
}
.advanced-block-desc {
  font-size: 0.8rem;
  color: var(--color-text-muted);
  margin: 0 0 1rem 0;
  line-height: 1.4;
}
.inline-badge {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  background: rgba(231, 76, 156, 0.2);
  color: #e74c9c;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 700;
}
.text-btn {
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: var(--border-radius-sm);
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.text-btn:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.1);
}
.text-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.no-items {
  font-size: 0.85rem;
  color: var(--color-text-muted);
  margin: 0;
  padding: 0.75rem;
  background: rgba(255, 255, 255, 0.02);
  border-radius: var(--border-radius-sm);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Chip list (libraries/users) */
.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.75rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 2rem;
  font-size: 0.8rem;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}
.chip:hover {
  border-color: var(--color-primary);
  background: rgba(59, 130, 246, 0.1);
}
.chip.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
}
.chip i {
  font-size: 0.75rem;
  opacity: 0.7;
}
.chip.active i {
  opacity: 1;
}
.chip-avatar {
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  font-weight: 600;
}
.chip.active .chip-avatar {
  background: rgba(255, 255, 255, 0.25);
}
.chip-badge {
  margin-left: 0.25rem;
  padding: 0.1rem 0.35rem;
  border-radius: 0.75rem;
  font-size: 0.6rem;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.8);
  border: none;
  cursor: pointer;
  transition: all 0.15s ease;
}
.chip-badge:hover {
  background: rgba(255, 255, 255, 0.3);
}
.chip-badge.badge-active {
  background: #e74c9c;
  color: white;
}

/* Inline form */
.inline-form {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
}
.inline-form .form-control {
  min-height: 42px;
}
.inline-form .btn {
  min-height: 42px;
  min-width: 42px;
}
.flex-1 {
  flex: 1;
}

/* Profile cards grid */
.profiles-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.75rem;
}
.profile-card {
  padding: 0.75rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--border-radius-sm);
}
.profile-card.anime {
  border-color: rgba(231, 76, 156, 0.3);
  background: rgba(231, 76, 156, 0.05);
}
.profile-card-header {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.profile-card-header i {
  opacity: 0.7;
}
.profile-card.anime .profile-card-header {
  color: #e74c9c;
}
.profile-card.anime .profile-card-header i {
  opacity: 1;
}

/* Form elements */
.form-group {
  margin-bottom: 1.5rem;
}
.form-group:last-child {
  margin-bottom: 0;
}
.form-group label {
  display: block;
  margin-top: 0.5rem;
  font-weight: 500;
  color: #e5e7eb;
}
.form-control {
  width: 100%;
  padding: 0.75rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-primary);
  font-size: 1rem;
  transition: var(--transition-base);
  min-height: 44px;
}
.form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  background: var(--color-bg-active);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}
.form-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.input-group {
  display: flex;
  gap: 0.5rem;
}
.input-group .form-control {
  flex: 1;
}
.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: var(--color-text-muted);
  line-height: 1.4;
}
.mb-3 { margin-bottom: 0.75rem; }

/* Buttons */
.btn {
  padding: 0.5rem 1rem;
  border-radius: var(--border-radius-sm);
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition-base);
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  min-height: 44px;
  min-width: 44px;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--color-primary); color: white; }
.btn-primary:hover:not(:disabled) { background: var(--color-primary-hover); }
.btn-outline { background: var(--color-bg-interactive); color: var(--color-text-primary); border: 1px solid var(--color-border-medium); }
.btn-outline:hover:not(:disabled) { border-color: rgba(255, 255, 255, 0.5); }
.btn-success { background: #10b981; color: white; border: 1px solid #10b981; }
.btn-success:hover:not(:disabled) { background: #059669; }
.btn-sm { padding: 0.375rem 0.75rem; font-size: 0.8125rem; min-height: 44px; min-width: 44px; }
.btn-block { width: 100%; margin-top: 1rem; }
.link { color: var(--color-primary); text-decoration: none; }
.link:hover { text-decoration: underline; }

/* Footer actions */
.settings-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  padding-top: 2rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

/* OMDb info section */
.omdb-info-section {
  margin-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding-top: 0.75rem;
}

.omdb-info-body {
  padding-top: 0.75rem;
  font-size: 0.85rem;
  color: var(--color-text-muted);
}

.omdb-info-lead {
  margin: 0 0 1rem;
  line-height: 1.5;
}

.omdb-pros-cons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.pros-block, .cons-block {
  padding: 0.75rem;
  border-radius: var(--border-radius-sm);
}

.pros-block {
  background: rgba(16, 185, 129, 0.06);
  border: 1px solid rgba(16, 185, 129, 0.15);
}

.cons-block {
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
}

.pros-cons-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.pros-cons-title.pros { color: #10b981; }
.pros-cons-title.cons { color: #ef4444; }

.pros-block ul, .cons-block ul {
  margin: 0;
  padding-left: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.pros-block ul li, .cons-block ul li {
  line-height: 1.4;
}

.omdb-info-footer {
  margin: 0;
  padding: 0.6rem 0.75rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: var(--border-radius-sm);
  border: 1px solid rgba(255, 255, 255, 0.06);
  line-height: 1.4;
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}

.omdb-info-footer i {
  flex-shrink: 0;
  margin-top: 0.15rem;
  color: var(--color-primary);
}

/* Spinner */
.fa-spinner.fa-spin { animation: spin 1s linear infinite; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

/* Responsive */
@media (max-width: 768px) {
  .rating-apis-row { grid-template-columns: 1fr; }
  .omdb-pros-cons { grid-template-columns: 1fr; }
  .service-card { padding: 1rem; }
  .service-header { flex-direction: column; align-items: flex-start; gap: 0.5rem; }
  .input-group { flex-direction: column; }
  .settings-actions { flex-direction: column; align-items: stretch; }
  .inline-form { flex-direction: column; }
  .profiles-grid { grid-template-columns: 1fr; }

  .form-control {
    padding: 0.875rem;
    font-size: 16px;
  }
  .btn {
    width: 100%;
    justify-content: center;
    padding: 0.875rem 1rem;
    font-size: 1rem;
  }
  .btn-sm {
    width: auto;
    min-width: 44px;
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
  }
  .section-header h2 { font-size: 1.5rem; }
  .service-card h3 { font-size: 1.1rem; }
}

@media (max-width: 480px) {
  .services-stack { gap: 1rem; }
  .service-card { padding: 0.75rem; }
  .collapsible-content { padding-top: 0.75rem; }
  .advanced-block { padding: 0.75rem; }
  .form-control { padding: 0.75rem; }
  .btn { padding: 0.75rem; }
  .chip { padding: 0.4rem 0.6rem; font-size: 0.75rem; }
}

/* ── Plex OAuth wizard button ─────────────────────────────────────────────── */
.btn-plex {
  background: #e5a00d;
  color: #1a1a1a;
  font-weight: 700;
  border: none;
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  justify-content: center;
}
.btn-plex:hover:not(:disabled) {
  background: #cc8f0b;
}
.btn-plex:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.oauth-success {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #10b981;
  font-weight: 600;
  font-size: 0.95rem;
}
</style>
