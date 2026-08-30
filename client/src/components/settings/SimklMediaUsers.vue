<template>
  <div class="settings-section" :class="{ 'settings-section--embedded': embedded }">
    <div class="settings-group" :class="{ 'settings-group--embedded': embedded }">
      <h2 v-if="!embedded" class="settings-group-title">
        <i class="fas fa-check-double"></i>
        Simkl — Media Users
      </h2>
      <p class="settings-group-subtitle">
        {{ subtitle }}
      </p>

      <!-- Client ID not configured. The routes read it from config and reject
           credentials in the request body, so there is nothing to link with. -->
      <div v-if="!simklAppConfigured" class="list-empty">
        <i class="fas fa-info-circle"></i>
        {{ credentialsMissingMessage }}
      </div>

      <div v-else>
        <!-- Install-level failure: the client ID itself was rejected. Shown
             above the user list because no individual link is at fault. -->
        <div v-if="clientIdError" class="error-banner" role="alert">
          <i class="fas fa-plug-circle-xmark"></i>
          <span>
            Simkl rejected this client ID — it may be wrong, suspended, or over its
            request limit. Check the app at
            <a href="https://simkl.com/settings/developer/" target="_blank" rel="noopener noreferrer" class="link">simkl.com developer settings</a>.
          </span>
        </div>

        <div v-if="loadError" class="error-banner" role="alert">
          <i class="fas fa-exclamation-triangle"></i>
          {{ loadError }}
        </div>

        <div v-if="isLoadingUsers" class="list-empty">
          <i class="fas fa-spinner fa-spin"></i> Loading media users…
        </div>

        <div v-else-if="mediaUsers.length === 0" class="list-empty">
          <i class="fas fa-users-slash"></i>
          {{ emptyUsersMessage }}
        </div>

        <ul v-else class="user-list">
          <li v-for="user in mediaUsers" :key="rowKey(user)" class="user-row">
            <div class="user-info">
              <i class="fas fa-user"></i>
              <div class="user-text">
                <span class="user-name">{{ user.external_username || user.external_user_id }}</span>
                <span class="user-meta" :class="{ 'user-meta--warn': needsReauth(user) }">
                  <i v-if="needsReauth(user)" class="fas fa-triangle-exclamation"></i>
                  {{ statusLabel(user) }}
                </span>
              </div>
            </div>

            <div class="user-actions">
              <button
                v-if="user.simkl && user.simkl.connected"
                class="btn btn-danger btn-sm icon-btn"
                :disabled="isUnlinking[rowKey(user)]"
                title="Unlink Simkl"
                @click="unlinkUser(user)"
              >
                <i :class="isUnlinking[rowKey(user)] ? 'fas fa-spinner fa-spin' : 'fas fa-unlink'"></i>
              </button>
              <button
                class="btn btn-outline btn-sm"
                :class="{ 'btn-warn': needsReauth(user) }"
                :disabled="isBusy(user)"
                @click="connectUser(user)"
              >
                <i :class="isBusy(user) ? 'fas fa-spinner fa-spin' : 'fas fa-link'"></i>
                {{ connectLabel(user) }}
              </button>
            </div>
          </li>
        </ul>

        <div v-if="connectedSimklUsers.length > 0" class="simkl-preview-panel">
          <button
            type="button"
            class="collapsible-toggle"
            @click="togglePreviewPanel"
          >
            <i class="fas fa-chevron-right toggle-arrow" :class="{ expanded: previewExpanded }"></i>
            <span>Recent Simkl Preview</span>
            <i v-if="previewLoading" class="fas fa-spinner fa-spin preview-loading-icon"></i>
          </button>

          <div v-show="previewExpanded" class="simkl-preview-content">
            <div class="simkl-preview-controls">
              <select
                v-if="!isSelfMode"
                v-model="previewTargetKey"
                class="form-control"
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
            </div>

            <div v-if="previewLoading" class="list-empty">
              <i class="fas fa-spinner fa-spin"></i>
              Loading recent Simkl items...
            </div>

            <div v-else-if="previewError" class="error-banner" role="alert">
              <i class="fas fa-exclamation-triangle"></i>
              {{ previewError }}
            </div>

            <!-- The preview reads a local cache that the first sync fills, so a
                 freshly linked account is empty for reasons that have nothing
                 to do with the user's library. -->
            <div v-else-if="previewItems.length === 0 && previewFetched && !initialSyncComplete" class="list-empty">
              <i class="fas fa-rotate fa-spin"></i>
              Syncing your Simkl library — this can take a moment on the first run.
            </div>

            <div v-else-if="previewItems.length === 0 && previewFetched" class="list-empty">
              <i class="fas fa-inbox"></i>
              No watch history found on this Simkl account.
            </div>

            <ul v-else-if="previewItems.length > 0" class="preview-list">
              <li v-for="item in previewItems" :key="previewItemKey(item)" class="preview-row">
                <div class="preview-title">
                  <i :class="mediaIcon(item.media_type)"></i>
                  <span>{{ item.title || 'Untitled' }}</span>
                  <span v-if="item.year" class="preview-year">({{ item.year }})</span>
                </div>
                <div class="preview-meta">
                  <span>{{ mediaLabel(item.media_type) }}</span>
                  <span v-if="item.tmdb_id">TMDb {{ item.tmdb_id }}</span>
                  <span v-if="item.status === 'watching'">Watching</span>
                  <span v-if="item.watched_at">{{ formatPreviewDate(item.watched_at) }}</span>
                </div>
              </li>
            </ul>
          </div>
        </div>

        <!-- Active PIN prompt. Simkl's destination is fixed, so the code is
             shown to copy rather than handed to a popup. -->
        <div v-if="simklUserCode" class="oauth-success">
          <div class="pin-row">
            <i class="fas fa-key"></i>
            <span>Enter this PIN at</span>
            <a :href="simklVerificationUri" target="_blank" rel="noopener noreferrer" class="link">
              {{ displayVerificationUri }}
            </a>
          </div>
          <div class="pin-row">
            <code class="pin-code">{{ simklUserCode }}</code>
            <button type="button" class="btn btn-outline btn-sm" @click="copyPin">
              <i :class="pinCopied ? 'fas fa-check' : 'fas fa-copy'"></i>
              {{ pinCopied ? 'Copied' : 'Copy' }}
            </button>
            <button type="button" class="btn btn-outline btn-sm" @click="cancelPin">
              <i class="fas fa-xmark"></i>
              Cancel
            </button>
          </div>
          <p class="pin-hint">Waiting for you to authorize — this page updates on its own.</p>
        </div>

        <div v-if="actionError" class="error-banner" role="alert">
          <i class="fas fa-exclamation-triangle"></i>
          {{ actionError }}
        </div>
      </div>
    </div>

    <!-- Confirm unlink dialog -->
    <teleport to="body">
      <div v-if="showUnlinkConfirm" class="modal-overlay" @click.self="cancelUnlink">
        <div class="modal-box">
          <h3>Unlink Simkl Account</h3>
          <p>
            Are you sure you want to unlink the Simkl account for
            <strong>{{ unlinkTargetLabel }}</strong>? This removes their seed and
            watched-history data from recommendation runs.
          </p>
          <!-- Simkl publishes no revocation endpoint, so promising otherwise
               would be a claim the API cannot back. -->
          <p class="modal-note">
            <i class="fas fa-circle-info"></i>
            This removes SuggestArr's copy of the token. To revoke access at Simkl
            itself, remove SuggestArr at
            <a href="https://simkl.com/settings/connected-apps/" target="_blank" rel="noopener noreferrer" class="link">simkl.com/settings/connected-apps</a>.
          </p>
          <div class="modal-actions">
            <button class="btn btn-outline" @click="cancelUnlink">Cancel</button>
            <button class="btn btn-danger" @click="confirmUnlink" :disabled="isUnlinking[unlinkTargetKey]">
              <i v-if="isUnlinking[unlinkTargetKey]" class="fas fa-spinner fa-spin"></i>
              Unlink
            </button>
          </div>
        </div>
      </div>
    </teleport>
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
import { formatWatchedDate } from './simklPreview.js';

