<template>
  <div data-testid="arr-connection" class="min-w-0 px-5 py-4 max-sm:px-4">
    <ServiceCardHeader icon="fas fa-film" title="Radarr &amp; Sonarr" :description="description" :status="status" :status-text="statusText" :folded="isFolded(status)" @toggle="editing = !editing" />
    <div v-show="!isFolded(status)" class="flex min-w-0 flex-col gap-5">
      <div v-for="svc in arrServices" :key="svc.id" :data-testid="`${svc.id}-connection`" class="flex min-w-0 flex-col gap-3">
        <div class="flex flex-col gap-1.5 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
          <label :for="`${svc.id}Url`">{{ svc.name }} URL</label>
          <input :id="`${svc.id}Url`" v-model="localConfig[svc.urlKey]" type="url" autocomplete="off" class="ui-input" :disabled="isLoading" :placeholder="svc.placeholder" />
        </div>
        <div class="flex flex-col gap-1.5 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
          <label :for="`${svc.id}Key`">{{ svc.name }} API key</label>
          <div class="flex gap-2">
            <input :id="`${svc.id}Key`" v-model="localConfig[svc.keyKey]" :type="shown[svc.id] ? 'text' : 'password'" autocomplete="off" class="ui-input" :disabled="isLoading" :placeholder="`${svc.name} API key (Settings → General)`" />
            <button @click="shown[svc.id] = !shown[svc.id]" type="button" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading" :aria-label="`${shown[svc.id] ? 'Hide' : 'Show'} ${svc.name} API key`">
              <i aria-hidden="true" :class="shown[svc.id] ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
          <small class="text-xs leading-normal text-ink-4">{{ svc.requirement }}</small>
        </div>
        <button type="button" class="ui-btn self-start" :disabled="isLoading || !localConfig[svc.urlKey] || !localConfig[svc.keyKey] || testing[svc.id]" @click="testConnection(svc)">
          <i aria-hidden="true" :class="testing[svc.id] ? 'fas fa-spinner fa-spin' : 'fas fa-plug'"></i>
          {{ testing[svc.id] ? 'Testing…' : `Test ${svc.name}` }}
        </button>

        <!-- Where new titles go: only meaningful once the instance answered and its options were read -->
        <div v-if="usesDirectDelivery && options[svc.id]" class="flex min-w-0 flex-col gap-4 rounded-lg border border-edge p-3" :data-testid="`${svc.id}-profiles`">
          <div v-for="kind in kinds" :key="kind.id" class="flex min-w-0 flex-col gap-2">
            <p class="m-0 text-[13px] font-semibold text-ink-2">{{ kind.label }} <span v-if="kind.id === 'anime'" class="font-normal text-ink-4">(optional — empty uses the default)</span></p>
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <select class="ui-input" :aria-label="`${svc.name} ${kind.label} quality profile`" :disabled="isLoading" :value="field(kind, svc, 'profileId') ?? ''" @change="setField(kind, svc, 'profileId', numberOrNull($event.target.value))">
                <option value="">{{ kind.id === 'anime' ? 'Same as default' : 'Choose a quality profile' }}</option>
                <option v-for="profile in options[svc.id].profiles" :key="profile.id" :value="profile.id">{{ profile.name }}</option>
              </select>
              <select class="ui-input" :aria-label="`${svc.name} ${kind.label} root folder`" :disabled="isLoading" :value="field(kind, svc, 'rootFolder') ?? ''" @change="setField(kind, svc, 'rootFolder', $event.target.value || null)">
                <option value="">{{ kind.id === 'anime' ? 'Same as default' : 'Choose a root folder' }}</option>
                <option v-for="folder in options[svc.id].rootFolders" :key="folder.path" :value="folder.path">{{ folder.path }}</option>
              </select>
            </div>
            <div v-if="options[svc.id].tags.length" class="flex flex-wrap gap-2" role="group" :aria-label="`${svc.name} ${kind.label} tags`">
              <label v-for="tag in options[svc.id].tags" :key="tag.id" class="flex cursor-pointer items-center gap-1.5 rounded-full border border-edge px-2.5 py-1 text-xs text-ink-3">
                <input type="checkbox" :checked="(field(kind, svc, 'tags') || []).includes(tag.id)" :disabled="isLoading" @change="toggleTag(kind, svc, tag.id)" />{{ tag.label }}
              </label>
            </div>
            <p v-if="isStale(kind, svc, options[svc.id])" class="ui-alert-bad m-0 text-xs" role="alert">The saved {{ kind.label.toLowerCase() }} profile or root folder no longer exists in {{ svc.name }}. Choose it again.</p>
          </div>
        </div>
      </div>
      <p v-if="backend === 'arr' && unavailableTypes.length" class="ui-alert-bad m-0 text-xs" role="status">Requests for {{ unavailableTypes.join(' and ') }} will be skipped until the matching instance is configured.</p>
      <BaseCheckbox v-if="usesDirectDelivery" v-model="localConfig.ARR_TAG_BY_USER" :disabled="isLoading" label="Also tag each title with who it was suggested for"
        description="Every title SuggestArr adds is tagged suggestarr (cleanup only removes those). This adds suggestarr-user-&lt;name&gt; too." data-testid="arr-tag-by-user" />
    </div>
  </div>
