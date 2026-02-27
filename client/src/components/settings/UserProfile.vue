<template>
  <div class="settings-users">
    <div class="section-header">
      <h2>My Profile</h2>
      <p>Update your account credentials and link your media server account.</p>
    </div>

    <div class="settings-grid">

      <!-- ── Account Information ─────────────────────────────────────────── -->
      <div class="settings-group accounts-group">
        <div class="group-title-row">
          <h3>
            <i class="fas fa-user-circle"></i>
            Account Information
          </h3>
        </div>

        <!-- Username -->
        <form @submit.prevent="saveUsername">
          <h4 class="subsection-title">Username</h4>
          <div class="form-group">
            <label for="newUsername">New username</label>
            <input
              id="newUsername"
              v-model="usernameForm.value"
              type="text"
              class="form-control"
              :placeholder="currentUser?.username || 'Current username'"
              maxlength="64"
              :disabled="isSavingUsername"
            />
          </div>
          <div v-if="usernameError" class="error-banner">
            <i class="fas fa-exclamation-circle"></i>
            {{ usernameError }}
          </div>
          <div v-if="usernameSuccess" class="success-banner">
            <i class="fas fa-check-circle"></i>
            {{ usernameSuccess }}
          </div>
          <button
            type="submit"
            class="btn btn-primary btn-sm"
            :disabled="isSavingUsername || !usernameForm.value.trim()"
          >
            <i :class="isSavingUsername ? 'fas fa-spinner fa-spin' : 'fas fa-save'"></i>
            {{ isSavingUsername ? 'Saving…' : 'Save Username' }}
          </button>
        </form>

        <div class="section-divider"></div>

        <!-- Password -->
        <form @submit.prevent="savePassword">
          <h4 class="subsection-title">Change Password</h4>
          <div class="form-group">
            <label for="currentPassword">Current password</label>
            <input
              id="currentPassword"
              v-model="passwordForm.current"
              type="password"
              class="form-control"
              placeholder="Current password"
              autocomplete="current-password"
              :disabled="isSavingPassword"
            />
          </div>
          <div class="form-group">
            <label for="newPassword">New password</label>
            <input
              id="newPassword"
              v-model="passwordForm.new"
              type="password"
              class="form-control"
              placeholder="At least 8 characters"
              autocomplete="new-password"
              :disabled="isSavingPassword"
            />
          </div>
          <div class="form-group">
            <label for="confirmPassword">Confirm new password</label>
            <input
              id="confirmPassword"
              v-model="passwordForm.confirm"
              type="password"
              class="form-control"
              placeholder="Repeat new password"
              autocomplete="new-password"
              :disabled="isSavingPassword"
            />
          </div>
          <div v-if="passwordError" class="error-banner">
            <i class="fas fa-exclamation-circle"></i>
            {{ passwordError }}
          </div>
          <div v-if="passwordSuccess" class="success-banner">
            <i class="fas fa-check-circle"></i>
            {{ passwordSuccess }}
          </div>
          <button
            type="submit"
            class="btn btn-primary btn-sm"
            :disabled="isSavingPassword || !passwordForm.current || !passwordForm.new || !passwordForm.confirm"
          >
            <i :class="isSavingPassword ? 'fas fa-spinner fa-spin' : 'fas fa-lock'"></i>
            {{ isSavingPassword ? 'Saving…' : 'Change Password' }}
          </button>
        </form>

      </div>

      <!-- ── Media Server Link ────────────────────────────────────────────── -->
      <div v-if="isLinkableService" class="settings-group">
        <h3>
          <i :class="providerIcon"></i>
          {{ providerLabel }} Account
        </h3>

        <p class="card-desc">
          Link your {{ providerLabel }} account so SuggestArr can personalise recommendations based on your watch history.
        </p>

        <!-- Already linked -->
        <div v-if="currentLink" class="user-row">
          <div class="user-identity">
            <div class="user-avatar">
              <i :class="providerIcon"></i>
            </div>
            <div class="user-info">
              <span class="user-name">{{ currentLink.external_username }}</span>
              <span class="user-meta">{{ providerLabel }} account</span>
            </div>
          </div>
          <button
            type="button"
            class="btn btn-danger btn-sm icon-btn"
            :disabled="isUnlinking"
            title="Unlink account"
            @click="unlinkAccount"
          >
            <i :class="isUnlinking ? 'fas fa-spinner fa-spin' : 'fas fa-unlink'"></i>
          </button>
        </div>

        <!-- Link form — Jellyfin / Emby (dropdown) -->
        <template v-else-if="selectedService !== 'plex'">
          <div v-if="isLoadingServerUsers" class="list-empty">
            <i class="fas fa-spinner fa-spin"></i>
            Loading {{ providerLabel }} users…
          </div>
          <div v-else-if="serverUsersError" class="error-banner">
            <i class="fas fa-exclamation-circle"></i>
            {{ serverUsersError }}
          </div>
          <template v-else>
            <div v-if="serverUsers.length === 0" class="list-empty">
              <i class="fas fa-users"></i>
              No users found on {{ providerLabel }}.
            </div>
            <div v-else class="form-group">
              <label for="serverUserSelect">Select your {{ providerLabel }} account</label>
              <select
                id="serverUserSelect"
                v-model="selectedServerUser"
                class="form-control"
                :disabled="isLinking"
              >
                <option value="" disabled>— choose an account —</option>
                <option
                  v-for="u in serverUsers"
                  :key="u.id"
                  :value="u"
                >
                  {{ u.name }}
                </option>
              </select>
            </div>
            <div v-if="linkError" class="error-banner">
              <i class="fas fa-exclamation-circle"></i>
              {{ linkError }}
            </div>
            <button
              type="button"
              class="btn btn-primary btn-sm"
              :disabled="isLinking || !selectedServerUser"
              @click="linkAccount"
            >
              <i :class="isLinking ? 'fas fa-spinner fa-spin' : 'fas fa-link'"></i>
              {{ isLinking ? 'Linking…' : 'Link Account' }}
            </button>
          </template>
        </template>

        <!-- Link form — Plex (OAuth) -->
        <template v-else>
          <div v-if="plexPolling" class="list-empty">
            <i class="fas fa-spinner fa-spin"></i>
            Waiting for Plex authorisation…
            <button type="button" class="btn btn-outline btn-sm" @click="cancelPlexOAuth">Cancel</button>
          </div>
          <template v-else>
            <div v-if="linkError" class="error-banner">
              <i class="fas fa-exclamation-circle"></i>
              {{ linkError }}
            </div>
            <button type="button" class="btn btn-primary btn-sm" :disabled="isLinking" @click="startPlexOAuth">
              <i :class="isLinking ? 'fas fa-spinner fa-spin' : 'fas fa-external-link-alt'"></i>
              {{ isLinking ? 'Starting…' : 'Link with Plex' }}
            </button>
          </template>
        </template>

      </div>

      <!-- No linkable service configured -->
      <div v-else-if="config && config.SELECTED_SERVICE !== undefined" class="settings-group">
        <h3>
          <i class="fas fa-plug"></i>
          Media Server
        </h3>
        <div class="list-empty">
          <i class="fas fa-info-circle"></i>
          No linkable media server is configured. An admin must configure Jellyfin, Emby, or Plex first.
        </div>
      </div>

    </div>
  </div>
