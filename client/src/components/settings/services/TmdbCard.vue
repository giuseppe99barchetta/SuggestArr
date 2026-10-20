<template>
  <div data-testid="tmdb-connection" :class="wizardMode ? '' : 'min-w-0 rounded-card border border-edge bg-panel p-5 max-sm:p-4 lg:row-span-2 lg:grid lg:grid-rows-subgrid lg:gap-y-0'">
    <ServiceCardHeader v-if="!wizardMode" icon="fas fa-film" title="TMDB" description="Recommendations, posters and metadata." required :status="getTmdbStatus" :status-text="getTmdbStatusText" />

    <div class="flex min-w-0 flex-col">
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
        <button @click="showTmdbKey = !showTmdbKey" type="button" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading" :aria-label="showTmdbKey ? 'Hide TMDB API key' : 'Show TMDB API key'">
          <i aria-hidden="true" :class="showTmdbKey ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
        </button>
      </div>
      <small class="text-xs leading-normal text-ink-4">
        Get one from <a href="https://www.themoviedb.org/settings/api" target="_blank" class="text-brand-ink no-underline hover:underline">TMDB Settings</a>
      </small>
    </div>

    <button
      @click="testTmdbConnection"
      class="ui-btn mt-auto self-start"
      :disabled="isLoading || !localConfig.TMDB_API_KEY || isTmdbTesting"
    >
      <i aria-hidden="true" v-if="isTmdbTesting" class="fas fa-spinner fa-spin"></i>
      <i aria-hidden="true" v-else-if="wizardMode && wizardTmdbConnected" class="fas fa-check"></i>
      <i aria-hidden="true" v-else class="fas fa-plug"></i>
      {{ isTmdbTesting ? 'Testing…' : (wizardMode && wizardTmdbConnected ? 'Connected ✓' : 'Test connection') }}
    </button>
    </div>
  </div>
</template>

<script>
import ServiceCardHeader from '../ServiceCardHeader.vue';
import { testTmdbApi } from '@/api/api';
import serviceCard from './serviceCard.js';

/**
 * TMDb API key: recommendations, posters and metadata.
 * Shares the page's settings through the `serviceCard` mixin; saving stays in SettingsServices.
 */
export default {
  name: 'TmdbCard',
  mixins: [serviceCard],
  components: { ServiceCardHeader },
  data() {
    return {
      showTmdbKey: false,
      // The wizard tests the key itself; the dashboard asks the page to.
      wizardTmdbTesting: false,
      wizardTmdbConnected: false,
    };
  },
  computed: {
    // Wizard-mode TMDB test state
    isTmdbTesting() {
      return this.wizardMode ? this.wizardTmdbTesting : (this.services.testingConnections?.tmdb || false);
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
  },
  methods: {
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
          this.services.$emit('validation-changed', true);
        } catch {
          this.wizardTmdbConnected = false;
          this._notifyError('Invalid TMDB API key. Please check and try again.');
          this.services.$emit('validation-changed', false);
        } finally {
          this.wizardTmdbTesting = false;
        }
      } else {
        await this.services.$emit('test-connection', 'tmdb', {
          api_key: this.localConfig.TMDB_API_KEY.trim(),
        });
      }
    },
  },
};
</script>
