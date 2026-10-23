<template>
  <div class="flex flex-col gap-4">
    <p class="m-0 text-[0.85rem] leading-normal text-ink-4">
      {{ subtitle }}
    </p>

    <!-- Client ID not configured. The routes read it from config and reject
         credentials in the request body, so there is nothing to link with. -->
    <p v-if="!simklAppConfigured" :class="emptyClass">
      <i aria-hidden="true" class="fas fa-info-circle"></i>
      {{ credentialsMissingMessage }}
    </p>

    <template v-else>
      <!-- Install-level failure: the client ID itself was rejected. Shown
           above the user list because no individual link is at fault. -->
      <p v-if="clientIdError" class="ui-alert-bad flex items-center gap-2" role="alert">
        <i aria-hidden="true" class="fas fa-plug-circle-xmark text-bad"></i>
        <span>
          Simkl rejected this client ID — it may be wrong, suspended, or over its
          request limit. Check the app at
          <a href="https://simkl.com/settings/developer/" target="_blank" rel="noopener noreferrer" class="text-brand-ink no-underline hover:underline">simkl.com developer settings</a>.
        </span>
      </p>

      <p v-if="loadError" class="ui-alert-bad flex items-center gap-2" role="alert">
        <i aria-hidden="true" class="fas fa-exclamation-triangle text-bad"></i>
        {{ loadError }}
      </p>

      <p v-if="isLoadingUsers" :class="emptyClass">
        <i aria-hidden="true" class="fas fa-spinner fa-spin"></i> Loading media users…
      </p>

      <p v-else-if="mediaUsers.length === 0" :class="emptyClass">
        <i aria-hidden="true" class="fas fa-users-slash"></i>
        {{ emptyUsersMessage }}
      </p>

      <ul v-else class="m-0 flex list-none flex-col gap-2 p-0">
        <li v-for="user in mediaUsers" :key="rowKey(user)" class="flex flex-wrap items-center justify-between gap-3 rounded-ctl border border-edge bg-white/3 px-4 py-3 transition-colors hover:border-edge-strong max-md:flex-col max-md:items-start">
          <div class="flex min-w-0 flex-1 items-center gap-2.5">
            <span v-if="isSelfMode" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-ctl bg-raised text-ink-2"><i aria-hidden="true" class="icon-simkl"></i></span>
            <i v-else aria-hidden="true" class="fas fa-user text-[0.9rem] text-ink-3 opacity-60"></i>
            <div class="flex min-w-0 flex-col">
              <span class="truncate text-[0.9rem] font-semibold text-ink" :class="{ 'font-bold': isSelfMode }">{{ isSelfMode ? 'Simkl' : (user.external_username || user.external_user_id) }}</span>
              <span class="text-xs" :class="needsReauth(user) ? 'text-caution' : (user.simkl?.connected ? 'text-ink-3' : 'text-ink-4')">
                <i v-if="needsReauth(user)" aria-hidden="true" class="fas fa-triangle-exclamation mr-1"></i>
                <i v-else-if="user.simkl?.connected" aria-hidden="true" class="fas fa-check-circle mr-1 text-good"></i>{{ statusLabel(user) }}
              </span>
            </div>
          </div>

          <div class="flex shrink-0 items-center gap-2 max-md:w-full max-md:justify-end">
            <button
              type="button"
              class="ui-btn h-9"
              :class="{ 'border-caution text-caution': needsReauth(user) }"
              :disabled="isBusy(user)"
              @click="connectUser(user)"
            >
              <i aria-hidden="true" :class="isBusy(user) ? 'fas fa-spinner fa-spin' : 'fas fa-link'"></i>
              {{ connectLabel(user) }}
            </button>
            <ActionMenu
              v-if="user.simkl && user.simkl.connected"
              :label="`More Simkl actions for ${user.external_username || user.external_user_id}`"
              :items="[{ label: 'Unlink Simkl', icon: 'fas fa-unlink', danger: true, onSelect: () => unlinkUser(user) }]"
            />
          </div>
        </li>
      </ul>

      <div v-if="connectedSimklUsers.length > 0" class="rounded-ctl border border-edge bg-white/3">
        <button
          type="button"
          class="flex w-full cursor-pointer items-center gap-2 border-0 bg-transparent p-4 text-left text-sm font-semibold text-ink"
          :aria-expanded="previewExpanded.toString()"
          @click="togglePreviewPanel"
        >
          <i aria-hidden="true" class="fas fa-chevron-right text-ink-4 transition-transform" :class="{ 'rotate-90': previewExpanded }"></i>
          <span>Recent Simkl activity</span>
          <i aria-hidden="true" v-if="previewLoading" class="fas fa-spinner fa-spin ml-auto text-ink-4"></i>
        </button>

        <div v-show="previewExpanded" class="flex flex-col gap-4 px-4 pb-4">
          <select
            v-if="!isSelfMode"
            v-model="previewTargetKey"
            class="ui-input"
            :disabled="previewLoading"
            @change="loadPreviewItems"
          >
            <option
              v-for="user in connectedSimklUsers"
              :key="rowKey(user)"
              :value="rowKey(user)"
            >
              {{ user.external_username || user.external_user_id }}
            </option>
          </select>

          <p v-if="previewLoading" :class="emptyClass">
            <i aria-hidden="true" class="fas fa-spinner fa-spin"></i>
            Loading recent Simkl items...
          </p>

          <p v-else-if="previewError" class="ui-alert-bad flex items-center gap-2" role="alert">
            <i aria-hidden="true" class="fas fa-exclamation-triangle text-bad"></i>
            {{ previewError }}
          </p>

          <!-- The preview reads a local cache that the first sync fills, so a
               freshly linked account is empty for reasons that have nothing
               to do with the user's library. -->
          <p v-else-if="previewItems.length === 0 && previewFetched && !initialSyncComplete" :class="emptyClass">
            <i aria-hidden="true" class="fas fa-rotate fa-spin"></i>
            Syncing your Simkl library — this can take a moment on the first run.
          </p>

          <p v-else-if="previewItems.length === 0 && previewFetched" :class="emptyClass">
            <i aria-hidden="true" class="fas fa-inbox"></i>
            No watch history found on this Simkl account.
          </p>

          <ul v-else-if="previewItems.length > 0" class="m-0 flex list-none flex-col gap-2 p-0">
            <li v-for="item in previewItems" :key="previewItemKey(item)" class="rounded-ctl border border-edge bg-white/3 px-4 py-2">
              <div class="flex min-w-0 items-center gap-2 text-sm font-semibold text-ink">
                <i aria-hidden="true" :class="mediaIcon(item.media_type)"></i>
                <span class="min-w-0">{{ item.title || 'Untitled' }}</span>
                <span v-if="item.year" class="text-xs font-normal text-ink-4">({{ item.year }})</span>
              </div>
              <div class="flex min-w-0 items-center gap-2 text-xs text-ink-4">
                <span>{{ mediaLabel(item.media_type) }}</span>
                <span v-if="item.tmdb_id">TMDb {{ item.tmdb_id }}</span>
                <span v-if="item.status === 'watching'">Watching</span>
                <span v-if="item.watched_at">{{ formatPreviewDate(item.watched_at) }}</span>
              </div>
            </li>
          </ul>
        </div>
      </div>

      <!-- Active device prompt. Simkl's destination is fixed, so the public
           code is shown to copy rather than handing the private code out. -->
      <div v-if="simklUserCode" class="flex flex-col gap-2 rounded-ctl border border-good/20 bg-good/10 px-4 py-3 text-[0.9rem] leading-relaxed text-good">
        <div class="flex flex-wrap items-center gap-2">
          <i aria-hidden="true" class="fas fa-key"></i>
          <span>Enter this PIN at</span>
          <a :href="simklVerificationUri" target="_blank" rel="noopener noreferrer" class="break-all text-brand-ink no-underline hover:underline">
            {{ displayVerificationUri }}
          </a>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <code class="rounded-ctl bg-raised px-2 py-1 font-mono text-xl font-bold tracking-[0.2em] text-ink">{{ simklUserCode }}</code>
          <button type="button" class="ui-btn h-9" @click="copyPin">
            <i aria-hidden="true" :class="pinCopied ? 'fas fa-check' : 'fas fa-copy'"></i>
            {{ pinCopied ? 'Copied' : 'Copy' }}
          </button>
          <button type="button" class="ui-btn h-9" @click="cancelPin">
            <i aria-hidden="true" class="fas fa-xmark"></i>
            Cancel
          </button>
        </div>
        <p class="m-0 text-xs text-ink-4">Waiting for you to authorize — this page updates on its own.</p>
      </div>

      <p v-if="actionError" class="ui-alert-bad flex items-center gap-2" role="alert">
        <i aria-hidden="true" class="fas fa-exclamation-triangle text-bad"></i>
        {{ actionError }}
      </p>
    </template>

    <AppDialog v-if="showUnlinkConfirm" title="Unlink Simkl account" icon="icon-simkl" tone="danger" @close="cancelUnlink">
      <p class="m-0 text-sm leading-relaxed text-ink-2">
        Unlink the Simkl account for <strong class="text-ink">{{ unlinkTargetLabel }}</strong>? Its seeds and watch history stop feeding recommendation runs.
      </p>
      <!-- AUTH V2 links are revoked by the backend when a refresh token is
           available; access-only legacy links still need manual removal. -->
      <p class="m-0 mt-3 text-xs leading-relaxed text-ink-4">
        <i aria-hidden="true" class="fas fa-circle-info mr-1"></i>
        This removes SuggestArr's copy of the token. Legacy links can be revoked at
        <a href="https://simkl.com/settings/connected-apps/" target="_blank" rel="noopener noreferrer" class="text-brand-ink no-underline hover:underline">simkl.com/settings/connected-apps</a>.
      </p>
      <template #footer>
        <button type="button" class="ui-btn" @click="cancelUnlink">Cancel</button>
        <button type="button" class="ui-btn-danger" :disabled="isUnlinking[unlinkTargetKey]" @click="confirmUnlink">
          <i v-if="isUnlinking[unlinkTargetKey]" aria-hidden="true" class="fas fa-spinner fa-spin"></i>Unlink
        </button>
      </template>
    </AppDialog>
  </div>
