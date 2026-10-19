<template>
  <div class="flex flex-col gap-3">
    <div v-if="isTraktSource" :class="emptyClass">
      <i aria-hidden="true" class="fas fa-tv"></i>
      <span>This job uses the owner's linked Trakt account.</span>
    </div>

    <template v-else>
      <div role="radiogroup" aria-label="Users to monitor" class="flex rounded-ctl border border-edge-strong bg-canvas p-1">
        <button
          v-for="mode in userModes"
          :key="mode.value"
          type="button"
          role="radio"
          :aria-checked="userMode === mode.value"
          class="flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-[8px] border-0 px-3 py-2 text-[13px] font-semibold transition-colors"
          :class="userMode === mode.value ? 'bg-brand text-white' : 'bg-transparent text-ink-3 hover:text-ink'"
          @click="setUserMode(mode.value)"
        >
          <i aria-hidden="true" :class="mode.icon"></i>
          {{ mode.label }}
        </button>
      </div>

      <template v-if="userMode === 'specific'">
        <div v-if="usersUnavailable" :class="emptyClass">
          <i aria-hidden="true" class="fas fa-lock"></i>
          <span>User selection is only available to administrators.</span>
        </div>
        <div v-else-if="availableUsers.length > 0" class="grid max-h-[220px] gap-2 overflow-y-auto sm:grid-cols-2">
          <button
            v-for="user in availableUsers"
            :key="user.id"
            type="button"
            class="flex cursor-pointer items-center gap-2.5 rounded-ctl border px-3 py-2 text-left text-sm transition-colors"
            :class="isUserSelected(user.id) ? 'border-brand bg-brand-soft text-ink' : 'border-edge-strong bg-panel-2 text-ink-2 hover:border-ink-4'"
            :aria-pressed="isUserSelected(user.id) ? 'true' : 'false'"
            @click="toggleUser(user.id)"
          >
            <i aria-hidden="true" :class="isUserSelected(user.id) ? 'fas fa-circle-check text-brand-ink' : 'far fa-circle text-ink-4'"></i>
            <span class="min-w-0 flex-1 truncate font-medium">{{ user.name || user.id }}</span>
          </button>
        </div>
        <div v-else-if="isLoading" :class="emptyClass">
          <i aria-hidden="true" class="fas fa-spinner fa-spin"></i>
          <span>Loading users...</span>
        </div>
        <div v-else :class="emptyClass">
          <i aria-hidden="true" class="fas fa-user-slash"></i>
          <span>No users found. Configure SELECTED_USERS in settings.</span>
        </div>
        <p v-if="availableUsers.length && !(modelValue.user_ids || []).length" class="m-0 text-xs text-caution">
          Select at least one user, or switch back to all users.
        </p>
      </template>
    </template>
  </div>
</template>

<script>
import axios from 'axios';
import { waitForAuthReady } from '@/composables/useAuth';

/**
 * Picks whose watch history a recommendation job reads: every configured media user or a chosen few.
 * Binds to the whole job form and only touches `user_ids`.
 */
export default {
  name: 'RecommendationUsers',
  props: {
    modelValue: {
      type: Object,
      default: () => ({})
    }
  },
  emits: ['update:modelValue'],
  data() {
    return {
      availableUsers: [],
      usersUnavailable: false,
      isLoading: false,
      localUserMode: (this.modelValue.user_ids || []).length ? 'specific' : 'all',
      selectedService: '',
      emptyClass: 'flex items-center justify-center gap-2 rounded-ctl border border-dashed border-edge-strong p-4 text-[13px] text-ink-4',
      userModes: [
        { value: 'all', label: 'All users', icon: 'fas fa-users' },
        { value: 'specific', label: 'Specific users', icon: 'fas fa-user-check' },
      ],
    };
  },
  computed: {
    isTraktSource() {
      return this.selectedService === 'trakt';
    },
    userMode() {
      return this.localUserMode;
    },
  },
  watch: {
    'modelValue.user_ids'(ids) {
      if (ids && ids.length) this.localUserMode = 'specific';
    },
  },
  async mounted() {
    await this.loadUsers();
  },
  methods: {
    async loadUsers() {
      this.isLoading = true;
      try {
        // Ensure auth is ready before making the protected API call
        await waitForAuthReady();
        const statusResponse = await axios.get('/api/config/status');
        this.selectedService = String(statusResponse.data?.selected_service || '').toLowerCase();
        if (this.isTraktSource) {
          if (this.modelValue.user_ids?.length) {
            this.$emit('update:modelValue', { ...this.modelValue, user_ids: [] });
          }
          return;
        }

        // /api/config/fetch is admin-only; non-admins receive a 403, which we
        // handle gracefully instead of treating it as a hard error.
        this.usersUnavailable = false;
        try {
          const response = await axios.get('/api/config/fetch');
          if (response.data?.SELECTED_SERVICE) {
            this.selectedService = String(response.data.SELECTED_SERVICE || '').toLowerCase();
          }
          if (response.data && response.data.SELECTED_USERS) {
            this.availableUsers = response.data.SELECTED_USERS.map(u => (
              typeof u === 'string' ? { id: u, name: u } : { id: u.id, name: u.name || u.id }
            ));
          }
        } catch (err) {
          if (err.response?.status === 403) {
            this.availableUsers = [];
            this.usersUnavailable = true;
          } else {
            throw err;
          }
        }
      } catch (error) {
        console.error('Failed to load users:', error);
      } finally {
        this.isLoading = false;
      }
    },

    setUserMode(mode) {
      this.localUserMode = mode;
      if (mode === 'all') {
        this.$emit('update:modelValue', { ...this.modelValue, user_ids: [] });
      }
    },

    isUserSelected(userId) {
      return (this.modelValue.user_ids || []).includes(userId);
    },

    toggleUser(userId) {
      const currentIds = this.modelValue.user_ids || [];
      const user_ids = this.isUserSelected(userId)
        ? currentIds.filter(id => id !== userId)
        : [...currentIds, userId];
      this.$emit('update:modelValue', { ...this.modelValue, user_ids });
    },
  }
};
</script>