// Statuses that mean the stored token can no longer be used and only a fresh
// PIN flow will fix it.
const REAUTH_STATUSES = ['needs_reauth', 'expired', 'error', 'revoked'];

export default {
  name: 'SimklMediaUsers',
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
    embedded: {
      type: Boolean,
      default: false,
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
        return 'Link your Simkl account to your media-server profile. SuggestArr uses your watch history as recommendation seeds and to skip what you have already finished.';
      }
      return 'Link a Simkl account to each media-server user. Linked accounts add watch history as recommendation seeds and contribute completed titles to the skip-watched set during that user\'s run.';
    },
    emptyUsersMessage() {
      if (this.isSelfMode) return 'Link your media server account first.';
      return 'No media users selected. Choose users in the Services configuration first.';
    },
    credentialsMissingMessage() {
      if (this.isSelfMode) {
        return 'Simkl is not configured. Ask an admin to set the Simkl Client ID under Services.';
      }
      return 'Simkl is not configured. Set the Simkl Client ID under Services before linking accounts.';
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
      try {
        await navigator.clipboard.writeText(this.simklUserCode);
        this.pinCopied = true;
        setTimeout(() => { this.pinCopied = false; }, 2000);
      } catch {
        // Clipboard access can be denied; the code is on screen to type.
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
          ? await previewMySimklRecent(10)
          : await previewMediaUserSimklRecent(user.provider, user.external_user_id, 10);
        this.previewItems = res.data?.items || [];
        this.previewFetched = true;
      } catch (err) {
        this.previewItems = [];
        this.previewFetched = true;
        if (err.response?.data?.code === 'client_id_failed') {
          this.clientIdError = true;
        } else {
          this.previewError = err.response?.data?.message || 'Failed to fetch recent Simkl items';
        }
      } finally {
        this.previewLoading = false;
      }
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

<style scoped>
/* Shared with UserManagement / SettingsServices */
.settings-section {
  padding-bottom: 1.5rem;
}

.settings-section--embedded {
  padding-bottom: 0;
}

.settings-group {
  padding: 1.5rem 2rem;
  margin-bottom: 1.5rem;
  border: 1px solid var(--surface-glass-light);
  border-radius: var(--border-radius);
  background: var(--surface-glass-subtle);
}

.settings-group--embedded {
  padding: 0;
  margin-bottom: 0;
  border: 0;
  background: transparent;
}

.settings-group-title {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0 0 0.5rem 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.settings-group-title i {
  opacity: 0.7;
}

.settings-group-subtitle {
  font-size: 0.85rem;
  color: var(--color-text-muted);
  margin: 0 0 1.25rem 0;
  line-height: 1.5;
}

.list-empty {
  font-size: 0.85rem;
  color: var(--color-text-muted);
  margin: 0;
  padding: 0.75rem;
  background: var(--surface-glass-subtle);
  border-radius: var(--border-radius-sm);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.user-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.user-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--surface-glass-subtle);
  border: 1px solid var(--surface-glass-light);
  border-radius: var(--border-radius-sm);
  transition: border-color 0.15s ease;
}

.user-row:hover {
  border-color: var(--surface-interactive);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  min-width: 0;
  flex: 1;
}

.user-info > i {
  opacity: 0.6;
  color: var(--color-text-secondary);
  font-size: 0.9rem;
}

.user-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-weight: 600;
  color: var(--color-text-primary);
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-meta {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.user-meta--warn {
  color: var(--color-warning);
}

.user-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.btn-warn {
  border-color: var(--color-warning);
  color: var(--color-warning);
}

.simkl-preview-panel {
  margin-bottom: var(--spacing-md);
  border: 1px solid var(--surface-glass-light);
  border-radius: var(--radius-sm);
  background: var(--surface-glass-subtle);
}

.collapsible-toggle {
  width: 100%;
  padding: var(--spacing-md);
  border: 0;
  background: transparent;
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
  text-align: left;
}

.toggle-arrow {
  color: var(--color-text-muted);
  transition: transform var(--transition-fast);
}

.toggle-arrow.expanded {
  transform: rotate(90deg);
}

.preview-loading-icon {
  margin-left: auto;
  color: var(--color-text-muted);
}

.simkl-preview-content {
  padding: 0 var(--spacing-md) var(--spacing-md);
}

.simkl-preview-controls {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
  margin-bottom: var(--spacing-md);
}

.preview-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.preview-row {
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--surface-glass-light);
  border-radius: var(--radius-sm);
  background: var(--surface-glass-subtle);
}

.preview-title,
.preview-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  min-width: 0;
}

