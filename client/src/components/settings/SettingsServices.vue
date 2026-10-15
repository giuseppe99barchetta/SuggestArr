<template>
  <div>
    <!-- Section header hidden in wizard mode (wizard shell provides its own header) -->
    <PageHeader v-if="!wizardMode" title="Connections" subtitle="The services SuggestArr reads from and sends requests to. Test each one after changing it, then save." />

    <div class="mb-5 flex flex-col gap-5">
      <!-- Media Server -->
      <div v-if="showSection('media-server')" :class="wizardMode ? '' : 'min-w-0 rounded-card border border-edge bg-panel p-5 max-sm:p-4'">
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
              <i v-if="plexOAuthLoading" class="fas fa-spinner fa-spin"></i>
              <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" style="width:18px;height:18px;fill:currentColor;flex-shrink:0">
                <path d="M18 18h12v12H18z"/><path d="M6 6h12v12H6zM30 6h12v12H30zM6 30h12v12H6zM30 30h12v12H30z"/>
              </svg>
              {{ plexOAuthLoading ? 'Waiting for Plex authorisation…' : 'Sign in with Plex' }}
            </button>
            <small class="block text-center text-xs leading-normal text-ink-4">
              <i class="fas fa-lock"></i> Opens Plex.tv in a new window for secure authentication.
            </small>
            <!-- Manual token fallback toggle -->
            <button
              @click="plexOAuthManualMode = !plexOAuthManualMode"
              class="flex cursor-pointer items-center gap-1.5 rounded-md border-0 bg-transparent px-2 py-1 text-xs font-semibold text-brand-ink hover:enabled:bg-raised disabled:cursor-not-allowed disabled:opacity-50 mt-2"
            >
              <i class="fas fa-keyboard"></i>
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
                <button @click="showPlexToken = !showPlexToken" type="button" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading">
                  <i :class="showPlexToken ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
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
              <i v-if="plexFetching" class="fas fa-spinner fa-spin"></i>
              <i v-else-if="plexConnected" class="fas fa-check"></i>
              <i v-else class="fas fa-plug"></i>
              {{ plexFetching ? 'Connecting…' : (plexConnected ? 'Connected' : 'Test & load') }}
            </button>
          </template>

          <!-- Step 2: logged in via OAuth → server selection -->
          <template v-if="plexOAuthLoggedIn && !plexOAuthManualMode">
            <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
              <div class="mt-3 flex items-center gap-2 text-[13px] font-semibold text-good">
                <i class="fas fa-check-circle"></i> Authenticated with Plex
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
                  @click="testAndFetchPlex"
                  class="ui-btn w-[42px] shrink-0 px-0"
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
              <button @click="showJellyfinToken = !showJellyfinToken" type="button" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading">
                <i :class="showJellyfinToken ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
              </button>
            </div>
          </div>
          <button
            @click="testAndFetchJellyfin"
            class="ui-btn mt-4"
            :disabled="isLoading || !localConfig.JELLYFIN_API_URL || !localConfig.JELLYFIN_TOKEN || jellyfinFetching"
          >
            <i v-if="jellyfinFetching" class="fas fa-spinner fa-spin"></i>
            <i v-else-if="jellyfinConnected" class="fas fa-check"></i>
            <i v-else class="fas fa-plug"></i>
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
              <p class="mt-1 mb-3.5 text-xs leading-normal text-ink-4">Libraries to monitor. Mark anime libraries with <span class="rounded bg-[#e74c9c]/20 px-1.5 py-px text-[11px] font-bold text-[#e74c9c]">Anime</span> to send them to the anime profiles.</p>
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
                    :class="isAnimeLibrary(localConfig.SELECTED_SERVICE, lib._id) ? 'bg-[#e74c9c] text-white' : 'bg-raised text-ink-3'"
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

      <!-- Seer  -->
      <div v-if="showSection('seer')" :class="wizardMode ? '' : 'min-w-0 rounded-card border border-edge bg-panel p-5 max-sm:p-4'">
        <ServiceCardHeader v-if="!wizardMode" icon="fas fa-paper-plane" title="Jellyseerr / Overseerr" description="Receives the requests. Approved titles are downloaded through Radarr and Sonarr from here." required :status="getSeerStatus" :status-text="getSeerStatusText" />

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
            <button @click="showSeerToken = !showSeerToken" type="button" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading">
              <i :class="showSeerToken ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
        </div>

        <button
          @click="testSeerAndFetchUsers"
          class="ui-btn mt-4"
          :disabled="isLoading || !localConfig.SEER_API_URL || !localConfig.SEER_TOKEN || seerTesting"
        >
          <i v-if="seerTesting" class="fas fa-spinner fa-spin"></i>
          <i v-else-if="seerConnected" class="fas fa-check"></i>
          <i v-else class="fas fa-plug"></i>
          {{ seerTesting ? 'Testing…' : (seerConnected ? 'Connected' : 'Test connection') }}
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
                <fieldset v-for="card in profileCards" :key="card.key" class="m-0 flex min-w-0 flex-col gap-3 rounded-ctl border bg-canvas p-3.5" :class="card.anime ? 'border-[#e74c9c]/30' : 'border-edge'">
                  <legend class="flex items-center gap-1.5 p-0 text-[13px] font-bold" :class="card.anime ? 'text-[#e74c9c]' : 'text-ink [&>i]:text-ink-4'"><i aria-hidden="true" :class="card.icon"></i>{{ card.title }}</legend>
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

      <!-- TMDB -->
      <div v-if="showSection('tmdb')" :class="wizardMode ? '' : 'min-w-0 rounded-card border border-edge bg-panel p-5 max-sm:p-4'">
        <ServiceCardHeader v-if="!wizardMode" icon="fas fa-film" title="TMDB" description="Finds titles similar to what you watched, plus posters and metadata." required :status="getTmdbStatus" :status-text="getTmdbStatusText" />

        <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
          <label for="tmdbApiKey">API key</label>
          <div class="flex gap-2">
            <input
              id="tmdbApiKey"
              v-model="localConfig.TMDB_API_KEY"
              :type="showTmdbKey ? 'text' : 'password'"
              placeholder="Enter your TMDB API key"
              class="ui-input"
              :disabled="isLoading"
            />
            <button @click="showTmdbKey = !showTmdbKey" type="button" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading">
              <i :class="showTmdbKey ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
          <small class="text-xs leading-normal text-ink-4">
            Get one from <a href="https://www.themoviedb.org/settings/api" target="_blank" class="text-brand-ink no-underline hover:underline">TMDB Settings</a>
          </small>
        </div>

        <button
          @click="testTmdbConnection"
          class="ui-btn mt-4"
          :disabled="isLoading || !localConfig.TMDB_API_KEY || isTmdbTesting"
        >
          <i v-if="isTmdbTesting" class="fas fa-spinner fa-spin"></i>
          <i v-else-if="wizardMode && wizardTmdbConnected" class="fas fa-check"></i>
          <i v-else class="fas fa-plug"></i>
          {{ isTmdbTesting ? 'Testing…' : (wizardMode && wizardTmdbConnected ? 'Connected ✓' : 'Test connection') }}
        </button>
      </div>


      <!-- Optional services: side by side in the dashboard -->
      <div v-if="showSection('omdb') || showSection('trakt')" :class="wizardMode ? '' : 'grid gap-5 lg:grid-cols-2'">
        <!-- OMDb (IMDB ratings) -->
        <div v-if="showSection('omdb')" :class="wizardMode ? '' : 'min-w-0 rounded-card border border-edge bg-panel p-5 max-sm:p-4 lg:row-span-2 lg:grid lg:grid-rows-subgrid lg:gap-y-0'">
          <ServiceCardHeader v-if="!wizardMode" icon="fas fa-star" title="IMDb ratings (OMDb)" description="Lets jobs filter suggestions by IMDb rating." :status="getOmdbStatus" :status-text="getOmdbStatusText" />

          <div class="min-w-0">
            <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
              <label for="omdbApiKey">API key</label>
              <div class="flex gap-2">
                <input
                  id="omdbApiKey"
                  v-model="localConfig.OMDB_API_KEY"
                  :type="showOmdbKey ? 'text' : 'password'"
                  placeholder="Enter your OMDb API key (optional)"
                  class="ui-input"
                  :disabled="isLoading"
                />
                <button @click="showOmdbKey = !showOmdbKey" type="button" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading">
                  <i :class="showOmdbKey ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
                </button>
              </div>
              <small class="text-xs leading-normal text-ink-4">
                Optional — needed only when rating source is set to IMDB or Both.
                Free key (1,000 req/day) at <a href="https://www.omdbapi.com/apikey.aspx" target="_blank" class="text-brand-ink no-underline hover:underline">omdbapi.com</a>
              </small>
              <details class="group text-xs leading-relaxed text-ink-3">
                <summary class="flex min-h-10 w-fit cursor-pointer list-none items-center gap-2 rounded-ctl text-brand-ink hover:text-ink [&::-webkit-details-marker]:hidden">
                  <i aria-hidden="true" class="fas fa-info-circle"></i>
                  How IMDb filtering works
                  <i aria-hidden="true" class="fas fa-chevron-down text-[10px] transition-transform group-open:rotate-180"></i>
                </summary>
                <div class="space-y-2 border-l border-edge-strong pl-3">
                  <p class="m-0">OMDb provides IMDb community ratings so jobs can skip suggestions below your minimum score. Choose IMDb to use these ratings on their own, or Both to combine them with TMDb.</p>
                  <p class="m-0">Set the rating source and minimum scores in <strong>Content Filters → Rating &amp; Popularity</strong>. Enabling IMDb filtering adds API calls and can slow down recommendations.</p>
                </div>
              </details>
            </div>

            <button
              @click="testOmdbConnection"
              class="ui-btn mt-4"
              :disabled="isLoading || !localConfig.OMDB_API_KEY || omdbTesting"
            >
              <i v-if="omdbTesting" class="fas fa-spinner fa-spin"></i>
              <i v-else-if="omdbConnected" class="fas fa-check"></i>
              <i v-else class="fas fa-plug"></i>
              {{ omdbTesting ? 'Testing…' : (omdbConnected ? 'Connected' : 'Test connection') }}
            </button>
          </div>
        </div>


        <!-- Trakt -->
        <div v-if="showSection('trakt')" :class="wizardMode ? '' : 'min-w-0 rounded-card border border-edge bg-panel p-5 max-sm:p-4 lg:row-span-2 lg:grid lg:grid-rows-subgrid lg:gap-y-0'">
          <ServiceCardHeader v-if="!wizardMode" icon="fas fa-history" title="Trakt" description="Adds Trakt watch history and personal recommendations. Users link their own accounts from their profile." :status="getTraktStatus" :status-text="getTraktStatusText" />

          <div class="min-w-0">
            <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
              <label for="traktClientId">Client ID</label>
              <input
                id="traktClientId"
                v-model="localConfig.TRAKT_CLIENT_ID"
                type="text"
                placeholder="Enter your Trakt Client ID"
                class="ui-input"
                :disabled="isLoading"
              />
            </div>
            <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
              <label for="traktClientSecret">Client Secret (optional)</label>
              <div class="flex gap-2">
                <input
                  id="traktClientSecret"
                  v-model="localConfig.TRAKT_CLIENT_SECRET"
                  :type="showTraktClientSecret ? 'text' : 'password'"
                  placeholder="Optional for legacy Trakt apps"
                  class="ui-input"
                  :disabled="isLoading"
                />
                <button @click="showTraktClientSecret = !showTraktClientSecret" type="button" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading">
                  <i :class="showTraktClientSecret ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
                </button>
              </div>
              <small class="text-xs leading-normal text-ink-4">
                Create an app at <a href="https://developer.trakt.tv/apps/new" target="_blank" rel="noopener noreferrer" class="text-brand-ink no-underline hover:underline">Trakt Developer</a> with <code>urn:ietf:wg:oauth:2.0:oob</code> as Redirect URI (ignore the insecure-URI warning) and leave Allowed origins empty. New Trakt apps use the Client ID without issuing a Client Secret.
              </small>
            </div>
            <div class="mt-3 flex items-center gap-2 text-[13px] font-semibold text-good" v-if="isTraktAppConfigured">
              <i class="fas fa-check-circle"></i>
              Trakt app credentials configured. Users can link their own Trakt accounts from their profile.
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!wizardMode" class="flex flex-wrap items-center gap-3 rounded-card border px-[18px] py-3.5" :class="hasChanges ? 'sticky bottom-4 z-10 border-brand-soft bg-[#18162b] max-lg:bottom-24' : 'border-edge bg-panel'">
      <span class="flex-[1_1_200px] text-sm" :class="hasChanges ? 'text-brand-ink' : 'text-ink-3'">{{ hasChanges ? 'You have unsaved changes.' : 'All changes saved.' }}</span>
      <button type="button" class="ui-btn border-0 bg-transparent text-ink-3 hover:text-ink" :disabled="isLoading" @click="resetToDefaults">Reset</button>
      <button type="button" class="ui-btn-primary" :disabled="isLoading || !hasChanges" @click="saveSettings">{{ isLoading ? 'Saving…' : 'Save changes' }}</button>
    </div>
  </div>
