<template>
  <div :class="wizardMode ? '' : 'min-w-0 px-5 py-4 max-sm:px-4'">
    <ServiceCardHeader v-if="!wizardMode" icon="fas fa-paper-plane" title="Jellyseerr / Overseerr" description="Receives the requests. Approved titles are downloaded through Radarr and Sonarr from here." :status="getSeerStatus" :status-text="getSeerStatusText" :folded="isFolded(getSeerStatus)" :summary="localConfig.SEER_API_URL" @toggle="editing = !editing" />
    <div v-show="!isFolded(getSeerStatus)">
      <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
        <label for="seerApiUrl">API URL</label>
        <input id="seerApiUrl" v-model="localConfig.SEER_API_URL" type="url" placeholder="http://localhost:5055" class="ui-input" :disabled="isLoading" @input="onSeerConfigChange" />
      </div>

      <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
        <label for="seerToken">API token</label>
        <div class="flex gap-2">
          <input
            id="seerToken"
            v-model="localConfig.SEER_TOKEN"
            :type="showSeerToken ? 'text' : 'password'"
            placeholder="Enter your API token"
            class="ui-input"
            :disabled="isLoading"
            @input="onSeerConfigChange"
          />
          <button @click="showSeerToken = !showSeerToken" type="button" :aria-label="showSeerToken ? 'Hide Seer token' : 'Show Seer token'" :aria-pressed="showSeerToken.toString()" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading">
            <i aria-hidden="true" :class="showSeerToken ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
          </button>
        </div>
      </div>

      <button
        @click="testSeerAndFetchUsers"
        class="ui-btn mt-4"
        :disabled="isLoading || !localConfig.SEER_API_URL || !localConfig.SEER_TOKEN || seerTesting"
      >
        <i aria-hidden="true" v-if="seerTesting" class="fas fa-spinner fa-spin"></i>
        <i aria-hidden="true" v-else-if="wizardMode && seerConnected" class="fas fa-check"></i>
        <i aria-hidden="true" v-else class="fas fa-plug"></i>
        {{ seerTesting ? 'Testing…' : (wizardMode && seerConnected ? 'Connected' : 'Test connection') }}
      </button>

      <!-- Request settings -->
      <div v-if="seerConnected" class="mt-5 overflow-hidden rounded-ctl border border-edge bg-panel-2">
        <button type="button" class="flex w-full cursor-pointer items-center gap-3 border-0 bg-transparent px-4 py-3 text-left text-inherit hover:bg-raised" :aria-expanded="String(seerAdvancedExpanded)" @click="seerAdvancedExpanded = !seerAdvancedExpanded">
          <span class="grid h-8 w-8 shrink-0 place-items-center rounded-[8px] bg-raised text-[13px] text-ink-3"><i aria-hidden="true" class="fas fa-sliders-h"></i></span>
          <span class="min-w-0 flex-1">
            <span class="block text-sm font-semibold text-ink">Request settings</span>
            <span class="block text-xs text-ink-4">{{ seerAuthenticated ? `As ${selectedSeerUser}` : 'As the admin account' }} · {{ localConfig.SEER_REQUEST_DELAY ?? 2 }}s between requests</span>
          </span>
          <i aria-hidden="true" class="fas fa-chevron-down text-xs text-ink-4 transition-transform" :class="{ 'rotate-180': seerAdvancedExpanded }"></i>
        </button>
        <div v-show="seerAdvancedExpanded" class="divide-y divide-edge border-t border-edge bg-panel">
          <section class="p-4">
            <h4 class="m-0 text-[13px] font-bold text-ink"><label for="seerRequestDelay">Delay between requests</label></h4>
            <p class="mt-1 mb-3.5 text-xs leading-normal text-ink-4">Raise it if Seer's notifications hit rate limits. 0 sends everything at once.</p>
            <div class="flex max-w-[180px] items-center gap-2">
              <input id="seerRequestDelay" v-model.number="localConfig.SEER_REQUEST_DELAY" type="number" min="0" max="60" class="ui-input" :disabled="isLoading" />
              <span class="text-sm text-ink-3">seconds</span>
            </div>
          </section>

          <section class="p-4">
            <h4 class="m-0 text-[13px] font-bold text-ink">Request as a local user</h4>
            <p class="mt-1 mb-3.5 text-xs leading-normal text-ink-4">Sign in as a Seer local user so requests are made on their behalf instead of the admin account.</p>
            <div v-if="seerUsers.length > 0" class="flex gap-2 max-sm:flex-col">
              <select v-model="selectedSeerUser" class="ui-input flex-1" aria-label="Seer user" :disabled="isLoading" @change="onSeerUserChange(selectedSeerUser)">
                <option :value="null" disabled>Select user…</option>
                <option v-for="option in seerUserOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <input v-model="seerUserPassword" type="password" placeholder="Password" aria-label="Seer user password" class="ui-input flex-1" :disabled="isLoading" autocomplete="new-password" />
              <button
                type="button"
                :class="seerAuthenticated ? 'ui-btn shrink-0 text-good' : 'ui-btn-primary shrink-0'"
                :disabled="isLoading || seerAuthenticating || !selectedSeerUser || !seerUserPassword"
                @click="authenticateSeerUser"
              >
                <i v-if="seerAuthenticating" aria-hidden="true" class="fas fa-spinner fa-spin"></i>
                <i v-else-if="seerAuthenticated" aria-hidden="true" class="fas fa-check"></i>
                {{ seerAuthenticated ? 'Signed in' : 'Sign in' }}
              </button>
            </div>
            <p v-else class="m-0 flex items-center gap-2 text-[13px] text-ink-3">No local users found. Requests use the admin account.</p>
          </section>

          <section class="p-4">
            <div class="flex items-baseline justify-between gap-3">
              <h4 class="m-0 text-[13px] font-bold text-ink">Download profiles</h4>
              <button type="button" class="flex cursor-pointer items-center gap-1.5 rounded-md border-0 bg-transparent px-2 py-1 text-xs font-semibold text-brand-ink hover:enabled:bg-raised disabled:cursor-not-allowed disabled:opacity-50" :disabled="loadingServers" @click="fetchArrServers">
                <i aria-hidden="true" :class="loadingServers ? 'fas fa-spinner fa-spin' : 'fas fa-sync-alt'"></i>
                {{ loadingServers ? 'Loading…' : (serversLoaded ? 'Reload' : 'Load servers') }}
              </button>
            </div>
            <p class="mt-1 mb-3.5 text-xs leading-normal text-ink-4">Default Radarr and Sonarr server, quality profile and root folder for automatic requests. Jobs can override them.</p>

            <div v-if="profileCards.length > 0" class="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
              <fieldset v-for="card in profileCards" :key="card.key" class="m-0 flex min-w-0 flex-col gap-3 rounded-ctl border bg-canvas p-3.5" :class="card.anime ? 'border-anime/30' : 'border-edge'">
                <legend class="flex items-center gap-1.5 p-0 text-[13px] font-bold" :class="card.anime ? 'text-anime' : 'text-ink [&>i]:text-ink-4'"><i aria-hidden="true" :class="card.icon"></i>{{ card.title }}</legend>
                <label class="ui-label">Server
                  <select :value="$data[card.key + 'ServerId'] ?? ''" class="ui-input" :disabled="isLoading" @change="card.onServer($event.target.value || null)">
                    <option value="">Seer default</option>
                    <option v-for="option in card.servers" :key="option.value" :value="option.value">{{ option.label }}</option>
                  </select>
                </label>
                <label v-if="card.profiles.length > 0" class="ui-label">Quality profile
                  <select v-model="$data[card.key + 'ProfileId']" class="ui-input" :disabled="isLoading" @change="updateProfileConfig">
                    <option :value="null">Server default</option>
                    <option v-for="option in card.profiles" :key="option.value" :value="option.value">{{ option.label }}</option>
                  </select>
                </label>
                <label v-if="card.folders.length > 0" class="ui-label">Root folder
                  <select v-model="$data[card.key + 'RootFolder']" class="ui-input" :disabled="isLoading" @change="updateProfileConfig">
                    <option :value="null">Server default</option>
                    <option v-for="option in card.folders" :key="option.value" :value="option.value">{{ option.label }}</option>
                  </select>
                </label>
              </fieldset>
            </div>
            <p v-else-if="serversLoaded" class="m-0 flex items-center gap-2 text-[13px] text-ink-3"><i aria-hidden="true" class="fas fa-exclamation-triangle text-caution"></i>No Radarr or Sonarr servers found in Seer.</p>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import ServiceCardHeader from '../ServiceCardHeader.vue';