.preview-title {
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.preview-title span {
  min-width: 0;
}

.preview-year,
.preview-meta {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  font-weight: 400;
}

.error-banner {
  background: var(--color-error-alpha-10);
  border: 1px solid var(--color-error-alpha-20);
  color: var(--color-error);
  padding: 0.75rem 1rem;
  border-radius: var(--border-radius-sm);
  margin-bottom: 1rem;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.oauth-success {
  padding: 0.75rem 1rem;
  background: var(--color-success-alpha-10);
  border: 1px solid var(--color-success-alpha-20);
  border-radius: var(--border-radius-sm);
  color: var(--color-success);
  font-size: 0.9rem;
  margin-bottom: 1rem;
  line-height: 1.6;
}

.pin-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.pin-row + .pin-row {
  margin-top: 0.6rem;
}

.pin-code {
  font-family: var(--font-mono, monospace);
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: 0.2em;
  padding: 0.35rem 0.75rem;
  border-radius: var(--border-radius-sm);
  background: var(--surface-glass-light);
  color: var(--color-text-primary);
}

.pin-hint {
  margin: 0.6rem 0 0 0;
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.link {
  color: var(--color-primary);
  text-decoration: none;
}

.link:hover {
  text-decoration: underline;
}

/* Confirm dialog */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-box {
  background: var(--surface-primary);
  border: 1px solid var(--surface-glass-light);
  border-radius: var(--border-radius);
  padding: 1.5rem;
  max-width: 420px;
  width: 90%;
}

.modal-box h3 {
  margin: 0 0 0.75rem 0;
  color: var(--color-text-primary);
  font-size: 1.05rem;
}

.modal-box p {
  margin: 0 0 1.25rem 0;
  color: var(--color-text-secondary);
  font-size: 0.9rem;
  line-height: 1.5;
}

.modal-note {
  font-size: 0.82rem;
  color: var(--color-text-muted);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

@media (max-width: 768px) {
  .settings-group {
    padding: 1rem;
  }
  .user-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .user-actions {
    width: 100%;
    justify-content: flex-end;
  }
  .simkl-preview-controls {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
