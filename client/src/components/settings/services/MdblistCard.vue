<template>
  <div data-testid="mdblist-connection" class="min-w-0 px-5 py-4 max-sm:px-4">
    <ServiceCardHeader icon="fas fa-list" title="MDBList" description="Import titles from public lists." :status="getMdblistStatus" :status-text="getMdblistStatusText" :folded="isFolded(getMdblistStatus)" @toggle="editing = !editing" />
    <div v-show="!isFolded(getMdblistStatus)">
      <div class="flex min-w-0 flex-col">
        <div class="mb-4 flex flex-col gap-1.5 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
          <label for="mdblistApiKey">API key</label>
          <div class="flex gap-2">
            <input id="mdblistApiKey" v-model="localConfig.MDBLIST_API_KEY" :type="showMdblistKey ? 'text' : 'password'" autocomplete="off" class="ui-input" :disabled="isLoading" placeholder="Enter your MDBList API key (optional)" />
            <button @click="showMdblistKey = !showMdblistKey" type="button" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading" :aria-label="showMdblistKey ? 'Hide MDBList API key' : 'Show MDBList API key'">
              <i aria-hidden="true" :class="showMdblistKey ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
          <small class="text-xs leading-normal text-ink-4">Get one from <a href="https://mdblist.com/preferences/" target="_blank" rel="noopener noreferrer" class="text-brand-ink no-underline hover:underline">MDBList Preferences</a></small>
        </div>
        <button type="button" class="ui-btn mt-auto self-start" :disabled="isLoading || !localConfig.MDBLIST_API_KEY || mdblistTesting" @click="testMdblistConnection()">
          <i aria-hidden="true" :class="mdblistTesting ? 'fas fa-spinner fa-spin' : 'fas fa-plug'"></i>
          {{ mdblistTesting ? 'Testing…' : 'Test connection' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import ServiceCardHeader from '../ServiceCardHeader.vue';
import { testMdblistApi } from '@/api/api';
import serviceCard from './serviceCard.js';

/**
 * MDBList API key, for importing public lists.
 * Shares the page's settings through the `serviceCard` mixin; saving stays in SettingsServices.
 */
export default {
  name: 'MdblistCard',
  mixins: [serviceCard],
  components: { ServiceCardHeader },
  data() {
    return {
      showMdblistKey: false,
      mdblistTesting: false,
      mdblistConnected: false,
    };
  },
  computed: {
    getMdblistStatus() {
      if (this.mdblistConnected) return 'status-connected';
      return this.localConfig.MDBLIST_API_KEY ? 'status-warning' : 'status-disconnected';
    },
    getMdblistStatusText() {
      if (this.mdblistTesting) return 'Testing…';
      if (this.mdblistConnected) return 'Connected';
      return this.localConfig.MDBLIST_API_KEY ? 'Not tested' : 'Not set';
    },
  },
  watch: {
    'localConfig.MDBLIST_API_KEY'() {
      this.mdblistConnected = false;
    },
  },
  mounted() {
    if (!this.wizardMode && this.localConfig.MDBLIST_API_KEY) this.testMdblistConnection(true);
  },
  methods: {
    async testMdblistConnection(silent = false) {
      const key = this.localConfig.MDBLIST_API_KEY;
      if (!key || this.mdblistTesting) return;
      this.mdblistTesting = true;
      this.mdblistConnected = false;
      try {
        await testMdblistApi(key.trim());
        if (this.localConfig.MDBLIST_API_KEY !== key) return;
        this.mdblistConnected = true;
        if (!silent && this.$toast) this.$toast.success('MDBList connection verified!', { position: 'top-right', duration: 3000 });
      } catch {
        if (this.localConfig.MDBLIST_API_KEY !== key) return;
        if (!silent) this._notifyError('Could not connect to MDBList. Check your API key and try again.');
      } finally {
        this.mdblistTesting = false;
      }
    },
  },
};
</script>
