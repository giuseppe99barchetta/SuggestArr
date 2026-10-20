<template>
  <div>
    <!-- Section header hidden in wizard mode (wizard shell provides its own header) -->
    <PageHeader v-if="!wizardMode" title="Connections" subtitle="The services SuggestArr reads from and sends requests to. Working ones are folded: open one to change it, test it, then save." />

    <div class="mb-5 flex flex-col gap-5">
      <section :class="wizardMode ? '' : 'flex flex-col gap-2'">
        <h3 v-if="!wizardMode" class="m-0 text-xs font-bold tracking-wider text-ink-4 uppercase">Required</h3>
        <div :class="listClass">
          <MediaServerCard v-if="showSection('media-server')" />
          <SeerCard v-if="showSection('seer')" />
          <TmdbCard v-if="showSection('tmdb')" />
        </div>
      </section>

      <section v-if="showSection('omdb') || showSection('trakt') || (!wizardMode && showSection('mdblist'))" :class="wizardMode ? '' : 'flex flex-col gap-2'">
        <h3 v-if="!wizardMode" class="m-0 text-xs font-bold tracking-wider text-ink-4 uppercase">Optional extras</h3>
        <div :class="listClass">
          <MdblistCard v-if="!wizardMode && showSection('mdblist')" />
          <OmdbCard v-if="showSection('omdb')" />
          <TraktCard v-if="showSection('trakt')" />
        </div>
      </section>
    </div>

    <div v-if="!wizardMode" class="flex flex-wrap items-center gap-3 rounded-card border px-[18px] py-3.5" :class="hasChanges ? 'sticky bottom-4 z-10 border-brand-soft bg-panel max-lg:bottom-24' : 'border-transparent px-0'">
      <span class="flex-[1_1_200px] text-sm" :class="hasChanges ? 'text-brand-ink' : 'text-ink-4'">{{ hasChanges ? 'You have unsaved changes.' : 'All changes saved.' }}</span>
      <button type="button" class="ui-btn border-0 bg-transparent text-ink-3 hover:text-ink" :disabled="isLoading" @click="resetToDefaults">Reset</button>
      <button type="button" class="ui-btn-primary" :disabled="isLoading || !hasChanges" @click="saveSettings">{{ isLoading ? 'Saving…' : 'Save changes' }}</button>
    </div>
  </div>
</template>

<script>
import PageHeader from '@/components/ui/PageHeader.vue';
import { confirmDialog } from '@/utils/confirmDialog';
import unsavedChangesGuard from './mixins/unsavedChangesGuard';
import MediaServerCard from './services/MediaServerCard.vue';
import SeerCard from './services/SeerCard.vue';
import TmdbCard from './services/TmdbCard.vue';
import MdblistCard from './services/MdblistCard.vue';
import OmdbCard from './services/OmdbCard.vue';
import TraktCard from './services/TraktCard.vue';

/**
 * Connections page: one card per service (./services), plus the shared draft,
 * change tracking, save and reset. Cards reach this page through `provide`.
 */
export default {
  name: 'SettingsServices',
  mixins: [unsavedChangesGuard],
  components: { PageHeader, MediaServerCard, SeerCard, TmdbCard, MdblistCard, OmdbCard, TraktCard },
  provide() {
    return { services: this };
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
      // Bumped by "Reset" so every card forgets its connection state.
      resetCount: 0,
    };
  },
  computed: {
    // Dashboard: each group is one panel with a row per service.
    listClass() {
      return this.wizardMode ? '' : 'flex flex-col divide-y divide-edge rounded-card border border-edge bg-panel';
    },
    hasChanges() {
      return JSON.stringify(this.localConfig) !== JSON.stringify(this.originalConfig);
    },
  },
  watch: {
    config: {
      immediate: true,
      handler(newConfig) {
        this.localConfig = { ...newConfig };
        this.originalConfig = { ...newConfig };
      },
    },
  },
  beforeUnmount() {
    // Snapshot local config back to the wizard when unmounting a wizard step
    if (this.wizardMode) {
      this.$emit('config-changed', { ...this.localConfig });
    }
  },
  methods: {
    // Returns true when this section should be visible.
    // In dashboard mode (wizardSection null): always true.
    // In wizard mode: only the matching section is visible.
    showSection(section) {
      return !this.wizardSection || this.wizardSection === section;
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
          MDBLIST_API_KEY: this._secretValue('MDBLIST_API_KEY') || '',
          SELECTED_SERVICE: this.localConfig.SELECTED_SERVICE,
          TRAKT_CLIENT_ID: this.localConfig.TRAKT_CLIENT_ID || '',
          TRAKT_CLIENT_SECRET: traktClientSecret,
          TRAKT_SYNC_SEEN_FEEDBACK: this.localConfig.TRAKT_SYNC_SEEN_FEEDBACK === true,
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
        TMDB_API_KEY: '', OMDB_API_KEY: '', MDBLIST_API_KEY: '', SELECTED_SERVICE: '', PLEX_TOKEN: '', PLEX_API_URL: '', PLEX_LIBRARIES: [],
        JELLYFIN_API_URL: '', JELLYFIN_TOKEN: '', JELLYFIN_LIBRARIES: [],
        TRAKT_CLIENT_ID: '', TRAKT_CLIENT_SECRET: '', TRAKT_SYNC_SEEN_FEEDBACK: false,
        SEER_API_URL: '', SEER_TOKEN: '', SEER_USER_NAME: null, SEER_USER_PSW: null,
        SEER_SESSION_TOKEN: null, SEER_ANIME_PROFILE_CONFIG: {}, SEER_REQUEST_DELAY: 2, SELECTED_USERS: [],
      };
      if (await confirmDialog({ title: 'Reset service settings?', message: 'All connections are cleared and saved: TMDb, your media server, Seer, Trakt, OMDb and MDBList.', confirmLabel: 'Reset', danger: true })) {
        this.localConfig = { ...this.localConfig, ...defaults };
        this.resetCount += 1; // each card forgets its connection state (serviceCard onReset)
        await this.saveSettings();
      }
    },
  },
};
</script>
