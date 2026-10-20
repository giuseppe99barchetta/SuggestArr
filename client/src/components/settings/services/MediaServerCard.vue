<template>
  <div :class="wizardMode ? '' : 'min-w-0 rounded-card border border-edge bg-panel p-5 max-sm:p-4'">
    <ServiceCardHeader v-if="!wizardMode" icon="fas fa-server" title="Media server" description="Where SuggestArr reads users, libraries and watch history from." required :status="getMediaServerStatus" :status-text="getMediaServerStatusText" />

    <div v-if="!wizardMode" class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
      <label for="selectedService">Service</label>
      <select id="selectedService" v-model="localConfig.SELECTED_SERVICE" class="ui-input" :disabled="isLoading">
        <option value="" disabled>Select a service</option>
        <option v-for="option in serviceOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
    </div>

    <!-- Plex: OAuth flow (both wizard and dashboard) -->
    <template v-if="localConfig.SELECTED_SERVICE === 'plex'">
      <!-- Step 1: not yet logged in → show Sign in button -->
      <div v-if="!plexOAuthLoggedIn" class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
        <button
          @click="loginWithPlexOAuth"
          class="ui-btn w-full border-[#e5a00d] bg-[#e5a00d] font-bold text-[#1a1a1a] hover:bg-[#cc8f0b]"
          :disabled="plexOAuthLoading"
        >
          <i aria-hidden="true" v-if="plexOAuthLoading" class="fas fa-spinner fa-spin"></i>
          <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" style="width:18px;height:18px;fill:currentColor;flex-shrink:0">
            <path d="M18 18h12v12H18z"/><path d="M6 6h12v12H6zM30 6h12v12H30zM6 30h12v12H6zM30 30h12v12H30z"/>
          </svg>
          {{ plexOAuthLoading ? 'Waiting for Plex authorisation…' : 'Sign in with Plex' }}
        </button>
        <small class="block text-center text-xs leading-normal text-ink-4">
          <i aria-hidden="true" class="fas fa-lock"></i> Opens Plex.tv in a new window for secure authentication.
        </small>
        <!-- Manual token fallback toggle -->
        <button
          @click="plexOAuthManualMode = !plexOAuthManualMode"
          class="flex cursor-pointer items-center gap-1.5 rounded-md border-0 bg-transparent px-2 py-1 text-xs font-semibold text-brand-ink hover:enabled:bg-raised disabled:cursor-not-allowed disabled:opacity-50 mt-2"
        >
          <i aria-hidden="true" class="fas fa-keyboard"></i>
          {{ plexOAuthManualMode ? 'Use Plex login instead' : 'Enter token manually' }}
        </button>
      </div>

      <!-- Manual token fallback (also shown when user toggles it) -->
      <template v-if="plexOAuthManualMode">
        <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
          <label for="plexTokenWizard">Plex token</label>
          <div class="flex gap-2">
            <input
              id="plexTokenManual"
              v-model="localConfig.PLEX_TOKEN"
              :type="showPlexToken ? 'text' : 'password'"
              placeholder="Enter your Plex token"
              class="ui-input"
              :disabled="isLoading"
            />
            <button @click="showPlexToken = !showPlexToken" type="button" :aria-label="showPlexToken ? 'Hide Plex token' : 'Show Plex token'" :aria-pressed="showPlexToken.toString()" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading">
              <i aria-hidden="true" :class="showPlexToken ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
        </div>
        <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
          <label for="plexApiUrlManual">API URL</label>
          <input id="plexApiUrlManual" v-model="localConfig.PLEX_API_URL" type="url" placeholder="http://localhost:32400" class="ui-input" :disabled="isLoading" />
        </div>
        <button
          @click="testAndFetchPlex"
          class="ui-btn mt-4"
          :disabled="!localConfig.PLEX_TOKEN || !localConfig.PLEX_API_URL || plexFetching"
        >
          <i aria-hidden="true" v-if="plexFetching" class="fas fa-spinner fa-spin"></i>
          <i aria-hidden="true" v-else-if="plexConnected" class="fas fa-check"></i>
          <i aria-hidden="true" v-else class="fas fa-plug"></i>
          {{ plexFetching ? 'Connecting…' : (plexConnected ? 'Connected' : 'Test & load') }}
        </button>
      </template>

      <!-- Step 2: logged in via OAuth → server selection -->
      <template v-if="plexOAuthLoggedIn && !plexOAuthManualMode">
        <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
          <div class="mt-3 flex items-center gap-2 text-[13px] font-semibold text-good">
            <i aria-hidden="true" class="fas fa-check-circle"></i> Authenticated with Plex
          </div>
        </div>
        <!-- Multiple servers: dropdown -->
        <div v-if="plexOAuthConnectionOptions.length > 1" class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
          <label>Server connection</label>
          <select v-model="plexOAuthSelectedConnIdx" class="ui-input" @change="onPlexOAuthServerSelect(plexOAuthSelectedConnIdx)">
            <option :value="null" disabled>Choose a server connection…</option>
            <option v-for="option in plexOAuthConnectionOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
        </div>
        <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
          <label>Or enter URL manually</label>
          <div class="flex gap-2">
            <input v-model="localConfig.PLEX_API_URL" type="url" placeholder="http://localhost:32400" class="ui-input" />
            <button
              type="button"
              aria-label="Test connection and load libraries"
              title="Test connection and load libraries"
              @click="testAndFetchPlex"
              class="ui-btn w-[42px] shrink-0 px-0"
              :disabled="!localConfig.PLEX_API_URL || plexFetching"
            >
              <i aria-hidden="true" v-if="plexFetching" class="fas fa-spinner fa-spin"></i>
              <i aria-hidden="true" v-else class="fas fa-plug"></i>
            </button>
          </div>
        </div>
      </template>
    </template>


    <!-- Jellyfin / Emby fields -->
    <template v-if="localConfig.SELECTED_SERVICE === 'jellyfin' || localConfig.SELECTED_SERVICE === 'emby'">
      <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
        <label for="jellyfinApiUrl">{{ localConfig.SELECTED_SERVICE === 'emby' ? 'Emby' : 'Jellyfin' }} URL</label>
        <input id="jellyfinApiUrl" v-model="localConfig.JELLYFIN_API_URL" type="url" placeholder="http://localhost:8096" class="ui-input" :disabled="isLoading" />
      </div>
      <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
        <label for="jellyfinToken">API token</label>
        <div class="flex gap-2">
          <input
            id="jellyfinToken"
            v-model="localConfig.JELLYFIN_TOKEN"
            :type="showJellyfinToken ? 'text' : 'password'"
            placeholder="Enter your API token"
            class="ui-input"
            :disabled="isLoading"
          />
          <button @click="showJellyfinToken = !showJellyfinToken" type="button" :aria-label="showJellyfinToken ? 'Hide token' : 'Show token'" :aria-pressed="showJellyfinToken.toString()" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading">
            <i aria-hidden="true" :class="showJellyfinToken ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
          </button>
        </div>
      </div>
      <button
        @click="testAndFetchJellyfin"
        class="ui-btn mt-4"
        :disabled="isLoading || !localConfig.JELLYFIN_API_URL || !localConfig.JELLYFIN_TOKEN || jellyfinFetching"
      >
        <i aria-hidden="true" v-if="jellyfinFetching" class="fas fa-spinner fa-spin"></i>
        <i aria-hidden="true" v-else-if="jellyfinConnected" class="fas fa-check"></i>
        <i aria-hidden="true" v-else class="fas fa-plug"></i>
        {{ jellyfinFetching ? 'Connecting…' : (jellyfinConnected ? 'Connected' : 'Test & load') }}
      </button>
    </template>

    <!-- Libraries & users -->
    <div v-if="mediaServerConnected" class="mt-5 overflow-hidden rounded-ctl border border-edge bg-panel-2">
      <button type="button" class="flex w-full cursor-pointer items-center gap-3 border-0 bg-transparent px-4 py-3 text-left text-inherit hover:bg-raised" :aria-expanded="String(mediaServerAdvancedExpanded)" @click="mediaServerAdvancedExpanded = !mediaServerAdvancedExpanded">
        <span class="grid h-8 w-8 shrink-0 place-items-center rounded-[8px] bg-raised text-[13px] text-ink-3"><i aria-hidden="true" class="fas fa-photo-video"></i></span>
        <span class="min-w-0 flex-1">
          <span class="block text-sm font-semibold text-ink">Libraries and users</span>
          <span class="block text-xs text-ink-4">{{ currentSelectedLibraries.length }} libraries · {{ currentSelectedUsers.length }} users selected</span>
        </span>
        <i aria-hidden="true" class="fas fa-chevron-down text-xs text-ink-4 transition-transform" :class="{ 'rotate-180': mediaServerAdvancedExpanded }"></i>
      </button>
      <div v-show="mediaServerAdvancedExpanded" class="divide-y divide-edge border-t border-edge bg-panel">
        <section class="p-4">
          <div class="flex items-baseline justify-between gap-3">
            <h4 class="m-0 text-[13px] font-bold text-ink">Libraries</h4>
            <button v-if="currentSelectedLibraries.length > 0" type="button" class="flex cursor-pointer items-center gap-1.5 rounded-md border-0 bg-transparent px-2 py-1 text-xs font-semibold text-brand-ink hover:enabled:bg-raised disabled:cursor-not-allowed disabled:opacity-50" @click="clearCurrentLibraries">Clear</button>
          </div>
          <p class="mt-1 mb-3.5 text-xs leading-normal text-ink-4">Libraries to monitor. Mark anime libraries with <span class="rounded bg-anime/20 px-1.5 py-px text-[11px] font-bold text-anime">Anime</span> to send them to the anime profiles.</p>
          <div v-if="currentLibraries.length > 0" class="flex flex-wrap gap-2">
            <div
              v-for="lib in currentLibraries"
              :key="lib._id"
              role="checkbox"
              tabindex="0"
              :aria-checked="String(isLibSelected(lib._id))"
              class="inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] [&>i]:text-[11px] [&>i]:opacity-70"
              :class="isLibSelected(lib._id) ? 'border-brand-ink bg-brand-soft/60 text-ink' : 'border-edge-strong bg-canvas text-ink-3 hover:border-ink-4 hover:text-ink'"
              @click="toggleLibrary(lib)"
              @keydown.space.prevent="toggleLibrary(lib)"
            >
              <i aria-hidden="true" :class="isLibSelected(lib._id) ? 'fas fa-check' : getLibraryIcon(lib._type)"></i>
              <span>{{ lib._name }}</span>
              <button
                v-if="isLibSelected(lib._id)"
                type="button"
                class="cursor-pointer rounded border-0 px-1.5 py-px text-[10px] font-bold"
                :class="isAnimeLibrary(localConfig.SELECTED_SERVICE, lib._id) ? 'bg-anime text-white' : 'bg-raised text-ink-3'"
                :aria-pressed="String(isAnimeLibrary(localConfig.SELECTED_SERVICE, lib._id))"
                title="Mark as anime"
                @click.stop="toggleAnimeFlag(localConfig.SELECTED_SERVICE, lib._id)"
              >Anime</button>
            </div>
          </div>
          <p v-else class="m-0 flex items-center gap-2 text-[13px] text-ink-3">No libraries found.</p>
        </section>

        <section class="p-4">
          <div class="flex items-baseline justify-between gap-3">
            <h4 class="m-0 text-[13px] font-bold text-ink">Users</h4>
            <button v-if="currentSelectedUsers.length > 0" type="button" class="flex cursor-pointer items-center gap-1.5 rounded-md border-0 bg-transparent px-2 py-1 text-xs font-semibold text-brand-ink hover:enabled:bg-raised disabled:cursor-not-allowed disabled:opacity-50" @click="clearCurrentUsers">Clear</button>
          </div>
          <p class="mt-1 mb-3.5 text-xs leading-normal text-ink-4">Users whose watch history drives suggestions.</p>
          <div v-if="currentUsers.length > 0" class="flex flex-wrap gap-2">
            <div
              v-for="user in currentUsers"
              :key="user.id"
              role="checkbox"
              tabindex="0"
              :aria-checked="String(isUserSelected(user.id))"
              class="inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] [&>i]:text-[11px] [&>i]:opacity-70"
              :class="isUserSelected(user.id) ? 'border-brand-ink bg-brand-soft/60 text-ink' : 'border-edge-strong bg-canvas text-ink-3 hover:border-ink-4 hover:text-ink'"
              @click="toggleUser(user)"
              @keydown.space.prevent="toggleUser(user)"
            >
              <span class="flex h-5 w-5 items-center justify-center rounded-full bg-raised text-[10px] font-bold">{{ (user.name || 'U').charAt(0).toUpperCase() }}</span>
              <span>{{ user.name }}</span>
            </div>
          </div>
          <p v-else class="m-0 flex items-center gap-2 text-[13px] text-ink-3">No users found.</p>
        </section>
      </div>
    </div>
  </div>
