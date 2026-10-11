<template>
  <div class="settings-users">

    <PageHeader title="Users" subtitle="SuggestArr accounts, their roles and who can sign up. Your own settings are under Profile." />

    <div class="settings-grid">

      <!-- Accounts Card -->
      <div class="settings-group accounts-group">
        <div class="group-title-row">
          <h3>
            <i class="fas fa-users"></i>
            Accounts
          </h3>
          <button class="btn btn-outline btn-sm" @click="openCreateModal">
            <i class="fas fa-user-plus"></i>
            New User
          </button>
        </div>

        <!-- Loading -->
        <div v-if="isLoadingUsers" class="list-empty">
          <i class="fas fa-spinner fa-spin"></i>
          Loading users…
        </div>

        <!-- Empty -->
        <div v-else-if="users.length === 0" class="list-empty">
          <i class="fas fa-users"></i>
          No accounts found.
        </div>

        <!-- User rows -->
        <div v-else class="user-list">
          <div
            v-for="user in users"
            :key="user.id"
            class="user-row"
            :class="{ 'user-row--inactive': !user.is_active }"
          >
            <!-- Avatar + name -->
            <div class="user-identity">
              <div class="user-avatar">
                <i class="fas fa-user"></i>
              </div>
              <div class="user-info">
                <span class="user-name">
                  {{ user.username }}
                  <span v-if="user.id === currentUserId" class="you-badge">you</span>
                </span>
                <span class="user-meta">
                  Last login: {{ formatDate(user.last_login) }}
                </span>
              </div>
            </div>

            <!-- Status chip -->
            <button
              :disabled="user.id === currentUserId || !!isSaving[user.id]"
              :class="['status-chip', user.is_active ? 'status-chip--active' : 'status-chip--inactive']"
              @click="toggleActive(user)"
            >
              <i :class="user.is_active ? 'fas fa-circle' : 'far fa-circle'"></i>
              {{ user.is_active ? 'Active' : 'Inactive' }}
            </button>

            <!-- Role select -->
            <div class="role-dropdown-wrap">
              <BaseDropdown
                v-model="user.role"
                :options="roleOptions"
                :disabled="user.id === currentUserId || !!isSaving[user.id]"
                @change="() => updateUserRole(user)"
              />
            </div>

            <!-- Edit permissions -->
            <button
              :disabled="!!isSaving[user.id]"
              class="btn btn-outline btn-sm icon-btn"
              title="Edit permissions"
              @click="openEditPermissionsModal(user)"
            >
              <i class="fas fa-pencil-alt"></i>
            </button>

            <button
              :disabled="!!isSaving[user.id] || !supportsUserLinks"
              class="btn btn-outline btn-sm icon-btn"
              title="Assign media account"
              @click="openMediaLinkModal(user)"
            >
              <i class="fas fa-link"></i>
            </button>

            <!-- Delete -->
            <button
              :disabled="user.id === currentUserId || !!isSaving[user.id]"
              class="btn btn-danger btn-sm icon-btn"
              title="Delete user"
              @click="confirmDelete(user)"
            >
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </div>
      </div>

      <!-- Self-Registration Card -->
      <div class="settings-group">
        <h3>
          <i class="fas fa-door-open"></i>
          Self-Registration
        </h3>

        <p class="card-desc">
          When enabled, anyone with access to the login page can create their own account.
          New accounts are assigned the <strong>user</strong> role.
        </p>

        <div class="form-group">
          <BaseCheckbox
            v-model="localAllowRegistration"
            :disabled="isSavingRegistration"
            label="Allow self-registration"
            @change="saveRegistration"
          />
          <small class="form-help">
            Disabled by default. Enable only if you want users to sign up themselves.
          </small>
        </div>
      </div>

    </div><!-- /settings-grid -->

    <AppDialog v-if="showCreateModal" width="max-w-xl" title="Create account" subtitle="A new SuggestArr login. Share the password with the person securely." icon="fas fa-user-plus" @close="showCreateModal = false">
      <form id="create-user-form" class="flex flex-col gap-4" @submit.prevent="submitCreate">
        <label class="ui-label">Username
          <input v-model="newUser.username" type="text" class="ui-input" placeholder="e.g. alex" maxlength="64" autocomplete="off" :disabled="isCreating" />
        </label>
        <div class="ui-label">
          <label for="newPassword">Password</label>
          <div class="flex gap-2">
            <input id="newPassword" v-model="newUser.password" :type="showNewPassword ? 'text' : 'password'" class="ui-input" placeholder="At least 8 characters" autocomplete="new-password" :disabled="isCreating" />
            <button type="button" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isCreating" :aria-label="showNewPassword ? 'Hide password' : 'Show password'" @click="showNewPassword = !showNewPassword">
              <i aria-hidden="true" :class="showNewPassword ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
          <span class="text-xs font-normal" :class="newUser.password && newUser.password.length < 8 ? 'text-caution' : 'text-ink-4'">
            {{ newUser.password && newUser.password.length < 8 ? 'Use at least 8 characters.' : 'Mix letters, numbers and symbols.' }}
          </span>
        </div>
        <fieldset class="m-0 flex flex-col gap-2 border-0 p-0">
          <legend class="mb-1.5 p-0 text-[13px] font-semibold text-ink-2">Role</legend>
          <label v-for="role in roleOptions" :key="role.value" class="flex cursor-pointer items-start gap-3 rounded-ctl border p-3" :class="newUser.role === role.value ? 'border-brand bg-brand-soft' : 'border-edge-strong bg-panel-2 hover:border-ink-4'">
            <input v-model="newUser.role" type="radio" name="new-user-role" :value="role.value" class="mt-0.5 accent-brand" :disabled="isCreating" />
            <span class="text-sm font-semibold text-ink">{{ role.label }}<span class="block text-xs font-normal text-ink-3">{{ role.value === 'admin' ? 'Full access, including settings and other accounts.' : 'Requests and their own profile.' }}</span></span>
          </label>
        </fieldset>
        <p v-if="createError" class="ui-alert-bad" role="alert">{{ createError }}</p>
      </form>
      <template #footer>
        <button type="button" class="ui-btn" :disabled="isCreating" @click="showCreateModal = false">Cancel</button>
        <button type="submit" form="create-user-form" class="ui-btn-primary" :disabled="isCreating">
          <i v-if="isCreating" aria-hidden="true" class="fas fa-spinner fa-spin"></i>{{ isCreating ? 'Creating…' : 'Create account' }}
        </button>
      </template>
    </AppDialog>

    <AppDialog v-if="showDeleteModal" title="Delete account" icon="fas fa-trash" tone="danger" @close="showDeleteModal = false">
      <p class="m-0 text-sm leading-relaxed text-ink-2">Permanently delete <strong class="text-ink">{{ deleteTarget?.username }}</strong>? They lose access immediately. This cannot be undone.</p>
      <template #footer>
        <button type="button" class="ui-btn" :disabled="isDeleting" @click="showDeleteModal = false">Cancel</button>
        <button type="button" class="ui-btn-danger" :disabled="isDeleting" @click="submitDelete">
          <i v-if="isDeleting" aria-hidden="true" class="fas fa-spinner fa-spin"></i>{{ isDeleting ? 'Deleting…' : 'Delete account' }}
        </button>
      </template>
    </AppDialog>

    <AppDialog v-if="showPermissionsModal" width="max-w-2xl" title="Permissions" icon="fas fa-user-shield" @close="showPermissionsModal = false">
      <template #subtitle>
        {{ permissionsTarget?.username }} · <span class="capitalize">{{ permissionsTarget?.role }}</span>
      </template>
      <div class="flex flex-col gap-6">
        <section class="flex flex-col gap-3">
          <h3 class="m-0 text-[11px] font-bold uppercase tracking-wider text-ink-4">Features</h3>
          <BaseCheckbox
            v-model="editPermissions.can_manage_ai"
            :disabled="isSavingPermissions"
            label="Can manage AI settings"
            description="Lets this user set their own AI provider and key."
          />
        </section>

        <section class="flex flex-col gap-2">
          <h3 class="m-0 text-[11px] font-bold uppercase tracking-wider text-ink-4">Seer identity</h3>
          <p class="m-0 text-[13px] text-ink-3">Approved requests are credited to this Seer user.</p>
          <BaseDropdown v-model="editPermissions.seer_user_id" :options="seerUserOptions" placeholder="Use technical user fallback" :disabled="isSavingPermissions" />
        </section>

        <fieldset class="m-0 flex flex-col gap-2 border-0 p-0">
          <legend class="mb-2 p-0 text-[11px] font-bold uppercase tracking-wider text-ink-4">Visible pages</legend>
          <div class="grid gap-2 sm:grid-cols-2">
            <label
              v-for="tab in availableTabs"
              :key="tab.value"
              class="flex items-center gap-3 rounded-ctl border border-edge-strong bg-panel-2 px-3 py-2.5 text-sm text-ink-2"
              :class="tab.required ? 'opacity-60' : 'cursor-pointer hover:border-ink-4'"
            >
              <input
                type="checkbox"
                class="accent-brand"
                :value="tab.value"
                :checked="editPermissions.visible_tabs_array.includes(tab.value)"
                :disabled="isSavingPermissions || tab.required"
                @change="toggleTab(tab.value)"
              />
              <i aria-hidden="true" class="w-4 text-center text-ink-4" :class="tab.icon"></i>
              <span class="flex-1">{{ tab.label }}</span>
              <span v-if="tab.required" class="text-[10px] font-bold uppercase tracking-wide text-ink-4">Always</span>
            </label>
          </div>
        </fieldset>

        <p v-if="permissionsError" class="ui-alert-bad" role="alert">{{ permissionsError }}</p>
      </div>
      <template #footer>
        <button type="button" class="ui-btn" :disabled="isSavingPermissions" @click="showPermissionsModal = false">Cancel</button>
        <button type="button" class="ui-btn-primary" :disabled="isSavingPermissions" @click="submitPermissions">
          <i v-if="isSavingPermissions" aria-hidden="true" class="fas fa-spinner fa-spin"></i>{{ isSavingPermissions ? 'Saving…' : 'Save permissions' }}
        </button>
      </template>
    </AppDialog>

    <AppDialog v-if="showMediaLinkModal" title="Link media account" icon="fas fa-link" :subtitle="mediaLinkSubtitle" @close="showMediaLinkModal = false">
      <div class="flex flex-col gap-3">
        <BaseDropdown
          v-model="selectedMediaUserId"
          :options="mediaUserOptions"
          :label="providerLabel + ' user'"
          placeholder="Select account"
          :disabled="isLoadingMediaUsers || isSavingMediaLink"
        />
        <p v-if="isLoadingMediaUsers" class="m-0 text-xs text-ink-4"><i aria-hidden="true" class="fas fa-spinner fa-spin mr-1"></i>Loading {{ providerLabel }} users…</p>
        <p v-if="mediaLinkError" class="ui-alert-bad" role="alert">{{ mediaLinkError }}</p>
      </div>
      <template #footer>
        <button type="button" class="ui-btn" :disabled="isSavingMediaLink" @click="showMediaLinkModal = false">Cancel</button>
        <button type="button" class="ui-btn-primary" :disabled="isSavingMediaLink || !selectedMediaUserId" @click="submitMediaLink">
          <i v-if="isSavingMediaLink" aria-hidden="true" class="fas fa-spinner fa-spin"></i>{{ isSavingMediaLink ? 'Saving…' : 'Save link' }}
        </button>
      </template>
    </AppDialog>

  </div>
