<template>
  <div :class="wizardMode ? '' : 'min-w-0 px-5 py-4 max-sm:px-4'">
    <ServiceCardHeader v-if="!wizardMode" icon="fas fa-check-double" title="Simkl" description="Adds Simkl watch history to recommendation jobs. Users link their own accounts from their profile." :status="getSimklStatus" :status-text="getSimklStatusText" :folded="isFolded(getSimklStatus)" @toggle="editing = !editing" />
    <div v-show="!isFolded(getSimklStatus)">
      <div class="min-w-0">
        <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
          <label for="simklClientId">Client ID</label>
          <input
            id="simklClientId"
            v-model="localConfig.SIMKL_CLIENT_ID"
            type="text"
            placeholder="Enter your Simkl Client ID"
            class="ui-input"
            :disabled="isLoading"
          />
          <small class="text-xs leading-normal text-ink-4">
            Create an AUTH V2 app at <a href="https://simkl.com/settings/developer/" target="_blank" rel="noopener noreferrer" class="text-brand-ink no-underline hover:underline">Simkl Developer Settings</a> and choose <strong>TV, devices &amp; command line</strong>. The device flow needs no client secret.
          </small>
        </div>
        <div class="mt-3 flex items-center gap-2 text-[13px] font-semibold text-good" v-if="isSimklAppConfigured">
          <i aria-hidden="true" class="fas fa-check-circle"></i>
          Simkl configured. Users can link their own Simkl accounts from their profile.
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import ServiceCardHeader from '../ServiceCardHeader.vue';
import serviceCard from './serviceCard.js';

/**
 * Simkl app client ID; users link their own accounts from their profile.
 * Shares the page's settings through the `serviceCard` mixin; saving stays in SettingsServices.
 */
export default {
  name: 'SimklCard',
  mixins: [serviceCard],
  components: { ServiceCardHeader },
  computed: {
    isSimklAppConfigured() {
      // AUTH V2 device authorization uses only the public client ID.
      return !!this.localConfig.SIMKL_CLIENT_ID;
    },
    getSimklStatus() {
      return this.isSimklAppConfigured ? 'status-connected' : 'status-disconnected';
    },
    getSimklStatusText() {
      return this.isSimklAppConfigured ? 'Configured' : 'Not set';
    },
  },
  watch: {
    isSimklAppConfigured(val) {
      this.emitValidation('simkl', val);
    },
  },
};
</script>