</template>

<script>
import {
  listSimklMediaUsers,
  getMySimklStatus,
  startMediaUserSimklPinCode,
  pollMediaUserSimklPinToken,
  cancelMediaUserSimklPin,
  unlinkMediaUserSimkl,
  previewMediaUserSimklRecent,
  startMySimklPinCode,
  pollMySimklPinToken,
  cancelMySimklPin,
  unlinkMySimkl,
  previewMySimklRecent,
} from '@/api/api';
import simklPinPolling from './mixins/simklPinPolling';
import { formatWatchedDate, previewLoaderMethods } from './simklPreview.js';
import { copyText } from '@/utils/clipboard';
import ActionMenu from '@/components/ui/ActionMenu.vue';
import AppDialog from '@/components/ui/AppDialog.vue';

// Statuses that mean the stored token can no longer be used and only a fresh
// PIN flow will fix it.
const REAUTH_STATUSES = ['needs_reauth', 'expired', 'revoked'];

export default {
  name: 'SimklMediaUsers',
  components: { ActionMenu, AppDialog },
  mixins: [simklPinPolling],
  props: {
    config: Object,
    mode: {
      type: String,
      default: 'admin',
      validator: value => ['admin', 'self'].includes(value),
    },
    simklConfigured: {
      type: Boolean,
      default: null,
    },
  },
  data() {
    return {
      mediaUsers: [],
      isLoadingUsers: false,
      loadError: null,
      actionError: null,
      clientIdError: false,
      isConnecting: {},
      isUnlinking: {},
      activeTarget: null,
      showUnlinkConfirm: false,
      unlinkTargetKey: '',
      unlinkTargetLabel: '',
      pinCopied: false,
      previewExpanded: false,
      previewTargetKey: '',
      previewItems: [],
      previewLoading: false,
      previewError: null,
      previewFetched: false,
      previewGeneration: 0,
      emptyClass: 'm-0 flex items-center gap-2 rounded-ctl bg-white/3 p-3 text-[0.85rem] text-ink-4',
    };
  },
  computed: {
    isSelfMode() {
      return this.mode === 'self';
    },
    simklAppConfigured() {
      if (this.simklConfigured !== null) return this.simklConfigured;
      return !!this.config?.SIMKL_CLIENT_ID;
    },
    subtitle() {
      if (this.isSelfMode) {
        return 'Recent Simkl watches seed your suggestions, and titles you already finished are skipped.';
      }
      return 'Link a Simkl account to each media-server user. Linked accounts add watch history as recommendation seeds and contribute completed titles to the skip-watched set during that user\'s run.';
    },
    emptyUsersMessage() {
      if (this.isSelfMode) return 'Link your media server account first.';
      return 'No media users selected. Choose users in the Connections configuration first.';
    },
    credentialsMissingMessage() {
      if (this.isSelfMode) {
        return 'Simkl is not configured. Ask an admin to set the Simkl Client ID in Connections.';
      }
      return 'Simkl is not configured. Set the Simkl Client ID in Connections before linking accounts.';
    },
    connectedSimklUsers() {
      return this.mediaUsers.filter(user => user.simkl && user.simkl.connected);
    },
    previewTargetUser() {
      return this.connectedSimklUsers.find(user => this.rowKey(user) === this.previewTargetKey) || null;
    },
    initialSyncComplete() {
      return this.previewTargetUser?.simkl?.initial_sync_complete !== false;
    },
    displayVerificationUri() {
      return this.simklVerificationUri.replace(/^https?:\/\//, '').replace(/\/$/, '');
    },
  },
  watch: {
    simklAppConfigured: {
      immediate: true,
      async handler(isConfigured) {
        if (isConfigured) {
          await this.loadMediaUsers();
        } else {
          this.mediaUsers = [];
          this.loadError = null;
          this.resetPreview();
        }
      },
    },
  },
  methods: {
    ...previewLoaderMethods,
    rowKey(user) {
      return `${user.provider}:${user.external_user_id}`;
    },
    isBusy(user) {
      return !!this.isConnecting[this.rowKey(user)] || (this.isPollingSimkl && this.activeTarget === this.rowKey(user));
    },
    needsReauth(user) {
      const s = user.simkl || {};
      return !s.connected && REAUTH_STATUSES.includes(s.status);
    },
    connectLabel(user) {
      if (this.isPollingSimkl && this.activeTarget === this.rowKey(user)) return 'Waiting for Simkl…';
      if (this.needsReauth(user)) return 'Re-link';
      return user.simkl && user.simkl.connected ? 'Re-link' : 'Link Simkl';
    },
    statusLabel(user) {
      const s = user.simkl || {};
      if (s.connected) return `Linked as ${s.simkl_username || 'Simkl user'}`;
      if (s.status === 'needs_reauth') {
        return s.last_error ? `Re-link required — ${s.last_error}` : 'Re-link required';
      }
      if (REAUTH_STATUSES.includes(s.status)) {
        return s.last_error ? `Needs re-link — ${s.last_error}` : 'Needs re-link';
      }
      return 'Not linked';
    },
    mediaIcon(mediaType) {
      if (mediaType === 'movie') return 'fas fa-film';
      if (mediaType === 'anime') return 'fas fa-dragon';
      return 'fas fa-tv';
    },
    mediaLabel(mediaType) {
      if (mediaType === 'movie') return 'Movie';
      if (mediaType === 'anime') return 'Anime';
      return 'TV';
    },
    /**
     * Route a failure to the install-level banner or the per-action one.
     *
     * A rejected client ID is not the fault of the user whose link request
     * happened to hit it, so showing it on their row would point at the wrong
     * remedy.
     */
    handleActionError(message, err) {
      if (err?.response?.data?.code === 'client_id_failed') {
        this.clientIdError = true;
        this.actionError = null;
        return;
      }
      this.actionError = message;
    },
    async loadMediaUsers() {
      this.isLoadingUsers = true;
      this.loadError = null;
      try {
        if (this.isSelfMode) {
          const res = await getMySimklStatus();
          this.mediaUsers = res.data?.media_user ? [res.data.media_user] : [];
        } else {
          const res = await listSimklMediaUsers();
          this.mediaUsers = res.data?.media_users || [];
        }
        this.ensurePreviewTarget();
        if (this.previewExpanded && this.previewTargetUser) {
          await this.loadPreviewItems();
        }
      } catch (err) {
        this.loadError = err.response?.data?.message || 'Failed to load media users';
        this.mediaUsers = [];
        this.resetPreview();
      } finally {
        this.isLoadingUsers = false;
      }
    },
    async connectUser(user) {
      const key = this.rowKey(user);
      this.actionError = null;
      this.clientIdError = false;
      this.pinCopied = false;
      this.activeTarget = key;
      this.isConnecting = { ...this.isConnecting, [key]: true };
      try {
        await this.startSimklPolling({
          requestCode: () => this.isSelfMode
            ? startMySimklPinCode()
            : startMediaUserSimklPinCode(user.provider, user.external_user_id),
          pollToken: () => this.isSelfMode
            ? pollMySimklPinToken()
            : pollMediaUserSimklPinToken(user.provider, user.external_user_id),
          cancelCode: () => this.isSelfMode
            ? cancelMySimklPin()
            : cancelMediaUserSimklPin(user.provider, user.external_user_id),
          onConnected: async (data) => {
            await this.loadMediaUsers();
            this.$toast.success(`Simkl linked for ${user.external_username || user.external_user_id} as ${data.simkl_username || 'Simkl user'}`);
          },
          setError: (message, err) => this.handleActionError(message, err),
        });
      } finally {
        this.isConnecting = { ...this.isConnecting, [key]: false };
      }
    },
    async copyPin() {
      // A refused copy needs no message: the code is on screen to type.
      if (await copyText(this.simklUserCode)) {
        this.pinCopied = true;
        setTimeout(() => { this.pinCopied = false; }, 2000);
      }
    },
    async cancelPin() {
      await this.cancelSimklPolling();
      this.activeTarget = null;
      this.pinCopied = false;
    },
    unlinkUser(user) {
      this.unlinkTargetKey = this.rowKey(user);
      this.unlinkTargetLabel = user.external_username || user.external_user_id;
      this.showUnlinkConfirm = true;
    },
    cancelUnlink() {
      this.showUnlinkConfirm = false;
      this.unlinkTargetKey = '';
      this.unlinkTargetLabel = '';
    },
    async confirmUnlink() {
      const key = this.unlinkTargetKey;
      const label = this.unlinkTargetLabel;
      this.isUnlinking = { ...this.isUnlinking, [key]: true };
      try {
        if (this.isSelfMode) {
          await unlinkMySimkl();
        } else {
          const [provider, externalUserId] = key.split(':');
          await unlinkMediaUserSimkl(provider, externalUserId);
        }
        await this.loadMediaUsers();
        this.$toast.success(`Simkl unlinked for ${label}`);
      } catch (err) {
        this.$toast.error(err.response?.data?.message || 'Failed to unlink Simkl');
      } finally {
        this.isUnlinking = { ...this.isUnlinking, [key]: false };
        this.cancelUnlink();
      }
    },
    ensurePreviewTarget() {
      if (!this.connectedSimklUsers.length) {
        this.resetPreview();
        return;
      }
      if (!this.previewTargetUser) {
        this.previewTargetKey = this.rowKey(this.connectedSimklUsers[0]);
      }
    },
    togglePreviewPanel() {
      this.previewExpanded = !this.previewExpanded;
      if (this.previewExpanded) {
        this.ensurePreviewTarget();
        this.loadPreviewItems();
      }
    },
    fetchPreview(user) {
      return this.isSelfMode
        ? previewMySimklRecent(10)
        : previewMediaUserSimklRecent(user.provider, user.external_user_id, 10);
    },
    previewItemKey(item) {
      return `${item.media_type || 'unknown'}:${item.tmdb_id || item.title}:${item.watched_at || ''}`;
    },
    formatPreviewDate(ts) {
      return formatWatchedDate(ts);
    },
  },
};
</script>
