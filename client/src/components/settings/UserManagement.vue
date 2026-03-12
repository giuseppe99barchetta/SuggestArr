<template>
  <div class="settings-users">

    <!-- Admin's own profile -->
    <UserProfile :config="config" :isLoading="isLoading" embedded />

    <div class="admin-section-divider">
      <h2>User Management</h2>
      <p>Manage SuggestArr accounts, roles, and access.</p>
    </div>

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
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model="localAllowRegistration"
              @change="saveRegistration"
              :disabled="isSavingRegistration"
            />
            <span class="checkbox-text">Allow self-registration</span>
          </label>
          <small class="form-help">
            Disabled by default. Enable only if you want users to sign up themselves.
          </small>
        </div>
      </div>

    </div><!-- /settings-grid -->

    <!-- ── Create User Modal ── -->
    <teleport to="body">
      <transition name="modal-fade">
        <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
          <div class="modal" role="dialog" aria-modal="true" aria-labelledby="create-user-title">
            <div class="modal-header">
              <div class="modal-title-wrap">
                <h3 class="modal-title" id="create-user-title"><i class="fas fa-user-plus"></i> Create Account</h3>
                <p class="modal-subtitle">Set secure credentials and access level for a new SuggestArr user.</p>
              </div>
              <button type="button" class="modal-close" aria-label="Close create account modal" @click="showCreateModal = false">
                <i class="fas fa-times"></i>
              </button>
            </div>

            <div class="modal-body">
              <section class="um-section-card">
                <div class="um-section-head">
                  <h4><i class="fas fa-id-badge"></i> Account details</h4>
                  <p>Username and password for first sign-in.</p>
                </div>

                <div class="um-fields-grid">
                  <div class="form-group um-form-group">
                    <label for="newUsername">Username</label>
                    <input
                      id="newUsername"
                      v-model="newUser.username"
                      type="text"
                      class="form-control"
                      placeholder="e.g. giuseppe.barchetta"
                      maxlength="64"
                      :disabled="isCreating"
                      @keydown.enter="submitCreate"
                    />
                    <small class="form-help">Use a unique username (up to 64 characters).</small>
                  </div>

                  <div class="form-group um-form-group">
                    <label for="newPassword">Password</label>
                    <div class="input-group">
                      <input
                        id="newPassword"
                        v-model="newUser.password"
                        :type="showNewPassword ? 'text' : 'password'"
                        class="form-control"
                        placeholder="At least 8 characters"
                        :disabled="isCreating"
                        @keydown.enter="submitCreate"
                      />
                      <button
                        type="button"
                        class="btn btn-outline btn-sm um-input-action"
                        :disabled="isCreating"
                        :aria-label="showNewPassword ? 'Hide password' : 'Show password'"
                        @click="showNewPassword = !showNewPassword"
                      >
                        <i :class="showNewPassword ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
                      </button>
                    </div>
                    <small class="form-help" :class="{ 'form-help--warn': newUser.password && newUser.password.length < 8 }">
                      {{ newUser.password && newUser.password.length < 8 ? 'Use at least 8 characters for better security.' : 'Use a strong password with letters, numbers, and symbols.' }}
                    </small>
                  </div>
                </div>
              </section>

              <section class="um-section-card">
                <div class="um-section-head">
                  <h4><i class="fas fa-user-tag"></i> Access level</h4>
                  <p>Choose what this account can manage.</p>
                </div>
                <div class="form-group um-form-group">
                  <BaseDropdown
                    v-model="newUser.role"
                    :options="roleOptions"
                    label="Role"
                    placeholder="Select role"
                    help-text="Admins have full access. Users have standard access."
                    :disabled="isCreating"
                  />
                </div>
              </section>

              <div v-if="createError" class="error-banner" role="alert">
                <i class="fas fa-exclamation-circle"></i>
                {{ createError }}
              </div>
            </div>

            <div class="modal-footer">
              <button class="btn btn-outline" :disabled="isCreating" @click="showCreateModal = false">
                Cancel
              </button>
              <button class="btn btn-primary um-btn-primary" :disabled="isCreating" @click="submitCreate">
                <i :class="isCreating ? 'fas fa-spinner fa-spin' : 'fas fa-user-plus'"></i>
                {{ isCreating ? 'Creating…' : 'Create Account' }}
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>

    <!-- ── Delete Confirm Modal ── -->
    <teleport to="body">
      <transition name="modal-fade">
        <div v-if="showDeleteModal" class="modal-overlay" @click.self="showDeleteModal = false">
          <div class="modal modal--sm" role="dialog" aria-modal="true" aria-labelledby="delete-user-title">
            <div class="modal-header modal-header--danger">
              <div class="modal-title-wrap">
                <h3 class="modal-title" id="delete-user-title"><i class="fas fa-exclamation-triangle"></i> Delete Account</h3>
                <p class="modal-subtitle">This action is permanent and immediately revokes user access.</p>
              </div>
              <button type="button" class="modal-close" aria-label="Close delete account modal" @click="showDeleteModal = false">
                <i class="fas fa-times"></i>
              </button>
            </div>

            <div class="modal-body">
              <section class="um-section-card um-section-card--danger">
                <div class="um-section-head">
                  <h4><i class="fas fa-trash"></i> Confirm deletion</h4>
                  <p>Review the account before continuing.</p>
                </div>
                <p class="um-confirm-text">
                  Permanently delete <strong>{{ deleteTarget?.username }}</strong>? This cannot be undone.
                </p>
              </section>
            </div>

            <div class="modal-footer">
              <button class="btn btn-outline" :disabled="isDeleting" @click="showDeleteModal = false">
                Cancel
              </button>
              <button class="btn btn-danger um-btn-primary" :disabled="isDeleting" @click="submitDelete">
                <i :class="isDeleting ? 'fas fa-spinner fa-spin' : 'fas fa-trash'"></i>
                {{ isDeleting ? 'Deleting…' : 'Delete Account' }}
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>
    <!-- ── Edit Permissions Modal ── -->
    <teleport to="body">
      <transition name="modal-fade">
        <div v-if="showPermissionsModal" class="modal-overlay" @click.self="showPermissionsModal = false">
          <div class="modal" role="dialog" aria-modal="true" aria-labelledby="permissions-title">
            <div class="modal-header">
              <div class="modal-title-wrap">
                <h3 class="modal-title" id="permissions-title"><i class="fas fa-user-shield"></i> Edit Permissions</h3>
                <p class="modal-subtitle">Control feature permissions and navigation visibility for this account.</p>
              </div>
              <button type="button" class="modal-close" aria-label="Close permissions modal" @click="showPermissionsModal = false">
                <i class="fas fa-times"></i>
              </button>
            </div>

            <div class="modal-body">
              <section class="permissions-user-info">
                <div class="user-avatar">
                  <i class="fas fa-user"></i>
                </div>
                <div class="user-details">
                  <div class="username">{{ permissionsTarget?.username }}</div>
                  <div class="role-badge" :class="`role-badge--${permissionsTarget?.role}`">
                    {{ permissionsTarget?.role }}
                  </div>
                </div>
              </section>

              <div class="um-sections-grid">
                <section class="permissions-section um-section-card">
                  <div class="um-section-head">
                    <h4><i class="fas fa-robot"></i> AI Management</h4>
                    <p>Enable or restrict personal AI configuration access.</p>
                  </div>
                  <label class="checkbox-label">
                    <input
                      type="checkbox"
                      v-model="editPermissions.can_manage_ai"
                      :disabled="isSavingPermissions"
                    />
                    <span class="checkbox-text checkbox-text--stack">
                      <strong>Can manage AI settings</strong>
                      <small>Allow user to configure their own OpenAI API key and settings.</small>
                    </span>
                  </label>
                </section>

                <section class="permissions-section um-section-card">
                  <div class="um-section-head">
                    <h4><i class="fas fa-th-large"></i> Visible Tabs</h4>
                    <p>Select which tabs this account can access in the interface.</p>
                  </div>
                  <div class="tabs-checkboxes">
                    <label
                      v-for="tab in availableTabs"
                      :key="tab.value"
                      class="checkbox-label checkbox-label--compact"
                      :class="{ disabled: tab.required }"
                    >
                      <input
                        type="checkbox"
                        :value="tab.value"
                        :checked="editPermissions.visible_tabs_array.includes(tab.value)"
                        @change="toggleTab(tab.value)"
                        :disabled="isSavingPermissions || tab.required"
                      />
                      <span class="tab-checkbox-content">
                        <i :class="tab.icon"></i>
                        {{ tab.label }}
                        <span v-if="tab.required" class="required-badge">Required</span>
                      </span>
                    </label>
                  </div>
                </section>
              </div>

              <div v-if="permissionsError" class="error-banner" role="alert">
                <i class="fas fa-exclamation-circle"></i>
                {{ permissionsError }}
              </div>
            </div>

            <div class="modal-footer">
              <button class="btn btn-outline" :disabled="isSavingPermissions" @click="showPermissionsModal = false">
                Cancel
              </button>
              <button class="btn btn-primary um-btn-primary" :disabled="isSavingPermissions" @click="submitPermissions">
                <i :class="isSavingPermissions ? 'fas fa-spinner fa-spin' : 'fas fa-save'"></i>
                {{ isSavingPermissions ? 'Saving…' : 'Save Permissions' }}
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>

  </div>