</template>

<script>
import { useAuth } from '@/composables/useAuth';
import {
  getMyLinks,
  getMediaServerUsers,
  linkJellyfin,
  linkEmby,
  unlinkProvider,
  plexOAuthStart,
  plexOAuthPoll,
  updateMyProfile,
} from '@/api/api';

const PROVIDER_META = {
  jellyfin: { label: 'Jellyfin', icon: 'fas fa-server' },
  emby:     { label: 'Emby',     icon: 'fas fa-server' },
  plex:     { label: 'Plex',     icon: 'fas fa-play-circle' },
};

export default {
  name: 'UserProfile',

  props: {
    config: Object,
    isLoading: Boolean,
  },

  setup() {
    const { currentUser, accessToken } = useAuth();
    return { currentUser, accessToken };
  },

  data() {
    return {
      // Account form state
      usernameForm: { value: '' },
      passwordForm: { current: '', new: '', confirm: '' },
      isSavingUsername: false,
      isSavingPassword: false,
      usernameError: null,
      usernameSuccess: null,
      passwordError: null,
      passwordSuccess: null,

      // Linked accounts
      links: [],

      // Server user dropdown (Jellyfin / Emby)
      serverUsers: [],
      isLoadingServerUsers: false,
      serverUsersError: null,
      selectedServerUser: '',

      // Linking / unlinking state
      isLinking: false,
      isUnlinking: false,
      linkError: null,

      // Plex OAuth
      plexPolling: false,
      plexPinId: null,
      plexPollTimer: null,
    };
  },

  computed: {
    selectedService() {
      return (this.config?.SELECTED_SERVICE || '').toLowerCase();
    },

    isLinkableService() {
      return ['jellyfin', 'emby', 'plex'].includes(this.selectedService);
    },

    providerLabel() {
      return PROVIDER_META[this.selectedService]?.label || '';
    },

    providerIcon() {
      return PROVIDER_META[this.selectedService]?.icon || 'fas fa-server';
    },

    currentLink() {
      return this.links.find(l => l.provider === this.selectedService) || null;
    },
  },

  mounted() {
    this.loadLinks();
    if (this.isLinkableService && this.selectedService !== 'plex') {
      this.loadServerUsers();
    }
  },

  beforeUnmount() {
    this.cancelPlexOAuth();
  },

  methods: {
    // ── Links ──────────────────────────────────────────────────────────────

    async loadLinks() {
      try {
        const res = await getMyLinks();
        this.links = res.data;
      } catch (err) {
        console.error('Failed to load media links', err);
      }
    },

    async loadServerUsers() {
      this.isLoadingServerUsers = true;
      this.serverUsersError = null;
      try {
        const res = await getMediaServerUsers(this.selectedService);
        this.serverUsers = res.data;
      } catch (err) {
        this.serverUsersError =
          err.response?.data?.error || `Could not load ${this.providerLabel} users`;
      } finally {
        this.isLoadingServerUsers = false;
      }
    },

    async linkAccount() {
      if (!this.selectedServerUser) return;
      this.linkError = null;
      this.isLinking = true;
      try {
        const payload = {
          external_user_id: this.selectedServerUser.id,
          external_username: this.selectedServerUser.name,
        };
        if (this.selectedService === 'jellyfin') {
          await linkJellyfin(payload);
        } else {
          await linkEmby(payload);
        }
        this.$toast.success(`${this.providerLabel} account linked`);
        this.selectedServerUser = '';
        await this.loadLinks();
      } catch (err) {
        this.linkError = err.response?.data?.error || `Failed to link ${this.providerLabel} account`;
      } finally {
        this.isLinking = false;
      }
    },

    async unlinkAccount() {
      this.isUnlinking = true;
      try {
        await unlinkProvider(this.selectedService);
        this.$toast.success(`${this.providerLabel} account unlinked`);
        await this.loadLinks();
      } catch (err) {
        this.$toast.error(err.response?.data?.error || `Failed to unlink ${this.providerLabel}`);
      } finally {
        this.isUnlinking = false;
      }
    },

    // ── Plex OAuth ─────────────────────────────────────────────────────────

    async startPlexOAuth() {
      this.linkError = null;
      this.isLinking = true;
      try {
        const res = await plexOAuthStart();
        this.plexPinId = res.data.pin_id;
        window.open(res.data.auth_url, '_blank', 'noopener,noreferrer');
        this.plexPolling = true;
        this._schedulePlexPoll();
      } catch (err) {
        this.linkError = err.response?.data?.error || 'Failed to start Plex authorisation';
      } finally {
        this.isLinking = false;
      }
    },

    _schedulePlexPoll() {
      this.plexPollTimer = setTimeout(() => this._pollPlex(), 3000);
    },

    async _pollPlex() {
      if (!this.plexPolling || !this.plexPinId) return;
      try {
        const res = await plexOAuthPoll(this.plexPinId);
        if (res.data.status === 'linked') {
          this.plexPolling = false;
          this.plexPinId = null;
          this.$toast.success(`Plex account linked as ${res.data.external_username}`);
          await this.loadLinks();
        } else {
          this._schedulePlexPoll();
        }
      } catch (err) {
        this.plexPolling = false;
        this.plexPinId = null;
        this.linkError = err.response?.data?.error || 'Plex authorisation failed';
      }
    },

    cancelPlexOAuth() {
      this.plexPolling = false;
      this.plexPinId = null;
      if (this.plexPollTimer) {
        clearTimeout(this.plexPollTimer);
        this.plexPollTimer = null;
      }
    },

    // ── Account updates ────────────────────────────────────────────────────

    async saveUsername() {
      this.usernameError = null;
      this.usernameSuccess = null;
      const newName = this.usernameForm.value.trim();
      if (!newName) return;
      this.isSavingUsername = true;
      try {
        const res = await updateMyProfile({ username: newName });
        // Update singleton auth state so the header reflects the new name immediately.
        if (this.currentUser) this.currentUser.username = newName;
        if (res.data.access_token) this.accessToken = res.data.access_token;
        this.usernameSuccess = 'Username updated.';
        this.usernameForm.value = '';
      } catch (err) {
        this.usernameError = err.response?.data?.error || 'Failed to update username';
      } finally {
        this.isSavingUsername = false;
      }
    },

    async savePassword() {
      this.passwordError = null;
      this.passwordSuccess = null;
      if (this.passwordForm.new !== this.passwordForm.confirm) {
        this.passwordError = 'New passwords do not match.';
        return;
      }
      this.isSavingPassword = true;
      try {
        await updateMyProfile({
          current_password: this.passwordForm.current,
          new_password: this.passwordForm.new,
        });
        this.passwordSuccess = 'Password changed successfully.';
        this.passwordForm = { current: '', new: '', confirm: '' };
      } catch (err) {
        this.passwordError = err.response?.data?.error || 'Failed to change password';
      } finally {
        this.isSavingPassword = false;
      }
    },
  },
};
</script>

