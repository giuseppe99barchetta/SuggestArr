<template>
  <div class="flex flex-col gap-4">
    <p class="m-0 text-[0.85rem] leading-normal text-ink-4">
      {{ subtitle }}
    </p>

    <!-- App credentials not configured -->
    <p v-if="!traktAppConfigured" :class="emptyClass">
      <i aria-hidden="true" class="fas fa-info-circle"></i>
      {{ credentialsMissingMessage }}
    </p>

    <template v-else>
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
            <span v-if="isSelfMode" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-ctl bg-raised text-ink-2"><i aria-hidden="true" class="icon-trakt"></i></span>
            <i v-else aria-hidden="true" class="fas fa-user text-[0.9rem] text-ink-3 opacity-60"></i>
            <div class="flex min-w-0 flex-col">
              <span class="truncate text-[0.9rem] font-semibold text-ink" :class="{ 'font-bold': isSelfMode }">{{ isSelfMode ? 'Trakt' : (user.external_username || user.external_user_id) }}</span>
              <span class="text-xs" :class="user.trakt?.connected ? 'text-ink-3' : 'text-ink-4'"><i v-if="user.trakt?.connected" aria-hidden="true" class="fas fa-check-circle mr-1 text-good"></i>{{ statusLabel(user) }}</span>
            </div>
          </div>

          <div class="flex shrink-0 items-center gap-2 max-md:w-full max-md:justify-end">
            <button
              type="button"
              class="ui-btn h-9"
              :disabled="isBusy(user)"
              @click="connectUser(user)"
            >
              <i aria-hidden="true" :class="isBusy(user) ? 'fas fa-spinner fa-spin' : 'fas fa-link'"></i>
              {{ connectLabel(user) }}
            </button>
            <ActionMenu
              v-if="user.trakt && user.trakt.connected"
              :label="`More Trakt actions for ${user.external_username || user.external_user_id}`"
              :items="[{ label: 'Unlink Trakt', icon: 'fas fa-unlink', danger: true, onSelect: () => unlinkUser(user) }]"
            />
          </div>
        </li>
      </ul>

      <div v-if="connectedTraktUsers.length > 0" class="rounded-ctl border border-edge bg-white/3">
        <button
          type="button"
          class="flex w-full cursor-pointer items-center gap-2 border-0 bg-transparent p-4 text-left text-sm font-semibold text-ink"
          :aria-expanded="previewExpanded.toString()"
          @click="togglePreviewPanel"
        >
          <i aria-hidden="true" class="fas fa-chevron-right text-ink-4 transition-transform" :class="{ 'rotate-90': previewExpanded }"></i>
          <span>Recent Trakt activity</span>
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
              v-for="user in connectedTraktUsers"
              :key="rowKey(user)"
              :value="rowKey(user)"
            >
              {{ user.external_username || user.external_user_id }}
            </option>
          </select>

          <p v-if="previewLoading" :class="emptyClass">
            <i aria-hidden="true" class="fas fa-spinner fa-spin"></i>
            Loading recent Trakt items...
          </p>

          <p v-else-if="previewError" class="ui-alert-bad flex items-center gap-2" role="alert">
            <i aria-hidden="true" class="fas fa-exclamation-triangle text-bad"></i>
            {{ previewError }}
          </p>

          <p v-else-if="previewItems.length === 0 && previewFetched" :class="emptyClass">
            <i aria-hidden="true" class="fas fa-inbox"></i>
            No recent Trakt items returned.
          </p>

          <ul v-else-if="previewItems.length > 0" class="m-0 flex list-none flex-col gap-2 p-0">
            <li v-for="item in previewItems" :key="previewItemKey(item)" class="rounded-ctl border border-edge bg-white/3 px-4 py-2">
              <div class="flex min-w-0 items-center gap-2 text-sm font-semibold text-ink">
                <i aria-hidden="true" :class="item.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
                <span class="min-w-0">{{ item.title || 'Untitled' }}</span>
                <span v-if="item.year" class="text-xs font-normal text-ink-4">({{ item.year }})</span>
              </div>
              <div class="flex min-w-0 items-center gap-2 text-xs text-ink-4">
                <span>{{ item.media_type === 'movie' ? 'Movie' : 'TV' }}</span>
                <span v-if="item.tmdb_id">TMDb {{ item.tmdb_id }}</span>
                <span v-if="item.watched_at">{{ formatPreviewDate(item.watched_at) }}</span>
              </div>
            </li>
          </ul>
        </div>
      </div>

      <!-- Active device-code prompt -->
      <div v-if="traktUserCode" class="break-all rounded-ctl border border-good/20 bg-good/10 px-4 py-3 text-[0.9rem] leading-relaxed text-good">
        <i aria-hidden="true" class="fas fa-key mr-1.5"></i>
        Enter <strong>{{ traktUserCode }}</strong> at
        <a :href="traktVerificationUrl" target="_blank" rel="noopener noreferrer" class="text-brand-ink no-underline hover:underline">{{ traktVerificationUrl }}</a>
        <p v-if="traktPopupBlocked" :class="[emptyClass, 'mt-3']">
          <i aria-hidden="true" class="fas fa-exclamation-circle"></i>
          Pop-up blocked. Open the link above manually to authorize.
        </p>
      </div>
      <p v-if="actionError" class="ui-alert-bad flex items-center gap-2" role="alert">
        <i aria-hidden="true" class="fas fa-exclamation-triangle text-bad"></i>
        {{ actionError }}
      </p>
    </template>

    <AppDialog v-if="showUnlinkConfirm" title="Unlink Trakt account" icon="icon-trakt" tone="danger" @close="cancelUnlink">
      <p class="m-0 text-sm leading-relaxed text-ink-2">
        Unlink the Trakt account for <strong class="text-ink">{{ unlinkTargetLabel }}</strong>? Its seeds and watch history stop feeding recommendation runs.
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
  listTraktMediaUsers,
  getMyTraktStatus,
  startMediaUserTraktDeviceCode,
  pollMediaUserTraktDeviceToken,
  unlinkMediaUserTrakt,
  previewMediaUserTraktRecent,
  startMyTraktDeviceCode,
  pollMyTraktDeviceToken,
  unlinkMyTrakt,
  previewMyTraktRecent,
} from '@/api/api';
import traktDevicePolling from './mixins/traktDevicePolling';
import ActionMenu from '@/components/ui/ActionMenu.vue';
import AppDialog from '@/components/ui/AppDialog.vue';

