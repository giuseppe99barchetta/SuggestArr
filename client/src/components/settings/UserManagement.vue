<template>
  <div class="settings-users">
    <div class="section-header">
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

            <!-- Role select -->
            <select
              v-model="user.role"
              :disabled="user.id === currentUserId || !!isSaving[user.id]"
              class="role-select"
              @change="updateUserRole(user)"
            >
              <option value="admin">Admin</option>
              <option value="viewer">Viewer</option>
              <option value="user">User</option>
            </select>

            <!-- Status chip -->
            <button
              :disabled="user.id === currentUserId || !!isSaving[user.id]"
              :class="['status-chip', user.is_active ? 'status-chip--active' : 'status-chip--inactive']"
              @click="toggleActive(user)"
            >
              <i :class="user.is_active ? 'fas fa-circle' : 'far fa-circle'"></i>
              {{ user.is_active ? 'Active' : 'Inactive' }}
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
              v-model="allowRegistration"
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
          <div class="modal-box">
            <div class="modal-header">
              <h3><i class="fas fa-user-plus"></i> Create Account</h3>
              <button class="modal-close" @click="showCreateModal = false">
                <i class="fas fa-times"></i>
              </button>
            </div>

            <div class="modal-body">
              <div class="form-group">
                <label for="newUsername">Username</label>
                <input
                  id="newUsername"
                  v-model="newUser.username"
                  type="text"
                  class="form-control"
                  placeholder="Enter username"
                  maxlength="64"
                  :disabled="isCreating"
                  @keydown.enter="submitCreate"
                />
              </div>

              <div class="form-group">
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
                    class="btn btn-outline btn-sm"
                    :disabled="isCreating"
                    @click="showNewPassword = !showNewPassword"
                  >
                    <i :class="showNewPassword ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
                  </button>
                </div>
              </div>

              <div class="form-group">
                <label for="newRole">Role</label>
                <select
                  id="newRole"
                  v-model="newUser.role"
                  class="form-control"
                  :disabled="isCreating"
                >
                  <option value="viewer">Viewer</option>
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
                <small class="form-help">
                  Admins have full access. Viewers have read-only access.
                </small>
              </div>

              <div v-if="createError" class="error-banner">
                <i class="fas fa-exclamation-circle"></i>
                {{ createError }}
              </div>
            </div>

            <div class="modal-footer">
              <button class="btn btn-outline" :disabled="isCreating" @click="showCreateModal = false">
                Cancel
              </button>
              <button class="btn btn-primary" :disabled="isCreating" @click="submitCreate">
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
          <div class="modal-box modal-box--sm">
            <div class="modal-header">
              <h3><i class="fas fa-exclamation-triangle"></i> Delete Account</h3>
              <button class="modal-close" @click="showDeleteModal = false">
                <i class="fas fa-times"></i>
              </button>
            </div>
            <div class="modal-body">
              <p style="color: #e5e7eb; margin: 0; line-height: 1.6;">
                Permanently delete <strong>{{ deleteTarget?.username }}</strong>?
                This cannot be undone.
              </p>
            </div>
            <div class="modal-footer">
              <button class="btn btn-outline" :disabled="isDeleting" @click="showDeleteModal = false">
                Cancel
              </button>
              <button class="btn btn-danger" :disabled="isDeleting" @click="submitDelete">
                <i :class="isDeleting ? 'fas fa-spinner fa-spin' : 'fas fa-trash'"></i>
                {{ isDeleting ? 'Deleting…' : 'Delete' }}
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
import { getUsers, createUserAdmin, updateUser, deleteUser } from '@/api/api';
import axios from 'axios';