import { testSeerApi, authenticateUser, fetchRadarrServers, fetchSonarrServers } from '@/api/api';
import serviceCard from './serviceCard.js';

/**
 * Seer (Jellyseerr/Overseerr) connection, request user and default Radarr/Sonarr profiles.
 * Shares the page's settings through the `serviceCard` mixin; saving stays in SettingsServices.
 */
export default {
  name: 'SeerCard',
  mixins: [serviceCard],
  components: { ServiceCardHeader },
  data() {
    return {
      showSeerToken: false,
      seerAdvancedExpanded: false,
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
    };
  },
  computed: {
    getSeerStatus() {
      if (this.seerConnected) return 'status-connected';
      return (this.localConfig.SEER_API_URL && this.localConfig.SEER_TOKEN)
        ? 'status-warning'
        : 'status-disconnected';
    },
    getSeerStatusText() {
      if (this.seerConnected) return 'Connected';
      return (this.localConfig.SEER_API_URL && this.localConfig.SEER_TOKEN)
        ? 'Not tested'
        : 'Not set';
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
    // One card per Seer default profile; `key` prefixes the matching *ServerId/*ProfileId/*RootFolder data fields.
    profileCards() {
      const cards = [];
      if (this.radarrServers.length) cards.push({ key: 'defaultMovie', title: 'Movies', icon: 'fas fa-film', servers: this.radarrServerOptions, profiles: this.defaultMovieProfiles, folders: this.defaultMovieRootFolders, onServer: this.onDefaultMovieServerChange });
      if (this.sonarrServers.length) cards.push({ key: 'defaultTv', title: 'TV shows', icon: 'fas fa-tv', servers: this.sonarrServerOptions, profiles: this.defaultTvProfiles, folders: this.defaultTvRootFolders, onServer: this.onDefaultTvServerChange });
      if (this.radarrServers.length && this.hasAnimeLibraries) cards.push({ key: 'animeMovie', title: 'Anime movies', icon: 'fas fa-torii-gate', anime: true, servers: this.radarrServerOptions, profiles: this.animeMovieProfiles, folders: this.animeMovieRootFolders, onServer: this.onAnimeMovieServerChange });
      if (this.sonarrServers.length && this.hasAnimeLibraries) cards.push({ key: 'animeTv', title: 'Anime TV', icon: 'fas fa-torii-gate', anime: true, servers: this.sonarrServerOptions, profiles: this.animeTvProfiles, folders: this.animeTvRootFolders, onServer: this.onAnimeTvServerChange });
      return cards;
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
    seerConnected(val) {
      this.emitValidation('seer', val);
    },
    // A newly loaded or saved configuration may carry a signed-in Seer user.
    'services.originalConfig': {
      immediate: true,
      handler() {
        this.loadSavedSeerState();
      },
    },
  },
  mounted() {
    if (this.localConfig.SEER_API_URL && this.localConfig.SEER_TOKEN) {
      this.testSeerAndFetchUsers(!this.wizardMode).then(async () => {
        if (this.seerConnected && this.localConfig.SEER_SESSION_TOKEN) {
          await this.fetchArrServers();
        }
      });
    }
  },
  methods: {
    onReset() {
      this.seerConnected = false; this.seerAuthenticated = false; this.seerUsers = [];
      this.radarrServers = []; this.sonarrServers = [];
    },
    async testSeerAndFetchUsers(silent = false) {
      let seerUrl = (this.localConfig.SEER_API_URL || '').trim();
      let seerToken = (this.localConfig.SEER_TOKEN || '').trim();

      // Browser autofill can populate password inputs without updating v-model.
      // Read from DOM as a fallback so test requests still include the token.
      if (!seerUrl) {
        const domUrl = (document.getElementById('seerApiUrl')?.value || '').trim();
        if (domUrl) {
          seerUrl = domUrl;
          this.localConfig.SEER_API_URL = domUrl;
        }
      }
      if (!seerToken) {
        const domToken = (document.getElementById('seerToken')?.value || '').trim();
        if (domToken) {
          seerToken = domToken;
          this.localConfig.SEER_TOKEN = domToken;
        }
      }

      if (!seerUrl || !seerToken) return;
      try {
        const url = seerUrl;
        new URL(url.startsWith('http') ? url : `http://${url}`);
      } catch {
        if (!silent) this._notifyError('Invalid URL format.', { position: 'top-right', duration: 4000 });
        return;
      }
      this.seerTesting = true;
      this.seerConnected = false;
      this.seerUsers = [];
      try {
        const response = await testSeerApi({
          SEER_API_URL: seerUrl,
          SEER_TOKEN: seerToken,
        });
        this.seerUsers = (response.data.users || []).filter(user => user.isLocal);
        this.seerConnected = true;
        this.loadSavedSeerUser();
        if (!silent && this.$toast) this.$toast.success(`Connected! Found ${this.seerUsers.length} local user(s).`, { position: 'top-right', duration: 3000 });
      } catch (error) {
        console.error('Seer connection test failed:', error);
        this.seerConnected = false;
        if (!silent) this._notifyError('Failed to connect. Verify URL and API Key.');
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
        this._notifyError('Incorrect username or password');
      } finally {
        this.seerAuthenticating = false;
      }
    },
    loadSavedSeerState() { if (this.localConfig.SEER_USER_NAME && this.localConfig.SEER_SESSION_TOKEN) this.seerAuthenticated = true; },
    loadSavedSeerUser() {
      if (this.localConfig.SEER_USER_NAME) this.selectedSeerUser = this.localConfig.SEER_USER_NAME;
      if (this.localConfig.SEER_USER_PSW) this.seerUserPassword = this.localConfig.SEER_USER_PSW;
    },

    // Download profile methods,
    async fetchArrServers() {
      this.loadingServers = true;
      this.serversLoaded = false;
      try {
        const payload = {
          SEER_API_URL: this.localConfig.SEER_API_URL,
          SEER_TOKEN: this.localConfig.SEER_TOKEN,
          SEER_SESSION_TOKEN: this.localConfig.SEER_SESSION_TOKEN
        };
        const [radarrRes, sonarrRes] = await Promise.all([
          fetchRadarrServers(payload),
          fetchSonarrServers(payload)
        ]);
        this.radarrServers = radarrRes.data.servers || [];
        this.sonarrServers = sonarrRes.data.servers || [];
        this.loadSavedProfileConfig();
      } catch (error) {
        console.error('Error fetching Radarr/Sonarr servers:', error);
        this.radarrServers = [];
        this.sonarrServers = [];
        this._notifyError('Failed to fetch servers.');
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
      Object.entries(profileConfig).forEach(([key, profile]) => {
        const servers = key.endsWith('_movie') ? this.radarrServers : this.sonarrServers;
        const server = servers.find(item => String(item.id) === String(profile.serverId));
        if (server?.is4k === true) profile.is4k = true;
        if (key.endsWith('_tv')) {
          const languageProfileId = key.startsWith('anime_') ? server?.activeAnimeLanguageProfileId : server?.activeLanguageProfileId;
          if (languageProfileId != null) profile.languageProfileId = languageProfileId;
        }
      });
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

    // Returns the value to send for a secret field on save.
    // If the value is unchanged from what was loaded (originalConfig), sends the
    // sentinel '***' so the backend's _merge_secrets preserves the stored value
    // without re-transmitting the secret over the wire.
    // If the user cleared the field, sends null/empty to allow clearing the stored value.
    // If the user entered a new value, sends it as-is.,
  },
};
</script>