export default {
  name: 'TraktMediaUsers',
  components: { ActionMenu, AppDialog },
  mixins: [traktDevicePolling],
  props: {
    config: Object,
    mode: {
      type: String,
      default: 'admin',
      validator: value => ['admin', 'self'].includes(value),
    },
    traktConfigured: {
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
      isConnecting: {},
      isUnlinking: {},
      activeTarget: null,
      showUnlinkConfirm: false,
      unlinkTargetKey: '',
      unlinkTargetLabel: '',
      traktPopupBlocked: false,
      previewExpanded: false,
      previewTargetKey: '',
      previewItems: [],
      previewLoading: false,
      previewError: null,
      previewFetched: false,
      emptyClass: 'm-0 flex items-center gap-2 rounded-ctl bg-white/3 p-3 text-[0.85rem] text-ink-4',
    };
  },
  computed: {
    isSelfMode() {
      return this.mode === 'self';
    },
    traktAppConfigured() {
      if (this.traktConfigured !== null) return this.traktConfigured;
      return !!this.config?.TRAKT_CLIENT_ID;
    },
    subtitle() {
      if (this.isSelfMode) {
        return 'Recent Trakt watches seed your suggestions, and titles you already watched are skipped.';
      }
      return 'Link a Trakt account to each media-server user. Linked accounts add recent watches as recommendation seeds and contribute watched history to the skip-watched set during that user\'s run.';
    },
    emptyUsersMessage() {
      if (this.isSelfMode) return 'Link your media server account first.';
      return 'No media users selected. Choose users in the Services configuration first.';
    },
    credentialsMissingMessage() {
      if (this.isSelfMode) {
        return 'Trakt app credentials are not configured. Ask an admin to set the Trakt Client ID in Connections.';
      }
      return 'Trakt app credentials are not configured. Set the Trakt Client ID in Connections before linking accounts.';
    },
    connectedTraktUsers() {
      return this.mediaUsers.filter(user => user.trakt && user.trakt.connected);
    },
    previewTargetUser() {
      return this.connectedTraktUsers.find(user => this.rowKey(user) === this.previewTargetKey) || null;
    },
  },
  watch: {
    traktAppConfigured: {
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
    rowKey(user) {
      return `${user.provider}:${user.external_user_id}`;
    },
    isBusy(user) {
      return !!this.isConnecting[this.rowKey(user)] || (this.isPollingTrakt && this.activeTarget === this.rowKey(user));
    },
    connectLabel(user) {
      if (this.isPollingTrakt && this.activeTarget === this.rowKey(user)) return 'Waiting for Trakt…';
      return user.trakt && user.trakt.connected ? 'Re-link' : 'Link Trakt';
    },
    statusLabel(user) {
      const t = user.trakt || {};
      if (t.connected) return `Linked as ${t.trakt_username || 'Trakt user'}`;
      if (t.status === 'expired' || t.status === 'error' || t.status === 'revoked') {
        return t.last_error ? `Needs re-link — ${t.last_error}` : 'Needs re-link';
      }
      return 'Not linked';
    },
    async loadMediaUsers() {
      this.isLoadingUsers = true;
      this.loadError = null;
      try {
        if (this.isSelfMode) {
          const res = await getMyTraktStatus();
          this.mediaUsers = res.data?.media_user ? [res.data.media_user] : [];
        } else {
          const res = await listTraktMediaUsers();
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
      this.activeTarget = key;
      this.isConnecting = { ...this.isConnecting, [key]: true };
      this.traktPopupBlocked = false;
      try {
        const started = await this.startTraktPolling({
          requestCode: () => this.isSelfMode
            ? startMyTraktDeviceCode()
            : startMediaUserTraktDeviceCode(user.provider, user.external_user_id),
          pollToken: (deviceCode) => this.isSelfMode
            ? pollMyTraktDeviceToken(deviceCode)
            : pollMediaUserTraktDeviceToken(user.provider, user.external_user_id, deviceCode),
          onConnected: async (data) => {
            await this.loadMediaUsers();
            this.$toast.success(`Trakt linked for ${user.external_username || user.external_user_id} as ${data.trakt_username || 'Trakt user'}`);
          },
          setError: (message) => { this.actionError = message; },
          onPopupBlocked: () => { this.traktPopupBlocked = true; },
          windowName: 'trakt-oauth',
        });
        if (!started) {
          this.traktPopupBlocked = true;
        }
      } finally {
        this.isConnecting = { ...this.isConnecting, [key]: false };
      }
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
          await unlinkMyTrakt();
        } else {
          const [provider, externalUserId] = key.split(':');
          await unlinkMediaUserTrakt(provider, externalUserId);
        }
        await this.loadMediaUsers();
        this.$toast.success(`Trakt unlinked for ${label}`);
      } catch (err) {
        this.$toast.error(err.response?.data?.message || 'Failed to unlink Trakt');
      } finally {
        this.isUnlinking = { ...this.isUnlinking, [key]: false };
        this.cancelUnlink();
      }
    },
    ensurePreviewTarget() {
      if (!this.connectedTraktUsers.length) {
        this.resetPreview();
        return;
      }
      if (!this.previewTargetUser) {
        this.previewTargetKey = this.rowKey(this.connectedTraktUsers[0]);
      }
    },
    resetPreview() {
      this.previewTargetKey = '';
      this.clearPreviewItems();
    },
    clearPreviewItems() {
      this.previewItems = [];
      this.previewError = null;
      this.previewFetched = false;
    },
    togglePreviewPanel() {
      this.previewExpanded = !this.previewExpanded;
      if (this.previewExpanded) {
        this.ensurePreviewTarget();
        this.loadPreviewItems();
      }
    },
    async loadPreviewItems() {
      const user = this.previewTargetUser;
      if (!user) return;
      this.previewLoading = true;
      this.previewError = null;
      this.previewFetched = false;
      try {
        const res = this.isSelfMode
          ? await previewMyTraktRecent(10)
          : await previewMediaUserTraktRecent(user.provider, user.external_user_id, 10);
        this.previewItems = res.data?.items || [];
        this.previewFetched = true;
      } catch (err) {
        this.previewItems = [];
        this.previewFetched = true;
        this.previewError = err.response?.data?.message || 'Failed to fetch recent Trakt items';
      } finally {
        this.previewLoading = false;
      }
    },
    previewItemKey(item) {
      return `${item.media_type || 'unknown'}:${item.tmdb_id || item.title}:${item.watched_at || ''}`;
    },
    formatPreviewDate(ts) {
      const date = new Date(Number(ts) * 1000);
      if (Number.isNaN(date.getTime())) return '';
      return date.toLocaleDateString();
    },
  },
};
</script>