</template>

<script>
import { useAuth } from '@/composables/useAuth';
import {
  adminLinkProvider,
  createUserAdmin,
  deleteUser,
  fetchPlexUsers,
  getMediaServerUsers,
  getUsers,
  updateUser,
  updateUserPermissions,
} from '@/api/api';
import axios from 'axios';
import BaseDropdown from '@/components/common/BaseDropdown.vue';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import PageHeader from '@/components/ui/PageHeader.vue';
import AppDialog from '@/components/ui/AppDialog.vue';

export default {
  name: 'UserManagement',

  components: { AppDialog, BaseDropdown, BaseCheckbox, PageHeader },

  props: {
    config: Object,
    isLoading: Boolean,
  },

  setup() {
    const { currentUser } = useAuth();
    return { currentUser };
  },

  data() {
    return {
      users: [],
      isLoadingUsers: false,
      isSaving: {},
      localAllowRegistration: false,
      isSavingRegistration: false,

      // Create modal
      showCreateModal: false,
      newUser: { username: '', password: '', role: 'user' },
      showNewPassword: false,
      createError: null,
      isCreating: false,

      // Delete modal
      showDeleteModal: false,
      deleteTarget: null,
      isDeleting: false,

      // Permissions modal
      showPermissionsModal: false,
      permissionsTarget: null,
      editPermissions: {
        can_manage_ai: false,
        visible_tabs_array: [],
        seer_user_id: null,
      },
      seerUsers: [],
      permissionsError: null,
      isSavingPermissions: false,

      showMediaLinkModal: false,
      mediaLinkTarget: null,
      mediaUsers: [],
      selectedMediaUserId: '',
      isLoadingMediaUsers: false,
      isSavingMediaLink: false,
      mediaLinkError: null,

      roleOptions: [
        { label: 'Admin', value: 'admin' },
        { label: 'User', value: 'user' },
      ],

      availableTabs: [
        { value: 'requests', label: 'Requests', icon: 'fas fa-film', required: false },
        { value: 'jobs', label: 'Jobs', icon: 'fas fa-briefcase', required: false },
        { value: 'ai_search', label: 'AI Search', icon: 'fas fa-robot', required: false },
        { value: 'profile', label: 'Profile', icon: 'fas fa-user-circle', required: true },
      ],
    };
  },

  computed: {
    currentUserId() {
      if (!this.currentUser) return null;
      return Number(this.currentUser.id ?? this.currentUser.sub ?? null);
    },
    selectedService() {
      return (this.config?.SELECTED_SERVICE || '').toLowerCase();
    },
    supportsUserLinks() {
      return ['jellyfin', 'emby', 'plex'].includes(this.selectedService);
    },
    providerLabel() {
      const labels = { plex: 'Plex', jellyfin: 'Jellyfin', emby: 'Emby' };
      return labels[this.selectedService] || 'media';
    },
    mediaLinkSubtitle() {
      return `Which ${this.providerLabel} user's watch history belongs to ${this.mediaLinkTarget?.username}.`;
    },
    mediaUserOptions() {
      return this.mediaUsers.map((user) => ({
        label: user.name || user.username || user.title || user.email || String(user.id),
        value: String(user.id),
      }));
    },
    seerUserOptions() {
      return [{ label: 'Technical user fallback', value: null }, ...this.seerUsers.map(user => ({ label: user.displayName || user.username || user.email || String(user.id), value: user.id }))];
    },
    selectedMediaUser() {
      return this.mediaUsers.find((user) => String(user.id) === String(this.selectedMediaUserId)) || null;
    },
  },

  watch: {
    'config.ALLOW_REGISTRATION': {
      immediate: true,
      handler(val) {
        this.localAllowRegistration = !!val;
      },
    },
  },

  mounted() {
    this.loadUsers();
    this.loadSeerUsers();
  },

  methods: {
    normalizeTabValue(tabValue) {
      if (tabValue === 'suggestions') return 'requests';
      if (tabValue === 'ai-search') {
        return 'ai_search';
      }
      return tabValue;
    },

    async loadUsers() {
      this.isLoadingUsers = true;
      try {
        const res = await getUsers();
        this.users = res.data;
      } catch (err) {
        this.$toast.error('Failed to load users');
        console.error(err);
      } finally {
        this.isLoadingUsers = false;
      }
    },
    async loadSeerUsers() {
      try { this.seerUsers = (await axios.get('/api/seer/get_users')).data.users || []; }
      catch { this.seerUsers = []; }
    },

    async updateUserRole(user) {
      this.isSaving[user.id] = true;
      try {
        await updateUser(user.id, { role: user.role });
        this.$toast.success(`Role updated for ${user.username}`);
      } catch (err) {
        this.$toast.error(err.response?.data?.error || 'Failed to update role');
        await this.loadUsers();
      } finally {
        this.isSaving[user.id] = false;
      }
    },

    async toggleActive(user) {
      this.isSaving[user.id] = true;
      const newActive = !user.is_active;
      try {
        await updateUser(user.id, { is_active: newActive });
        user.is_active = newActive;
        this.$toast.success(`${user.username} ${newActive ? 'activated' : 'deactivated'}`);
      } catch (err) {
        this.$toast.error(err.response?.data?.error || 'Failed to update status');
        await this.loadUsers();
      } finally {
        this.isSaving[user.id] = false;
      }
    },

    openCreateModal() {
      this.newUser = { username: '', password: '', role: 'user' };
      this.createError = null;
      this.showNewPassword = false;
      this.showCreateModal = true;
    },

    async submitCreate() {
      this.createError = null;
      const { username, password, role } = this.newUser;
      if (!username.trim() || !password) {
        this.createError = 'Username and password are required.';
        return;
      }
      this.isCreating = true;
      try {
        await createUserAdmin({ username: username.trim(), password, role });
        this.$toast.success(`Account "${username.trim()}" created`);
        this.showCreateModal = false;
        await this.loadUsers();
      } catch (err) {
        this.createError = err.response?.data?.error || 'Failed to create account';
      } finally {
        this.isCreating = false;
      }
    },

    confirmDelete(user) {
      this.deleteTarget = user;
      this.showDeleteModal = true;
    },

    async submitDelete() {
      if (!this.deleteTarget) return;
      this.isDeleting = true;
      try {
        await deleteUser(this.deleteTarget.id);
        this.$toast.success(`Account "${this.deleteTarget.username}" deleted`);
        this.showDeleteModal = false;
        await this.loadUsers();
      } catch (err) {
        this.$toast.error(err.response?.data?.error || 'Failed to delete account');
      } finally {
        this.isDeleting = false;
        this.deleteTarget = null;
      }
    },

    openEditPermissionsModal(user) {
      const normalizedTabs = Array.isArray(user.visible_tabs)
        ? user.visible_tabs.map((t) => this.normalizeTabValue(t)).filter(Boolean)
        : user.visible_tabs
        ? user.visible_tabs.split(',').map((t) => this.normalizeTabValue(t.trim())).filter(Boolean)
        : [];

      if (!normalizedTabs.includes('profile')) {
        normalizedTabs.push('profile');
      }

      this.permissionsTarget = user;
      this.editPermissions = {
        can_manage_ai: user.can_manage_ai || false,
        visible_tabs_array: [...new Set(normalizedTabs)],
        seer_user_id: user.seer_user_id ?? null,
      };
      this.permissionsError = null;
      this.showPermissionsModal = true;
    },

    toggleTab(tabValue) {
      const tab = this.availableTabs.find((t) => t.value === tabValue);
      if (tab && tab.required) return; // Don't allow toggling required tabs

      const idx = this.editPermissions.visible_tabs_array.indexOf(tabValue);
      if (idx > -1) {
        this.editPermissions.visible_tabs_array.splice(idx, 1);
      } else {
        this.editPermissions.visible_tabs_array.push(tabValue);
      }
    },

    async submitPermissions() {
      if (!this.permissionsTarget) return;
      this.isSavingPermissions = true;
      this.permissionsError = null;
      try {
        const allowedTabs = [...new Set(
          this.editPermissions.visible_tabs_array
            .map((tab) => this.normalizeTabValue(tab))
            .filter(tab => this.availableTabs.some(available => available.value === tab))
        )];

        const payload = {
          can_manage_ai: this.editPermissions.can_manage_ai,
          allowed_tabs: allowedTabs,
          seer_user_id: this.editPermissions.seer_user_id == null ? null : Number(this.editPermissions.seer_user_id),
        };
        const response = await updateUserPermissions(this.permissionsTarget.id, payload);
        if (response?.data?.success !== true) {
          throw new Error('Unexpected permissions response');
        }
        this.$toast.success(`Permissions updated for ${this.permissionsTarget.username}`);
        this.showPermissionsModal = false;
        await this.loadUsers();
      } catch (err) {
        console.error('Failed to update permissions:', err.response?.data || err);
        this.permissionsError = err.response?.data?.error || 'Failed to update permissions';
      } finally {
        this.isSavingPermissions = false;
      }
    },

    async openMediaLinkModal(user) {
      if (!this.supportsUserLinks) return;
      this.mediaLinkTarget = user;
      this.mediaUsers = [];
      this.selectedMediaUserId = '';
      this.mediaLinkError = null;
      this.showMediaLinkModal = true;
      await this.loadMediaUsers();
    },

    async loadMediaUsers() {
      if (!this.supportsUserLinks) {
        this.mediaLinkError = 'No supported media service configured';
        return;
      }

      this.isLoadingMediaUsers = true;
      try {
        if (this.selectedService === 'plex') {
          const res = await fetchPlexUsers({
            PLEX_TOKEN: this.config.PLEX_TOKEN,
            PLEX_API_URL: this.config.PLEX_API_URL,
          });
          this.mediaUsers = res.data?.users || [];
        } else {
          const res = await getMediaServerUsers(this.selectedService);
          this.mediaUsers = Array.isArray(res.data) ? res.data : [];
        }
      } catch (err) {
        this.mediaUsers = [];
        this.mediaLinkError = err.response?.data?.error
          || err.response?.data?.message
          || `Failed to load ${this.providerLabel} users`;
      } finally {
        this.isLoadingMediaUsers = false;
      }
    },

    async submitMediaLink() {
      if (!this.mediaLinkTarget || !this.selectedMediaUser) return;
      this.isSavingMediaLink = true;
      this.mediaLinkError = null;
      try {
        const user = this.selectedMediaUser;
        const externalUsername = user.name || user.username || user.title || user.email || String(user.id);
        await adminLinkProvider(this.mediaLinkTarget.id, this.selectedService, {
          external_user_id: String(user.id),
          external_username: externalUsername,
        });
        this.$toast.success(`${this.providerLabel} account assigned to ${this.mediaLinkTarget.username}`);
        this.showMediaLinkModal = false;
      } catch (err) {
        this.mediaLinkError = err.response?.data?.error || 'Failed to assign media account';
      } finally {
        this.isSavingMediaLink = false;
      }
    },

    async saveRegistration() {
      this.isSavingRegistration = true;
      try {
        await axios.post('/api/config/section/advanced', {
          ALLOW_REGISTRATION: this.localAllowRegistration,
        });
        this.$toast.success(
          `Self-registration ${this.localAllowRegistration ? 'enabled' : 'disabled'}`
        );
      } catch {
        this.$toast.error('Failed to save registration setting');
        this.localAllowRegistration = !!this.config.ALLOW_REGISTRATION;
      } finally {
        this.isSavingRegistration = false;
      }
    },

    formatDate(ts) {
      if (!ts) return 'Never';
      try {
        return new Date(ts).toLocaleString(undefined, {
          dateStyle: 'medium',
          timeStyle: 'short',
        });
      } catch {
        return ts;
      }
    },
  },
};
</script>

