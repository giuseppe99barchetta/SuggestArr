<template>
  <div class="settings-section" :class="{ 'settings-section--embedded': embedded }">
    <div class="settings-group" :class="{ 'settings-group--embedded': embedded }">
      <h2 v-if="!embedded" class="settings-group-title">
        <i class="fas fa-tv"></i>
        Trakt — Media Users
      </h2>
      <p class="settings-group-subtitle">
        Link a Trakt account to each media-server user. Linked accounts add recent
        watches as recommendation seeds and contribute watched history to the
        skip-watched set during that user's run.
      </p>

      <!-- App credentials not configured -->
      <div v-if="!traktAppConfigured" class="list-empty">
        <i class="fas fa-info-circle"></i>
        Trakt app credentials are not configured. Set the Trakt Client ID and Secret
        under Services before linking accounts.
      </div>

      <div v-else>
        <div v-if="loadError" class="error-banner" role="alert">
          <i class="fas fa-exclamation-triangle"></i>
          {{ loadError }}
        </div>

        <div v-if="isLoadingUsers" class="list-empty">
          <i class="fas fa-spinner fa-spin"></i> Loading media users…
        </div>

        <div v-else-if="mediaUsers.length === 0" class="list-empty">
          <i class="fas fa-users-slash"></i>
          No media users selected. Choose users in the Services configuration first.
        </div>

        <ul v-else class="user-list">
          <li v-for="user in mediaUsers" :key="rowKey(user)" class="user-row">
            <div class="user-info">
              <i class="fas fa-user"></i>
              <div class="user-text">
                <span class="user-name">{{ user.external_username || user.external_user_id }}</span>
                <span class="user-meta">{{ statusLabel(user) }}</span>
              </div>
            </div>

            <div class="user-actions">
              <button
                v-if="user.trakt && user.trakt.connected"
                class="btn btn-danger btn-sm icon-btn"
                :disabled="isUnlinking[rowKey(user)]"
                title="Unlink Trakt"
                @click="unlinkUser(user)"
              >
                <i :class="isUnlinking[rowKey(user)] ? 'fas fa-spinner fa-spin' : 'fas fa-unlink'"></i>
              </button>
              <button
                class="btn btn-outline btn-sm"
                :disabled="isBusy(user)"
                @click="connectUser(user)"
              >
                <i :class="isBusy(user) ? 'fas fa-spinner fa-spin' : 'fas fa-link'"></i>
                {{ connectLabel(user) }}
              </button>
            </div>
          </li>
        </ul>

        <div v-if="connectedTraktUsers.length > 0" class="trakt-preview-panel">
          <button
            type="button"
            class="collapsible-toggle"
            @click="togglePreviewPanel"
          >
            <i class="fas fa-chevron-right toggle-arrow" :class="{ expanded: previewExpanded }"></i>
            <span>Recent Trakt Preview</span>
          </button>

          <div v-show="previewExpanded" class="trakt-preview-content">
            <div class="trakt-preview-controls">
              <select v-model="previewTargetKey" class="form-control" :disabled="previewLoading" @change="clearPreviewItems">
                <option
                  v-for="user in connectedTraktUsers"
                  :key="rowKey(user)"
                  :value="rowKey(user)"
                >
                  {{ user.external_username || user.external_user_id }}
                </option>
              </select>
              <button
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="previewLoading || !previewTargetUser"
                @click="loadPreviewItems"
              >
                <i :class="previewLoading ? 'fas fa-spinner fa-spin' : 'fas fa-vial'"></i>
                {{ previewLoading ? 'Fetching...' : 'Test Fetch' }}
              </button>
            </div>

            <div v-if="previewError" class="error-banner" role="alert">
              <i class="fas fa-exclamation-triangle"></i>
              {{ previewError }}
            </div>

            <div v-else-if="previewItems.length === 0 && previewFetched" class="list-empty">
              <i class="fas fa-inbox"></i>
              No recent Trakt items returned.
            </div>

            <ul v-else-if="previewItems.length > 0" class="preview-list">
              <li v-for="item in previewItems" :key="previewItemKey(item)" class="preview-row">
                <div class="preview-title">
                  <i :class="item.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
                  <span>{{ item.title || 'Untitled' }}</span>
                  <span v-if="item.year" class="preview-year">({{ item.year }})</span>
                </div>
                <div class="preview-meta">
                  <span>{{ item.media_type === 'movie' ? 'Movie' : 'TV' }}</span>
                  <span v-if="item.tmdb_id">TMDb {{ item.tmdb_id }}</span>
                  <span v-if="item.watched_at">{{ formatPreviewDate(item.watched_at) }}</span>
                </div>
              </li>
            </ul>
          </div>
        </div>

        <!-- Active device-code prompt -->
        <div v-if="traktUserCode" class="oauth-success">
          <i class="fas fa-key"></i>
          Enter <strong>{{ traktUserCode }}</strong> at
          <a :href="traktVerificationUrl" target="_blank" rel="noopener noreferrer" class="link">{{ traktVerificationUrl }}</a>
          <p v-if="traktPopupBlocked" class="list-empty popup-blocked-hint">
            <i class="fas fa-exclamation-circle"></i>
            Pop-up blocked. Open the link above manually to authorize.
          </p>
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
          <h3>Unlink Trakt Account</h3>
          <p>
            Are you sure you want to unlink the Trakt account for
            <strong>{{ unlinkTargetLabel }}</strong>? This will remove their seed
            and watched-history data from recommendation runs.
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
  listTraktMediaUsers,
  startMediaUserTraktDeviceCode,
  pollMediaUserTraktDeviceToken,
  unlinkMediaUserTrakt,
  previewMediaUserTraktRecent,
} from '@/api/api';
import traktDevicePolling from './mixins/traktDevicePolling';

export default {
  name: 'TraktMediaUsers',
  mixins: [traktDevicePolling],
  props: {
    config: Object,
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
    };
  },
  computed: {
    traktAppConfigured() {
      return !!(this.config?.TRAKT_CLIENT_ID && this.config?.TRAKT_CLIENT_SECRET);
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
        const res = await listTraktMediaUsers();
        this.mediaUsers = res.data?.media_users || [];
        this.ensurePreviewTarget();
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
          requestCode: () => startMediaUserTraktDeviceCode(user.provider, user.external_user_id),
          pollToken: (deviceCode) => pollMediaUserTraktDeviceToken(user.provider, user.external_user_id, deviceCode),
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
        const [provider, externalUserId] = key.split(':');
        await unlinkMediaUserTrakt(provider, externalUserId);
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
      }
    },
    async loadPreviewItems() {
      const user = this.previewTargetUser;
      if (!user) return;
      this.previewLoading = true;
      this.previewError = null;
      this.previewFetched = false;
      try {
        const res = await previewMediaUserTraktRecent(user.provider, user.external_user_id, 10);
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
}

.user-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.trakt-preview-panel {
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

.trakt-preview-content {
  padding: 0 var(--spacing-md) var(--spacing-md);
}

.trakt-preview-controls {
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
  word-break: break-all;
}

.oauth-success i {
  margin-right: 0.35rem;
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

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.popup-blocked-hint {
  margin-top: 0.75rem;
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
  .trakt-preview-controls {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
