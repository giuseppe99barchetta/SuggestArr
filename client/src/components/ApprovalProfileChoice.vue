<template>
  <div v-if="types.length || notice" class="mt-5 flex flex-col gap-3">
    <p class="m-0 text-xs font-bold uppercase tracking-wider text-ink-4">Quality profile</p>
    <p v-if="notice" class="m-0 text-sm text-caution" role="status">{{ notice }}</p>
    <div v-for="type in types" :key="type" class="grid items-end gap-2.5 sm:grid-cols-[auto_repeat(3,minmax(0,1fr))]">
      <span class="self-center rounded-md bg-raised px-2 py-1 text-xs font-bold text-ink-2">{{ type === 'movie' ? 'Movie' : 'TV' }}</span>
      <label class="flex flex-col gap-1 text-xs font-semibold text-ink-3">
        Server
        <select :value="chosen[type].serverId ?? ''" class="h-10 rounded-ctl border border-edge-strong bg-canvas px-2.5 text-sm text-ink" @change="setServer(type, $event.target.value)">
          <option value="">Use Seer default</option>
          <option v-for="option in serverOptions(type)" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>
      <template v-if="isChosen(chosen[type].serverId)">
        <label class="flex flex-col gap-1 text-xs font-semibold text-ink-3">
          Quality profile
          <select v-model="chosen[type].profileId" class="h-10 rounded-ctl border border-edge-strong bg-canvas px-2.5 text-sm text-ink">
            <option value="">Select quality profile</option>
            <option v-for="option in profileOptions(type)" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
        </label>
        <label class="flex flex-col gap-1 text-xs font-semibold text-ink-3">
          Root folder
          <select v-model="chosen[type].rootFolder" class="h-10 rounded-ctl border border-edge-strong bg-canvas px-2.5 text-sm text-ink">
            <option value="">Select root folder</option>
            <option v-for="option in rootFolderOptions(type)" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
        </label>
      </template>
    </div>
    <p v-if="types.length" class="m-0 text-sm text-ink-4">Leave the quality profile empty to use the profile the job or Jellyseerr would pick.</p>
  </div>
</template>

<script>
import { approvalProfileNotice, buildProfilePayload, choiceForServer, defaultChoice, isChosen, profileTypes } from '@/utils/requestProfiles.js';

// The server / quality profile / root folder choice shown while approving.
// The host owns the dialog and the servers; it asks `payload()` on confirm.
export default {
  name: 'ApprovalProfileChoice',
  props: {
    // null while the servers are still loading.
    servers: { type: Object, default: null },
    mediaTypes: { type: Array, default: () => [] }
  },
  data() { return { chosen: { movie: {}, tv: {} } }; },
  computed: {
    types() { return profileTypes(this.mediaTypes, this.servers); },
    notice() { return approvalProfileNotice(this.servers); }
  },
  watch: {
    mediaTypes() { this.chosen = { movie: {}, tv: {} }; this.fillDefaults(); },
    // The servers may arrive after the dialog opened.
    servers() { this.fillDefaults(); }
  },
  created() { this.fillDefaults(); },
  methods: {
    isChosen,
    serversFor(type) { return (this.servers || {})[type] || []; },
    selectedServer(type) { return this.serversFor(type).find(server => String(server.id) === String(this.chosen[type].serverId)); },
    serverOptions(type) { return this.serversFor(type).map(server => ({ value: server.id, label: `${server.name}${server.is4k ? ' (4K)' : ''}` })); },
    profileOptions(type) { return (this.selectedServer(type)?.profiles || []).map(profile => ({ value: profile.id, label: profile.name })); },
    rootFolderOptions(type) { return (this.selectedServer(type)?.rootFolders || []).map(folder => ({ value: folder.path, label: folder.path })); },
    // Only where nothing is chosen yet: a server someone picked stays picked.
    fillDefaults() {
      for (const type of this.types) {
        if (!isChosen(this.chosen[type].serverId)) this.chosen[type] = defaultChoice(this.serversFor(type));
      }
    },
    setServer(type, serverId) {
      const server = this.serversFor(type).find(item => String(item.id) === String(serverId));
      this.chosen[type] = choiceForServer(server, serverId);
    },
    payload() { return buildProfilePayload(this.types, this.chosen); }
  }
};
</script>