<style scoped>
/* ── Outer wrapper ─────────────────────────────────────────────────────── */
.settings-users {
  color: var(--color-text-primary);
}

/* ── Admin section divider ─────────────────────────────────────────────── */
.admin-section-divider {
  margin-top: var(--spacing-xl);
  margin-bottom: var(--spacing-xl);
  padding-top: var(--spacing-xl);
  border-top: 1px solid var(--color-border-light);
}

.admin-section-divider h2 {
  font-size: var(--font-size-3xl);
  margin-bottom: var(--spacing-sm);
  color: var(--color-text-primary);
}

.admin-section-divider p {
  color: var(--color-text-muted);
  font-size: var(--font-size-base);
  margin: 0;
}

/* ── Settings grid ─────────────────────────────────────────────────────── */
.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
  align-items: stretch;
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

/* ── Settings group card ───────────────────────────────────────────────── */
.settings-group {
  background: var(--surface-raised);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: 1.25rem;
}

/* Same header as the Tailwind SectionCard: 17px title, icon in a tile. */
.settings-group h3 {
  font-size: 17px;
  font-weight: 700;
  margin: 0 0 var(--spacing-md);
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 0.875rem;
}

.settings-group h3 > i:first-child {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--surface-hover);
  color: var(--color-text-secondary);
  font-size: 15px;
}

