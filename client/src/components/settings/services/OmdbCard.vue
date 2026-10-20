<template>
  <div :class="wizardMode ? '' : 'min-w-0 px-5 py-4 max-sm:px-4'">
    <ServiceCardHeader v-if="!wizardMode" icon="fas fa-star" title="IMDb ratings (OMDb)" description="Lets jobs filter suggestions by IMDb rating." :status="getOmdbStatus" :status-text="getOmdbStatusText" :folded="isFolded(getOmdbStatus)" @toggle="editing = !editing" />
    <div v-show="!isFolded(getOmdbStatus)">
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
            <button @click="showOmdbKey = !showOmdbKey" type="button" :aria-label="showOmdbKey ? 'Hide OMDb API key' : 'Show OMDb API key'" :aria-pressed="showOmdbKey.toString()" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading">
              <i aria-hidden="true" :class="showOmdbKey ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
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
          <i aria-hidden="true" v-if="omdbTesting" class="fas fa-spinner fa-spin"></i>
          <i aria-hidden="true" v-else-if="wizardMode && omdbConnected" class="fas fa-check"></i>
          <i aria-hidden="true" v-else class="fas fa-plug"></i>
          {{ omdbTesting ? 'Testing…' : (wizardMode && omdbConnected ? 'Connected' : 'Test connection') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import ServiceCardHeader from '../ServiceCardHeader.vue';
import { testOmdbApi } from '@/api/api';
import serviceCard from './serviceCard.js';

/**
 * OMDb API key, for filtering suggestions by IMDb rating.
 * Shares the page's settings through the `serviceCard` mixin; saving stays in SettingsServices.
 */
export default {
  name: 'OmdbCard',
  mixins: [serviceCard],
  components: { ServiceCardHeader },
  data() {
    return {
      showOmdbKey: false,
      omdbTesting: false,
      omdbConnected: false,
    };
  },
  computed: {
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
  },
  mounted() {
    if (this.localConfig.OMDB_API_KEY) this.testOmdbConnection(!this.wizardMode);
  },
  methods: {
    onReset() {
      this.omdbConnected = false;
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
        if (!silent) {
          const serverMsg = error?.response?.data?.message;
          this._notifyError(serverMsg || 'Invalid OMDb API key. Please check and try again.');
        }
      } finally {
        this.omdbTesting = false;
      }
    },
  },
};
</script>
