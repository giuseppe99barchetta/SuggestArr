<template>
  <div class="text-ink" data-users-page>

    <PageHeader title="Users" subtitle="SuggestArr accounts, their roles and who can sign up. Your own settings are under Profile." />

    <div data-users-cards class="mb-8 grid items-stretch gap-5 min-[1001px]:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">

      <SectionCard icon="fas fa-users" title="Accounts">
        <template #actions>
          <button type="button" class="ui-btn h-9" @click="openCreateModal">
            <i aria-hidden="true" class="fas fa-user-plus"></i>
            New User
          </button>
        </template>

        <!-- Loading -->
        <p v-if="isLoadingUsers" :class="emptyClass">
          <i aria-hidden="true" class="fas fa-spinner fa-spin"></i>
          Loading users…
        </p>

        <!-- Empty -->
        <p v-else-if="users.length === 0" :class="emptyClass">
          <i aria-hidden="true" class="fas fa-users"></i>
          No accounts found.
        </p>

        <!-- User rows -->
        <div v-else class="flex flex-col gap-2">
          <div
            v-for="user in users"
            :key="user.id"
            class="flex items-center gap-4 rounded-ctl border border-edge bg-panel-2 px-4 py-3 transition hover:border-edge-strong hover:bg-raised max-[700px]:grid max-[700px]:grid-cols-3 max-[700px]:gap-2"
            :class="{ 'opacity-50': !user.is_active }"
          >
            <!-- Avatar + name -->
            <div class="flex min-w-0 flex-1 items-center gap-3 max-[700px]:col-span-full">
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-edge-strong bg-raised text-sm text-ink-4">
                <i aria-hidden="true" class="fas fa-user"></i>
              </div>
              <div class="flex min-w-0 flex-col gap-0.5">
                <span class="flex items-center gap-1.5 truncate text-[0.95rem] font-semibold text-ink">
                  {{ user.username }}
                  <span v-if="user.id === currentUserId" class="shrink-0 rounded-full bg-brand px-1.5 py-px text-[0.65rem] font-bold uppercase tracking-wide text-white">you</span>
                </span>
                <span class="text-[0.78rem] text-ink-4">
                  Last login: {{ formatDate(user.last_login) }}
                </span>
              </div>
            </div>

            <!-- Status chip -->
            <button
              type="button"
              :disabled="user.id === currentUserId || !!isSaving[user.id]"
              class="inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1 text-[0.78rem] font-semibold transition disabled:cursor-not-allowed disabled:opacity-40"
              :class="user.is_active ? 'border-good bg-good/10 text-good hover:enabled:bg-good/20' : 'border-edge-strong bg-panel-2 text-ink-4 hover:enabled:bg-raised'"
              @click="toggleActive(user)"
            >
              <i aria-hidden="true" :class="user.is_active ? 'fas fa-circle' : 'far fa-circle'"></i>
              {{ user.is_active ? 'Active' : 'Inactive' }}
            </button>

            <!-- Role select -->
            <div class="w-[140px] shrink-0 max-[700px]:col-span-2 max-[700px]:w-full">
              <BaseDropdown
                v-model="user.role"
                :options="roleOptions"
                :disabled="user.id === currentUserId || !!isSaving[user.id]"
                @change="() => updateUserRole(user)"
              />
            </div>

            <!-- Edit permissions -->
            <button
              type="button"
              :disabled="!!isSaving[user.id]"
              class="ui-btn h-9 w-9 shrink-0 px-0"
              title="Edit permissions"
              aria-label="Edit permissions"
              @click="openEditPermissionsModal(user)"
            >
              <i aria-hidden="true" class="fas fa-pencil-alt"></i>
            </button>

            <button
              type="button"
              :disabled="!!isSaving[user.id] || !supportsUserLinks"
              class="ui-btn h-9 w-9 shrink-0 px-0"
              title="Assign media account"
              aria-label="Assign media account"
              @click="openMediaLinkModal(user)"
            >
              <i aria-hidden="true" class="fas fa-link"></i>
            </button>

            <!-- Delete -->
            <button
              type="button"
              :disabled="user.id === currentUserId || !!isSaving[user.id]"
              class="ui-btn-icon-danger"
              title="Delete user"
              aria-label="Delete user"
              @click="confirmDelete(user)"
            >
              <i aria-hidden="true" class="fas fa-trash"></i>
            </button>
          </div>
        </div>
      </SectionCard>

      <SectionCard icon="fas fa-door-open" title="Self-Registration">
        <BaseCheckbox
          v-model="localAllowRegistration"
          :disabled="isSavingRegistration"
          class="w-full rounded-ctl border border-edge bg-panel-2 px-4 py-3"
          label="Allow sign-ups"
          description="Anyone with access to the login page can create a User account."
          @change="saveRegistration"
        />
      </SectionCard>

    </div>

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
import SectionCard from '@/components/ui/SectionCard.vue';

export default {
  name: 'UserManagement',

  components: { AppDialog, BaseDropdown, BaseCheckbox, PageHeader, SectionCard },

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
      emptyClass: 'm-0 flex items-center justify-center gap-3 rounded-[8px] border border-dashed border-edge-strong px-4 py-8 text-[0.95rem] text-ink-4',
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
