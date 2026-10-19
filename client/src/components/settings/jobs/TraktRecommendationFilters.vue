<template>
  <div>
    <div v-if="isLoading" :class="noticeClass">
      <i aria-hidden="true" class="fas fa-spinner fa-spin"></i>
      <span>Loading Trakt users...</span>
    </div>
    <div v-else-if="!traktConfigured" :class="noticeClass">
      <i aria-hidden="true" class="fas fa-link-slash"></i>
      <span>Configure Trakt app credentials in Connections first.</span>
    </div>
    <div v-else-if="connectedUsers.length === 0" :class="noticeClass">
      <i aria-hidden="true" class="fas fa-user-slash"></i>
      <span>No media users have a linked Trakt account yet.</span>
    </div>
    <div
      v-else
      class="grid gap-2 sm:grid-cols-2"
      role="radiogroup"
      aria-label="Trakt account"
    >
      <button
        v-for="user in connectedUsers"
        :key="user.external_user_id"
        type="button"
        class="flex w-full cursor-pointer items-center gap-2.5 rounded-ctl border px-3 py-2 text-left text-sm transition-colors"
        :class="selectedUserId === user.external_user_id ? 'border-brand bg-brand-soft text-ink' : 'border-edge-strong bg-panel-2 text-ink-2 hover:border-ink-4'"
        role="radio"
        :aria-checked="selectedUserId === user.external_user_id"
        @click="selectUser(user.external_user_id)"
      >
        <i aria-hidden="true" :class="selectedUserId === user.external_user_id ? 'fas fa-circle-dot text-brand-ink' : 'far fa-circle text-ink-4'"></i>
        <span class="min-w-0 flex-1 truncate font-medium">{{ user.external_username || user.external_user_id }}</span>
      </button>
    </div>
  </div>
</template>

<script>
/**
 * Picks the one media user whose linked Trakt recommendations a Trakt job fetches.
 * Binds to the whole job form and only touches `user_ids`.
 */
export default {
  name: 'TraktRecommendationFilters',
  props: {
    modelValue: {
      type: Object,
      default: () => ({})
    },
    traktConfigured: {
      type: Boolean,
      default: false
    },
    connectedUsers: {
      type: Array,
      default: () => []
    },
    isLoading: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:modelValue'],
  data() {
    return {
      noticeClass: 'flex items-center gap-2 rounded-ctl border border-dashed border-edge-strong p-3 text-[13px] text-ink-4',
    };
  },
  computed: {
    selectedUserId() {
      const ids = this.modelValue.user_ids || [];
      return ids.length ? ids[0] : '';
    }
  },
  watch: {
    connectedUsers: {
      handler(users) {
        if (!this.selectedUserId && users.length === 1) {
          this.selectUser(users[0].external_user_id);
        }
      },
      immediate: true
    }
  },
  methods: {
    selectUser(externalUserId) {
      this.$emit('update:modelValue', {
        ...this.modelValue,
        user_ids: [externalUserId]
      });
    }
  }
};
</script>