export default {
  name: 'UserManagement',

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
      allowRegistration: false,
      isSavingRegistration: false,

      // Create modal
      showCreateModal: false,
      newUser: { username: '', password: '', role: 'viewer' },
      showNewPassword: false,
      createError: null,
      isCreating: false,

      // Delete modal
      showDeleteModal: false,
      deleteTarget: null,
      isDeleting: false,
    };
  },

  computed: {
    currentUserId() {
      if (!this.currentUser) return null;
      return Number(this.currentUser.id ?? this.currentUser.sub ?? null);
    },
  },

  mounted() {
    this.loadUsers();
    this.loadRegistrationSetting();
  },

  methods: {
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

    async loadRegistrationSetting() {
      try {
        const res = await axios.get('/api/config/section/advanced');
        this.allowRegistration = Boolean(res.data?.ALLOW_REGISTRATION);
      } catch (err) {
        console.error('Failed to load registration setting', err);
      }
    },

    async updateUserRole(user) {
      this.$set(this.isSaving, user.id, true);
      try {
        await updateUser(user.id, { role: user.role });
        this.$toast.success(`Role updated for ${user.username}`);
      } catch (err) {
        this.$toast.error(err.response?.data?.error || 'Failed to update role');
        await this.loadUsers();
      } finally {
        this.$set(this.isSaving, user.id, false);
      }
    },

    async toggleActive(user) {
      this.$set(this.isSaving, user.id, true);
      const newActive = !user.is_active;
      try {
        await updateUser(user.id, { is_active: newActive });
        user.is_active = newActive;
        this.$toast.success(`${user.username} ${newActive ? 'activated' : 'deactivated'}`);
      } catch (err) {
        this.$toast.error(err.response?.data?.error || 'Failed to update status');
        await this.loadUsers();
      } finally {
        this.$set(this.isSaving, user.id, false);
      }
    },

    openCreateModal() {
      this.newUser = { username: '', password: '', role: 'viewer' };
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

    async saveRegistration() {
      this.isSavingRegistration = true;
      try {
        await axios.post('/api/config/section/advanced', {
          ALLOW_REGISTRATION: this.allowRegistration,
        });
        this.$toast.success(
          `Self-registration ${this.allowRegistration ? 'enabled' : 'disabled'}`
        );
      } catch (err) {
        this.$toast.error('Failed to save registration setting');
        this.allowRegistration = !this.allowRegistration;
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
  grid-column: 1 / -1;
}

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

/* ── User list ─────────────────────────────────────────────────────────── */
.user-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.user-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.9rem 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: var(--border-radius-sm);
  transition: var(--transition-base);
}

.user-row:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
}

.user-row--inactive {
  opacity: 0.5;
}

/* ── User identity ─────────────────────────────────────────────────────── */
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
  display: flex;
  align-items: center;
  gap: 0.4rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.you-badge {
  background: var(--color-primary);
  color: #fff;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.user-meta {
  font-size: 0.78rem;
  color: var(--color-text-muted);
}

/* ── Role select ───────────────────────────────────────────────────────── */
.role-select {
  background: var(--color-bg-interactive);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  padding: 0.35rem 0.6rem;
  font-size: 0.85rem;
  cursor: pointer;
  transition: var(--transition-base);
  flex-shrink: 0;
}

.role-select:focus {
  outline: none;
  border-color: var(--color-primary);
}

.role-select:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Status chip ───────────────────────────────────────────────────────── */
.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  border: 1px solid;
  cursor: pointer;
  flex-shrink: 0;
  transition: var(--transition-base);
}

.status-chip--active {
  color: var(--color-success);
  border-color: rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.1);
}

.status-chip--active:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.18);
}

.status-chip--inactive {
  color: var(--color-text-muted);
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
}

.status-chip--inactive:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
}

.status-chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Icon-only button ──────────────────────────────────────────────────── */
.icon-btn {
  width: 34px;
  height: 34px;
  padding: 0;
  justify-content: center;
  flex-shrink: 0;
}

/* ── Error banner ──────────────────────────────────────────────────────── */
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

/* ── Modal overlay ─────────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 1rem;
}

/* ── Modal box ─────────────────────────────────────────────────────────── */
.modal-box {
  background: #1e1e2e;
  border: 1px solid rgba(165, 180, 252, 0.3);
  border-radius: var(--border-radius-md);
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6);
}

.modal-box--sm {
  max-width: 380px;
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #a5b4fc;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.modal-close {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-muted);
  font-size: 1rem;
  padding: 0.35rem 0.5rem;
  border-radius: var(--border-radius-sm);
  transition: color 0.2s, background 0.2s;
}

.modal-close:hover {
  color: #e5e7eb;
  background: rgba(255, 255, 255, 0.08);
}

.modal-body {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

/* ── Modal transition ──────────────────────────────────────────────────── */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

/* ── Responsive ────────────────────────────────────────────────────────── */
@media (max-width: 600px) {
  .user-row {
    flex-wrap: wrap;
    gap: 0.6rem;
  }
  .user-identity {
    width: 100%;
  }
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
