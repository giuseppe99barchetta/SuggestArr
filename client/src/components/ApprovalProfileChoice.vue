<template>
  <div v-if="types.length" class="approval-profile-choice">
    <p class="approval-profile-label">Quality profile</p>
    <div v-for="type in types" :key="type" class="approval-profile-row">
      <span class="badge badge-media">{{ type === 'movie' ? 'MOVIE' : 'TV' }}</span>
      <BaseDropdown :model-value="chosen[type].serverId ?? ''" :options="serverOptions(type)" label="Server" placeholder="Use Seer default" @update:model-value="setServer(type, $event)" />
      <template v-if="isChosen(chosen[type].serverId)">
        <BaseDropdown v-model="chosen[type].profileId" :options="profileOptions(type)" label="Quality profile" placeholder="Select quality profile" />
        <BaseDropdown v-model="chosen[type].rootFolder" :options="rootFolderOptions(type)" label="Root folder" placeholder="Select root folder" />
      </template>
    </div>
    <p class="approval-profile-hint">Leave the server empty to use the profile the job or Jellyseerr would pick.</p>
  </div>
</template>

<script>
import BaseDropdown from '@/components/common/BaseDropdown.vue';
import { buildProfilePayload, isChosen, profileTypes } from '@/utils/requestProfiles.js';

// The server / quality profile / root folder choice shown while approving.
// The host owns the dialog and the servers; it asks `payload()` on confirm.
export default {
  name: 'ApprovalProfileChoice',
  components: { BaseDropdown },
  props: {
    servers: { type: Object, required: true },
    mediaTypes: { type: Array, default: () => [] }
  },
  data() { return { chosen: { movie: {}, tv: {} } }; },
  computed: {
    types() { return profileTypes(this.mediaTypes, this.servers); }
  },
  watch: {
    mediaTypes() { this.chosen = { movie: {}, tv: {} }; }
  },
  methods: {
    isChosen,
    serversFor(type) { return (this.servers || {})[type] || []; },
    selectedServer(type) { return this.serversFor(type).find(server => String(server.id) === String(this.chosen[type].serverId)); },
    serverOptions(type) { return this.serversFor(type).map(server => ({ value: server.id, label: `${server.name}${server.is4k ? ' (4K)' : ''}` })); },
    profileOptions(type) { return (this.selectedServer(type)?.profiles || []).map(profile => ({ value: profile.id, label: profile.name })); },
    rootFolderOptions(type) { return (this.selectedServer(type)?.rootFolders || []).map(folder => ({ value: folder.path, label: folder.path })); },
    setServer(type, serverId) {
      const server = this.serversFor(type).find(item => String(item.id) === String(serverId));
      // is4k and the language profile follow from the server, so they are read
      // off it rather than asked for — same as the job dialog does.
      this.chosen[type] = { serverId, profileId: '', rootFolder: '', is4k: server?.is4k === true, languageProfileId: server?.activeLanguageProfileId ?? '' };
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
@media(max-width:768px){.approval-profile-row{grid-template-columns:1fr}}
</style>