<style scoped>
/* ── Outer wrapper ─────────────────────────────────────────────────────── */
.settings-users {
  color: var(--color-text-primary);
  padding: var(--spacing-lg);
}

/* ── Section header ────────────────────────────────────────────────────── */
.section-header {
  margin-bottom: 2rem;
}

.section-header h2 {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
  color: var(--color-text-primary);
}

.section-header p {
  color: var(--color-text-muted);
  font-size: 1rem;
  margin: 0;
}

/* ── Settings grid ─────────────────────────────────────────────────────── */
.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 2rem;
  margin-bottom: 2rem;
}

/* ── Settings group card ───────────────────────────────────────────────── */
.settings-group {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--border-radius-md);
  padding: 1.5rem;
}

.settings-group h3 {
  font-size: 1.2rem;
  margin-bottom: 1rem;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.accounts-group {
  grid-column: 1 / 1;
}


/* Form elements */
.form-group {
  margin-bottom: 1.5rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  margin-top: 0.5rem;
  font-weight: 500;
  color: #e5e7eb;
}
.form-control {
  width: 100%;
  padding: 0.75rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-primary);
  font-size: 1rem;
  transition: var(--transition-base);
  min-height: 44px;
}

.form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  background: var(--color-bg-active);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-group {
  display: flex;
  gap: 0.5rem;
}