</template>

<script>
import PageHeader from '@/components/ui/PageHeader.vue';
import ServiceCardHeader from './ServiceCardHeader.vue';
import axios from 'axios';
import {
  testSeerApi, authenticateUser, fetchRadarrServers, fetchSonarrServers,
  fetchJellyfinLibraries, fetchJellyfinUsers, fetchPlexLibraries, fetchPlexUsers,
  testOmdbApi, testTmdbApi
} from '@/api/api';

export default {
  name: 'SettingsServices',
  components: { PageHeader, ServiceCardHeader },
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
      showTraktClientSecret: false,
      // Wizard-mode self-contained TMDB test state
      wizardTmdbTesting: false,
      wizardTmdbConnected: false,
      // OMDb connection test
      omdbTesting: false,
      omdbConnected: false,
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
    isTraktAppConfigured() {
      return !!this.localConfig.TRAKT_CLIENT_ID;
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
        return this.localConfig.TMDB_API_KEY ? 'Not tested' : 'Not set';
      }
      return this.localConfig.TMDB_API_KEY ? 'Connected' : 'Not set';
    },
    getOmdbStatus() {
      if (this.omdbConnected) return 'status-connected';
      if (this.localConfig.OMDB_API_KEY) return 'status-warning';
      return 'status-disconnected';
    },
    getOmdbStatusText() {
      if (this.omdbConnected) return 'Connected';
      if (this.localConfig.OMDB_API_KEY) return 'Not tested';
      return 'Not set';
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
    getTraktStatus() {
      if (this.isTraktAppConfigured) return 'status-connected';
      if (this.localConfig.TRAKT_CLIENT_ID || this.localConfig.TRAKT_CLIENT_SECRET) return 'status-warning';
      return 'status-disconnected';
    },
    getTraktStatusText() {
      if (this.isTraktAppConfigured) return 'Configured';
      if (this.localConfig.TRAKT_CLIENT_ID || this.localConfig.TRAKT_CLIENT_SECRET) return 'Incomplete';
      return 'Not set';
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
    isTraktAppConfigured(val) {
      if (
        this.wizardMode
        && this.wizardSection === 'trakt'
      ) {
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
  mounted() {
    this._runAutoTests();
  },
  methods: {
    _notifyError(message, opts = { position: 'top-right', duration: 5000 }) {
      if (this.$toast) {
        this.$toast.error(message, opts);
        return;
      }
      if (this.wizardMode && typeof window !== 'undefined' && typeof window.alert === 'function') {
        window.alert(message);
      }
    },

    // Runs all silent connection tests in parallel on mount so they don't block each other.
    _runAutoTests() {
      const service = this.localConfig.SELECTED_SERVICE;
      const tasks = [];
      const silent = !this.wizardMode;

      if (service === 'plex' && this.localConfig.PLEX_TOKEN && this.localConfig.PLEX_API_URL) {
        tasks.push(
          this.testAndFetchPlex(silent).then(() => {
            if (this.plexConnected) this.plexOAuthLoggedIn = true;
          }),
        );
      } else if ((service === 'jellyfin' || service === 'emby') &&
                 this.localConfig.JELLYFIN_TOKEN && this.localConfig.JELLYFIN_API_URL) {
        tasks.push(this.testAndFetchJellyfin(silent));
      }

      if (this.localConfig.SEER_API_URL && this.localConfig.SEER_TOKEN) {
        tasks.push(
          this.testSeerAndFetchUsers(silent).then(async () => {
            if (this.seerConnected && this.localConfig.SEER_SESSION_TOKEN) {
              await this.fetchArrServers();
            }
          }),
        );
      }

      if (this.localConfig.OMDB_API_KEY) {
        tasks.push(this.testOmdbConnection(silent));
      }

      Promise.allSettled(tasks);
    },

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
        } catch {
          this.wizardTmdbConnected = false;
          this._notifyError('Invalid TMDB API key. Please check and try again.');
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
      } catch {
        this.omdbConnected = false;
        if (!silent) this._notifyError('Invalid OMDb API key. Please check and try again.');
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
      } catch {
        this._notifyError('Invalid URL format.', { position: 'top-right', duration: 4000 });
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
      } catch {
        this._notifyError('Invalid URL format.', { position: 'top-right', duration: 4000 });
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

    // Download profile methods
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
    // If the user entered a new value, sends it as-is.
    _secretValue(key) {
      const current = this.localConfig[key];
      if (!current) return current || null;
      if (current === this.originalConfig[key]) return '***';
      return current;
    },

    async saveSettings() {
      try {
        const traktClientIdChanged = this.localConfig.TRAKT_CLIENT_ID !== this.originalConfig.TRAKT_CLIENT_ID;
        const traktSecretUnchanged = this.localConfig.TRAKT_CLIENT_SECRET === this.originalConfig.TRAKT_CLIENT_SECRET;
        const traktClientSecret = traktClientIdChanged && traktSecretUnchanged
          ? ''
          : (this._secretValue('TRAKT_CLIENT_SECRET') || '');
        const dataToSave = {
          TMDB_API_KEY: this._secretValue('TMDB_API_KEY'),
          OMDB_API_KEY: this._secretValue('OMDB_API_KEY') || '',
          SELECTED_SERVICE: this.localConfig.SELECTED_SERVICE,
          TRAKT_CLIENT_ID: this.localConfig.TRAKT_CLIENT_ID || '',
          TRAKT_CLIENT_SECRET: traktClientSecret,
        };
        if (this.localConfig.SELECTED_SERVICE === 'plex') {
          Object.assign(dataToSave, {
            PLEX_TOKEN: this._secretValue('PLEX_TOKEN'),
            PLEX_API_URL: this.localConfig.PLEX_API_URL,
            PLEX_LIBRARIES: this.localConfig.PLEX_LIBRARIES || [],
          });
        } else if (this.localConfig.SELECTED_SERVICE === 'jellyfin' || this.localConfig.SELECTED_SERVICE === 'emby') {
          Object.assign(dataToSave, {
            JELLYFIN_API_URL: this.localConfig.JELLYFIN_API_URL,
            JELLYFIN_TOKEN: this._secretValue('JELLYFIN_TOKEN'),
            JELLYFIN_LIBRARIES: this.localConfig.JELLYFIN_LIBRARIES || [],
          });
        }
        Object.assign(dataToSave, {
          SEER_API_URL: this.localConfig.SEER_API_URL,
          SEER_TOKEN: this._secretValue('SEER_TOKEN'),
          SEER_USER_NAME: this.localConfig.SEER_USER_NAME || null,
          SEER_USER_PSW: this._secretValue('SEER_USER_PSW') || null,
          SEER_SESSION_TOKEN: this._secretValue('SEER_SESSION_TOKEN') || null,
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
        TRAKT_CLIENT_ID: '', TRAKT_CLIENT_SECRET: '',
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