.accounts-group {
  grid-column: 1 / 1;
}

.group-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-lg);
}

.group-title-row h3 {
  margin: 0;
}

.card-desc {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  margin-bottom: var(--spacing-lg);
  line-height: 1.5;
}

/* ── Form controls (match other settings modals) ─────────────────────── */
.form-group {
  margin-bottom: var(--spacing-lg);
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label:not(.base-checkbox) {
  display: block;
  margin-top: 0;
  margin-bottom: var(--spacing-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.form-help {
  display: block;
  margin-top: var(--spacing-xs);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  line-height: 1.4;
}

/* ── Empty / loading state ─────────────────────────────────────────────── */
.list-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: calc(var(--spacing-sm) + var(--spacing-xs));
  padding: var(--spacing-xl) var(--spacing-md);
  color: var(--color-text-muted);
  font-size: calc(var(--font-size-base) * 0.95);
  border: 1px dashed var(--color-border-medium);
  border-radius: var(--radius-sm);
}

/* ── User list ─────────────────────────────────────────────────────────── */
.user-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.user-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: calc(var(--spacing-sm) + var(--spacing-xs)) var(--spacing-md);
  background: var(--surface-base);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  transition: var(--transition-base);
}

.user-row:hover {
  background: var(--surface-interactive);
  border-color: var(--color-border-medium);
}

.user-row--inactive {
  opacity: 0.5;
}

/* ── User identity ─────────────────────────────────────────────────────── */
.user-identity {
  display: flex;
  align-items: center;
  gap: calc(var(--spacing-sm) + var(--spacing-xs));
  flex: 1;
  min-width: 0;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  background: var(--surface-interactive);
  border: 1px solid var(--color-border-medium);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  flex-shrink: 0;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: calc(var(--spacing-sm) * 0.3);
  min-width: 0;
}

.user-name {
  font-weight: var(--font-weight-semibold);
  font-size: calc(var(--font-size-base) * 0.95);
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: calc(var(--spacing-sm) * 0.8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.you-badge {
  background: var(--color-primary);
  color: var(--color-text-primary);
  font-size: calc(var(--font-size-base) * 0.65);
  font-weight: var(--font-weight-bold);
  padding: calc(var(--spacing-sm) * 0.2) calc(var(--spacing-sm) * 0.8);
  border-radius: var(--radius-full);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.user-meta {
  font-size: calc(var(--font-size-base) * 0.78);
  color: var(--color-text-muted);
}

/* ── Role dropdown ─────────────────────────────────────────────────────── */
.role-dropdown-wrap {
  width: 140px;
  flex-shrink: 0;
}

/* ── Status chip ───────────────────────────────────────────────────────── */
.status-chip {
  display: inline-flex;
  align-items: center;
  gap: calc(var(--spacing-sm) * 0.7);
  padding: calc(var(--spacing-sm) * 0.6) calc(var(--spacing-sm) * 1.4);
  border-radius: var(--radius-full);
  font-size: calc(var(--font-size-base) * 0.78);
  font-weight: var(--font-weight-semibold);
  border: 1px solid;
  cursor: pointer;
  flex-shrink: 0;
  transition: var(--transition-base);
}

.status-chip--active {
  color: var(--color-success);
  border-color: var(--color-success);
  background: var(--color-success-alpha-10);
}

.status-chip--active:hover:not(:disabled) {
  background: var(--color-success-alpha-20);
}

.status-chip--inactive {
  color: var(--color-text-muted);
  border-color: var(--color-border-medium);
  background: var(--surface-base);
}

.status-chip--inactive:hover:not(:disabled) {
  background: var(--surface-interactive);
}

.status-chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Icon-only button ──────────────────────────────────────────────────── */
.icon-btn {
  min-width: 36px;
  min-height: 36px;
  width: 36px;
  height: 36px;
  padding: 0;
  justify-content: center;
  flex-shrink: 0;
}

/* ── Responsive ────────────────────────────────────────────────────────── */
@media (max-width: 1000px) {
  .settings-grid { grid-template-columns: minmax(0, 1fr); }
}

@media (max-width: 700px) {
  .user-row {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--spacing-sm);
  }
  .user-identity {
    grid-column: 1 / -1;
  }
  .role-dropdown-wrap {
    grid-column: 2 / -1;
    width: 100%;
  }
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