.input-group .form-control {
  flex: 1;
}

.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: var(--color-text-muted);
  line-height: 1.4;
}

.mb-3 { margin-bottom: 0.75rem; }

.group-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.group-title-row h3 {
  margin: 0;
}

.card-desc {
  color: var(--color-text-muted);
  font-size: 0.9rem;
  margin-bottom: 1.25rem;
  line-height: 1.5;
}

/* ── Form sub-sections ─────────────────────────────────────────────────── */
.settings-group form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.subsection-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin: 0;
}

.section-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 1.25rem 0;
}

/* ── Empty / loading state ─────────────────────────────────────────────── */
.list-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 2rem 1rem;
  color: var(--color-text-muted);
  font-size: 0.95rem;
  border: 1px dashed rgba(255, 255, 255, 0.1);
  border-radius: var(--border-radius-sm);
}

/* ── User row (linked state) ───────────────────────────────────────────── */
.user-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.9rem 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: var(--border-radius-sm);
}

.user-identity {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  min-width: 0;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
  font-size: 0.9rem;
  flex-shrink: 0;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.user-name {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--color-text-primary);
}

.user-meta {
  font-size: 0.78rem;
  color: var(--color-text-muted);
}

.icon-btn {
  width: 34px;
  height: 34px;
  padding: 0;
  justify-content: center;
  flex-shrink: 0;
}

/* ── Feedback banners ──────────────────────────────────────────────────── */
.error-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--color-danger);
  font-size: 0.875rem;
  padding: 0.6rem 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--border-radius-sm);
}

.success-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--color-success);
  font-size: 0.875rem;
  padding: 0.6rem 0.75rem;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.25);
  border-radius: var(--border-radius-sm);
}

/* ── Responsive ────────────────────────────────────────────────────────── */
@media (max-width: 700px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