</template>

<script>
import ServiceCardHeader from '../ServiceCardHeader.vue';
import axios from 'axios';
import { fetchJellyfinLibraries, fetchJellyfinUsers, fetchPlexLibraries, fetchPlexUsers } from '@/api/api';
import serviceCard from './serviceCard.js';

/**
 * Media server connection (Plex, Jellyfin or Emby), its libraries and users.
 * Shares the page's settings through the `serviceCard` mixin; saving stays in SettingsServices.
 */
export default {
  name: 'MediaServerCard',
  mixins: [serviceCard],
  components: { ServiceCardHeader },
  data() {
    return {
      showPlexToken: false,
      showJellyfinToken: false,
      mediaServerAdvancedExpanded: false,
      serviceOptions: [
        { value: 'plex', label: 'Plex' },
        { value: 'jellyfin', label: 'Jellyfin' },
        { value: 'emby', label: 'Emby' }
      ],
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
      // Plex OAuth
      plexOAuthLoading: false,
      plexOAuthLoggedIn: false,
      plexOAuthServers: [],
      plexOAuthSelectedConnIdx: null,
      plexOAuthManualMode: false,
      plexOAuthPollTimer: null,
    };
  },
  computed: {
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
      return 'Not tested';
    },
  },
  watch: {
    // Wizard step validation: the media server step is done once it connects.
    jellyfinConnected(val) {
      this.emitValidation('media-server', val);
    },
    plexConnected(val) {
      this.emitValidation('media-server', val);
    },
  },
  mounted() {
    // Silent connection check of the saved server (with toasts in the wizard).
    const service = this.localConfig.SELECTED_SERVICE;
    const silent = !this.wizardMode;
    if (service === 'plex' && this.localConfig.PLEX_TOKEN && this.localConfig.PLEX_API_URL) {
      this.testAndFetchPlex(silent).then(() => {
        if (this.plexConnected) this.plexOAuthLoggedIn = true;
      });
    } else if ((service === 'jellyfin' || service === 'emby') &&
               this.localConfig.JELLYFIN_TOKEN && this.localConfig.JELLYFIN_API_URL) {
      this.testAndFetchJellyfin(silent);
    }
  },
  beforeUnmount() {
    if (this.plexOAuthPollTimer) clearInterval(this.plexOAuthPollTimer);
  },
  methods: {
    onReset() {
      this.jellyfinConnected = false; this.jellyfinLibraries = []; this.jellyfinUsers = [];
      this.selectedJellyfinLibraries = []; this.selectedJellyfinUsers = [];
      this.plexConnected = false; this.plexLibraries = []; this.plexUsers = [];
      this.selectedPlexLibraries = []; this.selectedPlexUsers = [];
    },
    async loginWithPlexOAuth() {
      this.plexOAuthLoading = true;
      try {
        const res = await axios.post('/api/plex/auth');
        const { pin_id, auth_url } = res.data;
        window.open(auth_url, '_blank', 'width=800,height=600');
        this.plexOAuthPollTimer = setInterval(() => this.pollPlexOAuth(pin_id), 3000);
      } catch {
        this._notifyError('Error starting Plex login.');
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
        this._notifyError('Error fetching Plex servers.');
      }
    },
    async onPlexOAuthServerSelect(url) {
      this.localConfig.PLEX_API_URL = url;
      await this.testAndFetchPlex();
    },

    // Unified library/user helpers for the template,
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
    async testJellyfinConnection() {
      if (!this.localConfig.JELLYFIN_API_URL || !this.localConfig.JELLYFIN_TOKEN) return;
      try {
        const url = this.localConfig.JELLYFIN_API_URL.trim();
        const testUrl = url.startsWith('http') ? url : `http://${url}`;
        new URL(testUrl);
      } catch {
        this._notifyError('Invalid URL format.', { position: 'top-right', duration: 4000 });
        return;
      }
      await this.services.$emit('test-connection', 'jellyfin', {
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
      } catch {
        this._notifyError('Invalid URL format.', { position: 'top-right', duration: 4000 });
        return;
      }
      await this.services.$emit('test-connection', 'plex', {
        token: this.localConfig.PLEX_TOKEN.trim(),
        api_url: this.localConfig.PLEX_API_URL.trim(),
      });
    },
    async testAndFetchJellyfin(silent = false) {
      if (!this.localConfig.JELLYFIN_API_URL || !this.localConfig.JELLYFIN_TOKEN) return;
      try {
        const url = this.localConfig.JELLYFIN_API_URL.trim();
        new URL(url.startsWith('http') ? url : `http://${url}`);
      } catch {
        if (!silent) this._notifyError('Invalid URL format.', { position: 'top-right', duration: 4000 });
        return;
      }
      this.jellyfinFetching = true;
      this.jellyfinConnected = false;
      try {
        const fetchPayload = {
          JELLYFIN_API_URL: this.localConfig.JELLYFIN_API_URL,
          JELLYFIN_TOKEN: this.localConfig.JELLYFIN_TOKEN,
        };

        const libRes = await fetchJellyfinLibraries(fetchPayload);
        this.jellyfinLibraries = libRes.data.items || [];
        this.jellyfinConnected = true;
        this.loadSavedJellyfinLibraries();
        try {
          const userRes = await fetchJellyfinUsers(fetchPayload);
          this.jellyfinUsers = userRes.data.users || [];
          this.loadSavedJellyfinUsers();
        } catch (e) { console.error('Error fetching Jellyfin users:', e); }
        if (!silent && this.$toast) this.$toast.success(`Connected! Found ${this.jellyfinLibraries.length} libraries.`, { position: 'top-right', duration: 3000 });
      } catch (error) {
        console.error('Jellyfin connection failed:', error);
        this.jellyfinConnected = false;
        this.jellyfinLibraries = [];
        this.jellyfinUsers = [];
        if (!silent) {
          const status = error?.response?.status;
          const serverMsg = error?.response?.data?.message;
          if (status === 401 || status === 403) {
            this._notifyError('Jellyfin rejected the API key (401). Ensure you are using a server-level API key from Dashboard → API Keys, not a user session token.');
          } else if (serverMsg) {
            this._notifyError(`Failed to connect: ${serverMsg}`);
          } else {
            this._notifyError('Failed to connect. Check your Jellyfin URL and API key.');
          }
        }
      } finally {
        this.jellyfinFetching = false;
      }
    },
    async testAndFetchPlex(silent = false) {
      if (!this.localConfig.PLEX_API_URL || !this.localConfig.PLEX_TOKEN) return;
      try {
        const url = this.localConfig.PLEX_API_URL.trim();
        new URL(url.startsWith('http') ? url : `http://${url}`);
      } catch {
        if (!silent) this._notifyError('Invalid URL format.', { position: 'top-right', duration: 4000 });
        return;
      }
      this.plexFetching = true;
      this.plexConnected = false;
      try {
        const libRes = await fetchPlexLibraries({
          PLEX_API_URL: this.localConfig.PLEX_API_URL,
          PLEX_TOKEN: this.localConfig.PLEX_TOKEN,
        });
        this.plexLibraries = libRes.data.items || [];
        this.plexConnected = true;
        this.loadSavedPlexLibraries();
        try {
          const userRes = await fetchPlexUsers({
            PLEX_API_URL: this.localConfig.PLEX_API_URL,
            PLEX_TOKEN: this.localConfig.PLEX_TOKEN,
          });
          this.plexUsers = userRes.data.users || [];
          this.loadSavedPlexUsers();
        } catch (e) { console.error('Error fetching Plex users:', e); }
        if (!silent && this.$toast) this.$toast.success(`Connected! Found ${this.plexLibraries.length} libraries.`, { position: 'top-right', duration: 3000 });
      } catch (error) {
        console.error('Plex connection failed:', error);
        this.plexConnected = false;
        this.plexLibraries = [];
        this.plexUsers = [];
        if (!silent) this._notifyError('Failed to connect. Check your URL and token.');
      } finally {
        this.plexFetching = false;
      }
    },

    // Jellyfin library/user selection,
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

    // Plex library/user selection,
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

    // Shared helpers,
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

    // Seer connection test + user fetch,
  },
};
</script>