</template>

<script>
import ServiceCardHeader from '../ServiceCardHeader.vue';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import { getArrOptionsApi, testArrApi } from '@/api/api';
import serviceCard from './serviceCard.js';

const ARR_SERVICES = [
  { id: 'radarr', name: 'Radarr', mediaType: 'movie', urlKey: 'RADARR_API_URL', keyKey: 'RADARR_TOKEN', placeholder: 'http://radarr:7878', requirement: 'Movies. Needs Radarr v5 or newer.' },
  { id: 'sonarr', name: 'Sonarr', mediaType: 'tv', urlKey: 'SONARR_API_URL', keyKey: 'SONARR_TOKEN', placeholder: 'http://sonarr:8989', requirement: 'TV shows. Needs Sonarr v4 or newer (older versions cannot be matched to your recommendations).' },
];
const KINDS = [{ id: 'default', label: 'Default' }, { id: 'anime', label: 'Anime' }];

/**
 * Radarr and Sonarr connections. Their library is treated as "already owned" when
 * "Exclude Downloaded Content" is on; with direct delivery they also receive the requests,
 * using the quality profile / root folder / tags chosen here. Saving stays in SettingsServices.
 */
export default {
  name: 'ArrCard',
  mixins: [serviceCard],
  components: { ServiceCardHeader, BaseCheckbox },
  data() {
    return {
      arrServices: ARR_SERVICES,
      kinds: KINDS,
      shown: {},
      testing: {},
      connected: {},
      options: {},
    };
  },
  computed: {
    backend() {
      return this.localConfig.REQUEST_BACKEND || 'seer';
    },
    usesDirectDelivery() {
      return this.backend === 'arr';
    },
    description() {
      return this.usesDirectDelivery
        ? 'Requests are added straight to Radarr and Sonarr.'
        : 'Skip titles already in your Radarr or Sonarr, monitored or not.';
    },
    configured() {
      return ARR_SERVICES.filter((svc) => this.localConfig[svc.urlKey] && this.localConfig[svc.keyKey]);
    },
    unavailableTypes() {
      return ARR_SERVICES.filter((svc) => !this.configured.includes(svc)).map((svc) => (svc.mediaType === 'movie' ? 'movies' : 'TV shows'));
    },
    profilesComplete() {
      return this.configured.every((svc) => this.field(KINDS[0], svc, 'profileId') && this.field(KINDS[0], svc, 'rootFolder'));
    },
    valid() {
      return this.configured.length > 0 && this.configured.every((svc) => this.connected[svc.id]) && (!this.usesDirectDelivery || this.profilesComplete);
    },
    status() {
      if (!this.configured.length) return 'status-disconnected';
      return this.valid ? 'status-connected' : 'status-warning';
    },
    statusText() {
      if (!this.configured.length) return 'Not set';
      if (this.configured.some((svc) => this.testing[svc.id])) return 'Testing…';
      if (this.valid) return 'Connected';
      return this.configured.every((svc) => this.connected[svc.id]) ? 'Choose profiles' : 'Not tested';
    },
  },
  watch: {
    'localConfig.RADARR_API_URL'() { this.forget('radarr'); },
    'localConfig.RADARR_TOKEN'() { this.forget('radarr'); },
    'localConfig.SONARR_API_URL'() { this.forget('sonarr'); },
    'localConfig.SONARR_TOKEN'() { this.forget('sonarr'); },
    valid: { immediate: true, handler(valid) { this.emitValidation('arr', valid); } },
  },
  mounted() {
    if (!this.wizardMode) this.configured.forEach((svc) => this.testConnection(svc, true));
  },
  methods: {
    onReset() {
      this.connected = {};
      this.options = {};
    },
    forget(id) {
      this.connected[id] = false;
      delete this.options[id];
    },
    credentials(svc) {
      return { service: svc.id, [svc.urlKey]: this.localConfig[svc.urlKey], [svc.keyKey]: this.localConfig[svc.keyKey] };
    },
    async testConnection(svc, silent = false) {
      if (this.testing[svc.id]) return;
      if (!silent) this.editing = true; // keep the card open while it is being configured
      const url = this.localConfig[svc.urlKey];
      const key = this.localConfig[svc.keyKey];
      this.testing[svc.id] = true;
      this.connected[svc.id] = false;
      try {
        await testArrApi(this.credentials(svc));
        if (this.localConfig[svc.urlKey] !== url || this.localConfig[svc.keyKey] !== key) return;
        this.connected[svc.id] = true;
        if (!silent && this.$toast) this.$toast.success(`${svc.name} connection verified!`, { position: 'top-right', duration: 3000 });
        await this.loadOptions(svc);
      } catch {
        if (!silent) this._notifyError(`Could not connect to ${svc.name}. Check the URL and API key.`);
      } finally {
        this.testing[svc.id] = false;
      }
    },
    async loadOptions(svc) {
      try {
        const { data } = await getArrOptionsApi(this.credentials(svc));
        this.options[svc.id] = { profiles: data.profiles || [], rootFolders: data.rootFolders || [], tags: data.tags || [] };
      } catch {
        delete this.options[svc.id];
      }
    },
    // ARR_PROFILE_CONFIG: { default_movie: {profileId, rootFolder, tags}, anime_movie: {...}, default_tv, anime_tv }
    entry(kind, svc) {
      return (this.localConfig.ARR_PROFILE_CONFIG || {})[`${kind.id}_${svc.mediaType}`] || {};
    },
    field(kind, svc, name) {
      return this.entry(kind, svc)[name];
    },
    setField(kind, svc, name, value) {
      this.editing = true;
      const key = `${kind.id}_${svc.mediaType}`;
      const next = { ...this.entry(kind, svc), [name]: value };
      const all = { ...(this.localConfig.ARR_PROFILE_CONFIG || {}) };
      if (kind.id === 'anime' && !next.profileId && !next.rootFolder && !(next.tags || []).length) delete all[key];
      else all[key] = next;
      this.localConfig.ARR_PROFILE_CONFIG = all;
    },
    toggleTag(kind, svc, tagId) {
      const tags = new Set(this.field(kind, svc, 'tags') || []);
      if (!tags.delete(tagId)) tags.add(tagId);
      this.setField(kind, svc, 'tags', [...tags]);
    },
    numberOrNull(value) {
      return value === '' ? null : Number(value);
    },
    isStale(kind, svc, options) {
      const profileId = this.field(kind, svc, 'profileId');
      const rootFolder = this.field(kind, svc, 'rootFolder');
      return (profileId && !options.profiles.some((p) => p.id === profileId)) || (rootFolder && !options.rootFolders.some((f) => f.path === rootFolder));
    },
  },
};
</script>
