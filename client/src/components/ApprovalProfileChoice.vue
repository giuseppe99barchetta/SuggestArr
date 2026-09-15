<template>
  <div v-if="types.length || notice" class="approval-profile-choice">
    <p class="approval-profile-label">Quality profile</p>
    <p v-if="notice" class="approval-profile-notice" role="status">{{ notice }}</p>
    <div v-for="type in types" :key="type" class="approval-profile-row">
      <span class="badge badge-media">{{ type === 'movie' ? 'MOVIE' : 'TV' }}</span>
      <BaseDropdown :model-value="chosen[type].serverId ?? ''" :options="serverOptions(type)" label="Server" placeholder="Use Seer default" @update:model-value="setServer(type, $event)" />
      <template v-if="isChosen(chosen[type].serverId)">
        <BaseDropdown v-model="chosen[type].profileId" :options="profileOptions(type)" label="Quality profile" placeholder="Select quality profile" />
        <BaseDropdown v-model="chosen[type].rootFolder" :options="rootFolderOptions(type)" label="Root folder" placeholder="Select root folder" />
      </template>
    </div>
    <p v-if="types.length" class="approval-profile-hint">Leave the quality profile empty to use the profile the job or Jellyseerr would pick.</p>
  </div>
</template>

<script>
import BaseDropdown from '@/components/common/BaseDropdown.vue';
import { approvalProfileNotice, buildProfilePayload, choiceForServer, defaultChoice, isChosen, profileTypes } from '@/utils/requestProfiles.js';

// The server / quality profile / root folder choice shown while approving.
// The host owns the dialog and the servers; it asks `payload()` on confirm.
export default {
  name: 'ApprovalProfileChoice',
  components: { BaseDropdown },
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

<style scoped>
.approval-profile-choice{display:grid;gap:var(--spacing-sm);margin-top:var(--spacing-lg)}
.approval-profile-label{margin:0;color:var(--color-text-muted);font-size:var(--font-size-sm);font-weight:var(--font-weight-semibold);text-transform:uppercase}
.approval-profile-row{display:grid;grid-template-columns:auto repeat(3,minmax(0,1fr));align-items:end;gap:var(--spacing-sm)}
.approval-profile-row>.badge{align-self:center}
.approval-profile-hint{margin:0;color:var(--color-text-muted);font-size:var(--font-size-sm)}
.approval-profile-notice{margin:0;color:var(--color-warning);font-size:var(--font-size-sm)}
@media(max-width:768px){.approval-profile-row{grid-template-columns:1fr}}
</style>