</template>

<script>
import { useAuth } from '@/composables/useAuth';
import { getUsers, createUserAdmin, updateUser, updateUserPermissions, deleteUser } from '@/api/api';
import axios from 'axios';
import BaseDropdown from '@/components/common/BaseDropdown.vue';
import UserProfile from './UserProfile.vue';

export default {
  name: 'UserManagement',

  components: { BaseDropdown, UserProfile },

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
      },
      permissionsError: null,
      isSavingPermissions: false,

      roleOptions: [
        { label: 'Admin', value: 'admin' },
        { label: 'User', value: 'user' },
      ],

      availableTabs: [
        { value: 'requests', label: 'Requests', icon: 'fas fa-film', required: false },
        { value: 'jobs', label: 'Jobs', icon: 'fas fa-briefcase', required: false },
        { value: 'services', label: 'Services', icon: 'fas fa-cogs', required: false },
        { value: 'database', label: 'Database', icon: 'fas fa-database', required: false },
        { value: 'advanced', label: 'Advanced', icon: 'fas fa-sliders-h', required: false },
        { value: 'ai_search', label: 'AI Search', icon: 'fas fa-robot', required: false },
        { value: 'profile', label: 'Profile', icon: 'fas fa-user-circle', required: true },
        { value: 'logs', label: 'Logs', icon: 'fas fa-file-alt', required: false },

      ],
    };
  },

  computed: {
    currentUserId() {
      if (!this.currentUser) return null;
      return Number(this.currentUser.id ?? this.currentUser.sub ?? null);
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
  },

  methods: {
    normalizeTabValue(tabValue) {
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
            .filter(Boolean)
        )];

        const payload = {
          can_manage_ai: this.editPermissions.can_manage_ai,
          allowed_tabs: allowedTabs,
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

    async saveRegistration() {
      this.isSavingRegistration = true;
      try {
        await axios.post('/api/config/section/advanced', {
          ALLOW_REGISTRATION: this.localAllowRegistration,
        });
        this.$toast.success(
          `Self-registration ${this.localAllowRegistration ? 'enabled' : 'disabled'}`
        );
      } catch (err) {
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
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: var(--spacing-xl);
  margin-bottom: var(--spacing-xl);
}

/* ── Settings group card ───────────────────────────────────────────────── */
.settings-group {
  background: var(--surface-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
}

.settings-group h3 {
  font-size: var(--font-size-xl);
  margin-bottom: var(--spacing-md);
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
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

.form-group label {
  display: block;
  margin-top: 0;
  margin-bottom: var(--spacing-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: calc(var(--spacing-sm) + var(--spacing-xs));
  cursor: pointer;
  margin-bottom: var(--spacing-sm);
}

.checkbox-label input[type='checkbox'] {
  vertical-align: middle;
  width: var(--font-size-xl);
  height: var(--font-size-xl);
  accent-color: var(--color-primary);
  flex-shrink: 0;
}

.checkbox-text {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  vertical-align: middle;
  margin-left: var(--spacing-xs);
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
}

.checkbox-text--stack {
  flex-direction: column;
  align-items: flex-start;
  gap: calc(var(--spacing-sm) * 0.3);
}

.checkbox-text small {
  color: var(--color-text-muted);
  font-size: calc(var(--font-size-base) * 0.8);
  font-weight: var(--font-weight-normal);
}

.form-control {
  width: 100%;
  padding: 0 var(--input-padding-x-md);
  background: var(--surface-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--input-border-radius);
  color: var(--color-text-primary);
  font-size: var(--input-font-size-md);
  transition: var(--transition-base);
  min-height: var(--input-height-md);
}

.form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  background: var(--surface-hover);
  box-shadow: var(--shadow-focus);
}

.form-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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

/* ── Error banner ──────────────────────────────────────────────────────── */
.error-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  color: var(--color-error);
  font-size: var(--font-size-sm);
  padding: calc(var(--spacing-sm) * 1.2) calc(var(--spacing-sm) + var(--spacing-xs));
  background: var(--color-error-alpha-10);
  border: 1px solid var(--color-error);
  border-radius: var(--radius-sm);
}

/* ── UserManagement modal redesign ─────────────────────────────────────── */
.um-btn-primary {
  min-width: 150px;
}

.um-section-card {
  border: 0;
  border-radius: 0;
  padding: 0;
  background: transparent;
  display: flex;
  flex-direction: column;
  gap: calc(var(--spacing-sm) + var(--spacing-xs));
}

.um-section-card + .um-section-card {
  border-top: 1px solid var(--color-border-light);
  padding-top: var(--spacing-md);
}

.um-section-card--danger {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  background: var(--surface-base);
}

.um-section-head {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.um-section-head h4 {
  margin: 0;
  font-size: calc(var(--font-size-base) * 0.92);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: calc(var(--spacing-sm) * 0.9);
}

.um-section-head p {
  margin: 0;
  font-size: calc(var(--font-size-base) * 0.82);
  color: var(--color-text-muted);
  line-height: 1.4;
}

.um-fields-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--spacing-md);
}

.um-fields-grid .form-group:first-child {
  grid-column: 1 / -1;
}

.um-form-group {
  margin-bottom: 0;
  display: flex;
  flex-direction: column;
  gap: calc(var(--spacing-sm) * 0.9);
}

.um-modal-body .form-group label {
  margin-bottom: 0;
  font-size: calc(var(--font-size-base) * 0.84);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-muted);
}

.um-modal-body .form-control {
  min-height: var(--input-height-md);
  height: var(--input-height-md);
  padding: 0 var(--input-padding-x-md);
  font-size: var(--input-font-size-md);
  background: var(--surface-interactive);
  border-color: var(--color-border-light);
}

.um-modal-body .form-control::placeholder {
  color: var(--color-text-muted);
}

.um-modal-body .form-control:focus {
  background: var(--surface-hover);
  border-color: var(--color-border-focus);
  box-shadow: var(--shadow-focus);
}

.um-modal-body select.form-control {
  padding-right: var(--spacing-xl);
}

.um-modal-body .input-group {
  display: flex;
  align-items: stretch;
  gap: 0;
}

.um-modal-body .input-group .form-control {
  flex: 1;
}

.um-input-action {
  min-height: var(--btn-height-md);
  height: var(--btn-height-md);
  min-width: var(--btn-height-md);
  padding: 0 var(--btn-padding-x-sm);
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
  margin-left: -1px;
}

.um-modal-body .input-group .form-control {
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}

.um-modal-body .form-help {
  margin-top: 0;
  font-size: calc(var(--font-size-base) * 0.8);
}

.form-help--warn {
  color: var(--color-warning);
}

.um-confirm-text {
  margin: 0;
  line-height: 1.5;
  color: var(--color-text-primary);
}

.permissions-user-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md) calc(var(--spacing-md) + calc(var(--spacing-xs) * 0.4));
  background: var(--surface-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.permissions-user-info .user-avatar {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
}

.permissions-user-info .user-details {
  flex: 1;
}

.permissions-user-info .user-details .username {
  font-size: calc(var(--font-size-base) * 1.05);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-xs);
}

.permissions-user-info .user-details .role-badge {
  display: inline-flex;
  align-items: center;
  gap: calc(var(--spacing-sm) * 0.7);
  padding: var(--spacing-xs) calc(var(--spacing-sm) * 1.2);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  border-radius: var(--radius-full);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.role-badge--admin {
  background: var(--color-error-alpha-20);
  color: var(--color-error-light);
  border: 1px solid var(--color-error);
}

.role-badge--user {
  background: var(--color-primary-alpha-20);
  color: var(--color-primary-light);
  border: 1px solid var(--color-primary);
}

.um-sections-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: calc(var(--spacing-sm) + calc(var(--spacing-xs) * 1.6));
}

.permissions-section {
  display: flex;
  flex-direction: column;
  gap: calc(var(--spacing-sm) + calc(var(--spacing-xs) * 1.6));
}

.tabs-checkboxes {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.tabs-checkboxes label {
  display: flex;
  align-items: center;
  gap: calc(var(--spacing-sm) + var(--spacing-xs));
  padding: calc(var(--spacing-md) * 0.65) calc(var(--spacing-sm) + var(--spacing-xs));
  background: var(--surface-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
  position: relative;
}

.tabs-checkboxes label:hover:not(.disabled) {
  background: var(--surface-hover);
  border-color: var(--color-border-medium);
}

.tabs-checkboxes label:focus-within {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-focus);
}

.tabs-checkboxes label.disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.tabs-checkboxes input[type='checkbox'] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  flex-shrink: 0;
}

.tabs-checkboxes input[type='checkbox']:disabled {
  cursor: not-allowed;
}

.tabs-checkboxes .tab-label {
  display: flex;
  align-items: center;
  gap: calc(var(--spacing-sm) * 1.2);
  flex: 1;
}

.tab-checkbox-content {
  display: inline-flex;
  align-items: center;
  gap: calc(var(--spacing-sm) * 1.2);
  flex: 1;
}

.tab-checkbox-content i {
  color: var(--color-primary-light);
  font-size: var(--font-size-base);
  width: 20px;
  text-align: center;
}

.tabs-checkboxes .tab-label i {
  color: var(--color-primary-light);
  font-size: var(--font-size-base);
  width: 20px;
  text-align: center;
}

.tabs-checkboxes .tab-label span {
  font-size: calc(var(--font-size-base) * 0.95);
  color: var(--color-text-primary);
}

.required-badge {
  margin-left: auto;
  padding: calc(var(--spacing-sm) * 0.4) var(--spacing-sm);
  font-size: calc(var(--font-size-base) * 0.7);
  font-weight: var(--font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: var(--color-info-alpha-20);
  color: var(--color-info-light);
  border: 1px solid var(--color-info);
  border-radius: var(--radius-full);
}

/* ── Responsive ────────────────────────────────────────────────────────── */
@media (max-width: 600px) {
  .user-row {
    flex-wrap: wrap;
    gap: calc(var(--spacing-sm) * 1.2);
  }
  .user-identity {
    width: 100%;
  }
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .um-modal-content {
    max-height: calc(100vh - var(--spacing-lg));
  }

  .um-fields-grid {
    grid-template-columns: 1fr;
  }

  .um-modal-header,
  .um-modal-body,
  .um-modal-footer {
    padding-left: var(--spacing-md);
    padding-right: var(--spacing-md);
  }

  .um-modal-footer {
    justify-content: stretch;
  }

  .um-modal-footer .btn {
    flex: 1;
  }
}
</style>
