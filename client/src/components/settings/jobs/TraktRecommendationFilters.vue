<template>
  <div class="flex flex-col gap-5">
    <div>
      <label id="trakt-user-label" class="mb-1 block text-[13px] font-semibold text-ink-2">Trakt Account</label>
      <p class="mb-3 block text-xs text-ink-4">
        Choose the media user whose linked Trakt recommendations this job should fetch.
      </p>

      <div v-if="isLoading" class="flex items-center gap-2 rounded-ctl border border-dashed border-edge p-3 text-[0.8rem] text-ink-4">
        <i class="fas fa-spinner fa-spin"></i>
        <span>Loading Trakt users...</span>
      </div>

      <div v-else-if="!traktConfigured" class="flex items-center gap-2 rounded-ctl border border-dashed border-edge p-3 text-[0.8rem] text-ink-4">
        <i class="fas fa-link-slash"></i>
        <span>Configure Trakt app credentials in Connections first.</span>
      </div>

      <div v-else-if="connectedUsers.length === 0" class="flex items-center gap-2 rounded-ctl border border-dashed border-edge p-3 text-[0.8rem] text-ink-4">
        <i class="fas fa-user-slash"></i>
        <span>No media users have a linked Trakt account yet.</span>
      </div>

      <div
        v-else
        class="flex flex-col gap-2"
        role="radiogroup"
        aria-labelledby="trakt-user-label"
      >
        <button
          v-for="user in connectedUsers"
          :key="user.external_user_id"
          type="button"
          class="flex w-full cursor-pointer items-center gap-3 rounded-ctl border p-3 text-left text-inherit transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          :class="selectedUserId === user.external_user_id ? 'border-brand bg-brand/10' : 'border-edge bg-transparent hover:bg-white/5'"
          role="radio"
          :aria-checked="selectedUserId === user.external_user_id"
          @click="selectUser(user.external_user_id)"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-full bg-panel-2 text-ink-4">
            <i class="fas fa-user"></i>
          </div>
          <div class="flex flex-1 flex-col gap-0.5">
            <span class="text-[0.85rem] text-ink">{{ user.external_username || user.external_user_id }}</span>
            <span class="text-[0.7rem] text-ink-4">Trakt connected</span>
          </div>
          <i v-if="selectedUserId === user.external_user_id" class="fas fa-check text-brand-ink"></i>
        </button>
      </div>
    </div>

    <div>
      <label class="mb-1 block text-[13px] font-semibold text-ink-2">Request Behavior</label>
      <div class="flex flex-col gap-1.5">
        <div class="flex items-center gap-3">
          <BaseCheckbox v-model="localFilters.exclude_downloaded">
            <span class="inline-flex items-center gap-2 font-medium text-ink">
              <i class="fas fa-download"></i>
              Exclude downloaded content
            </span>
          </BaseCheckbox>
        </div>
        <small class="mb-2 ml-7 block text-xs text-ink-4">Skip titles already in your library</small>

        <div class="flex items-center gap-3">
          <BaseCheckbox v-model="localFilters.exclude_requested">
            <span class="inline-flex items-center gap-2 font-medium text-ink">
              <i class="fas fa-clock"></i>
              Exclude requested content
            </span>
          </BaseCheckbox>
        </div>
        <small class="mb-2 ml-7 block text-xs text-ink-4">Skip titles already requested in Seer</small>
      </div>
    </div>

    <div v-if="showAdvanced">
      <label for="maxTraktResults" class="mb-1 block text-[13px] font-semibold text-ink-2">Total Request Limit: {{ maxResults }}</label>
      <input
        id="maxTraktResults"
        :value="maxResults"
        type="range"
        min="5"
        max="100"
        step="5"
        class="w-full accent-brand"
        @input="updateMaxResults"
      />
      <small class="mt-1.5 block text-xs text-ink-4">Maximum Trakt recommendations to request per run</small>
    </div>
  </div>
</template>

<script>
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';

export default {
  name: 'TraktRecommendationFilters',
  components: { BaseCheckbox },
  props: {
    modelValue: {
      type: Object,
      default: () => ({})
    },
    showAdvanced: {
      type: Boolean,
      default: false
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
      isUpdatingFromParent: false,
      localFilters: {
        exclude_downloaded: true,
        exclude_requested: true
      }
    };
  },
  computed: {
    selectedUserId() {
      const ids = this.modelValue.user_ids || [];
      return ids.length ? ids[0] : '';
    },
    maxResults() {
      return this.modelValue.max_results || 20;
    }
  },
  watch: {
    modelValue: {
      handler(newVal) {
        this.isUpdatingFromParent = true;
        this.localFilters = {
          exclude_downloaded: newVal.filters?.exclude_downloaded ?? true,
          exclude_requested: newVal.filters?.exclude_requested ?? true
        };
        this.$nextTick(() => {
          this.isUpdatingFromParent = false;
        });
      },
      deep: true,
      immediate: true
    },
    localFilters: {
      handler(newVal) {
        if (!this.isUpdatingFromParent) {
          this.updateFilters(newVal);
        }
      },
      deep: true
    },
    connectedUsers: {
      handler(users) {
        if (!this.selectedUserId && users.length === 1) {
          this.selectUser(users[0].external_user_id);
        }
      },
      immediate: true
    }
  },
  mounted() {
    if (
      this.modelValue.filters?.exclude_downloaded === undefined
      || this.modelValue.filters?.exclude_requested === undefined
    ) {
      this.updateFilters(this.localFilters);
    }
  },
  methods: {
    selectUser(externalUserId) {
      this.$emit('update:modelValue', {
        ...this.modelValue,
        user_ids: [externalUserId]
      });
    },
    updateFilters(filters) {
      this.$emit('update:modelValue', {
        ...this.modelValue,
        filters: {
          ...this.modelValue.filters,
          ...filters
        }
      });
    },
    updateMaxResults(event) {
      this.$emit('update:modelValue', {
        ...this.modelValue,
        max_results: Number(event.target.value)
      });
    }
  }
};
</script>
