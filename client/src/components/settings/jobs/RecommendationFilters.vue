<template>
  <div class="flex flex-col gap-5">
    <!-- User Selection Mode -->
    <div v-if="!isTraktSource">
      <label class="mb-2 block text-sm font-medium text-ink-2">Monitor Users</label>
      <div class="flex gap-2">
        <button
          v-for="mode in userModes"
          :key="mode.value"
          type="button"
          class="flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-ctl border px-4 py-3 text-[0.9rem] transition"
          :class="userMode === mode.value ? 'border-brand bg-brand text-white' : 'border-edge bg-panel-2 text-ink-3 hover:border-ink-4 hover:text-ink'"
          @click="setUserMode(mode.value)"
        >
          <i :class="mode.icon"></i>
          {{ mode.label }}
        </button>
      </div>
    </div>

    <!-- User Selection (when specific mode) -->
    <div v-if="!isTraktSource && userMode === 'specific'">
      <label class="mb-2 block text-sm font-medium text-ink-2">Select Users</label>
      <div v-if="usersUnavailable" :class="emptyClass">
        <i class="fas fa-lock"></i>
        <span>User selection is only available to administrators.</span>
      </div>
      <div v-else-if="availableUsers.length > 0" class="flex max-h-[200px] flex-col gap-2 overflow-y-auto rounded-ctl border border-edge bg-white/3 p-2">
        <button
          v-for="user in availableUsers"
          :key="user.id"
          type="button"
          class="flex cursor-pointer items-center gap-3 rounded-ctl border p-3 text-left transition"
          :class="isUserSelected(user.id) ? 'border-brand bg-brand/10' : 'border-edge bg-panel-2 hover:border-ink-4'"
          :aria-pressed="isUserSelected(user.id) ? 'true' : 'false'"
          @click="toggleUser(user.id)"
        >
          <span class="flex h-8 w-8 items-center justify-center rounded-full" :class="isUserSelected(user.id) ? 'bg-brand text-white' : 'bg-white/5 text-ink-4'">
            <i class="fas fa-user"></i>
          </span>
          <span class="flex-1 font-medium text-ink">{{ user.name || user.id }}</span>
          <i v-if="isUserSelected(user.id)" class="fas fa-check text-brand-ink"></i>
        </button>
      </div>
      <div v-else-if="isLoading" :class="emptyClass">
        <i class="fas fa-spinner fa-spin"></i>
        <span>Loading users...</span>
      </div>
      <div v-else :class="emptyClass">
        <i class="fas fa-user-slash"></i>
        <span>No users found. Configure SELECTED_USERS in settings.</span>
      </div>
    </div>

    <div v-if="isTraktSource">
      <label class="mb-2 block text-sm font-medium text-ink-2">Trakt Account</label>
      <div :class="emptyClass">
        <i class="fas fa-tv"></i>
        <span>This job uses the owner's linked Trakt account.</span>
      </div>
    </div>

    <!-- AI Enhancement (shown when LLM is configured) -->
    <div v-if="llmConfigured" class="rounded-ctl border border-brand bg-brand/10 px-4 py-3">
      <label class="mb-3 flex items-center gap-2 text-sm font-medium text-brand-ink">
        <i class="fas fa-robot"></i>
        AI Enhancement
      </label>
      <div class="py-1">
        <BaseCheckbox
          v-model="localFilters.use_llm"
          @change="updateFilters(localFilters)"
        >
          <span class="flex items-center gap-2 font-medium text-ink">
            <i class="fas fa-brain w-4 text-ink-4"></i>
            Enable AI-powered recommendations
          </span>
        </BaseCheckbox>
      </div>
      <small v-if="localFilters.use_llm" class="mt-2 flex items-start gap-1.5 text-sm text-brand-ink opacity-85">
        <i class="fas fa-info-circle mt-0.5"></i>
        The AI will analyze the full watch history to generate personalized recommendations, replacing the standard TMDb similarity search.
      </small>
      <small v-else class="mt-2 block text-sm text-ink-4">
        Use your configured LLM to generate recommendations based on watch history patterns instead of TMDb similarity.
      </small>
    </div>

    <!-- Advanced Recommendation Settings (only shown when showAdvanced is true) -->
    <template v-if="showAdvanced">
      <div>
        <label class="mb-2 block text-sm font-medium text-ink-2" for="maxRecommendationResults">Total Request Limit: {{ maxResults }}</label>
        <input
          id="maxRecommendationResults"
          :value="maxResults"
          type="range"
          min="5"
          max="100"
          step="5"
          class="w-full accent-brand"
          @input="updateMaxResults"
        />
        <small class="mt-2 block text-sm text-ink-4">Maximum items this recommendation job can request per run</small>
      </div>

      <div v-for="slider in sliders" :key="slider.key">
        <label class="mb-2 block text-sm font-medium text-ink-2" :for="slider.key">{{ slider.label }}: {{ localFilters[slider.key] || slider.fallback }}</label>
        <input
          :id="slider.key"
          v-model.number="localFilters[slider.key]"
          type="range"
          :min="slider.min"
          :max="slider.max"
          :step="slider.step"
          class="w-full accent-brand"
        />
        <small class="mt-2 block text-sm text-ink-4">{{ slider.help }}</small>
      </div>

      <!-- Behavior Toggles -->
      <div>
        <label class="mb-2 block text-sm font-medium text-ink-2">Behavior Options</label>
        <div class="flex flex-col gap-1 rounded-ctl border border-edge bg-white/3 p-3">
          <template v-for="toggle in behaviorToggles" :key="toggle.key">
            <div class="flex items-center gap-3 rounded-[8px] p-2 transition hover:bg-panel-2">
              <BaseCheckbox v-model="localFilters[toggle.key]" :disabled="toggle.trakt && !traktUsable">
                <span class="flex items-center gap-2 font-medium text-ink" :class="{ 'opacity-50': toggle.trakt && !traktUsable }">
                  <i :class="[toggle.icon, 'w-4 text-ink-4']"></i>
                  {{ toggle.label }}
                </span>
              </BaseCheckbox>
            </div>
            <small v-if="toggle.trakt && traktWarning" class="mb-2 ml-10 text-xs text-caution">
              <i class="fas fa-exclamation-triangle"></i>
              {{ traktWarning }}
            </small>
            <small v-else class="mb-2 ml-10 text-xs text-ink-4">{{ toggle.help }}</small>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import axios from 'axios';
import { waitForAuthReady } from '@/composables/useAuth';
import { listTraktMediaUsers } from '@/api/api';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';

export default {
  name: 'RecommendationFilters',
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
    llmConfigured: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:modelValue'],
  data() {
    return {
      availableUsers: [],
      usersUnavailable: false,
      isLoading: false,
      localFilters: {
        use_llm: false,
        max_similar_movie: 5,
        max_similar_tv: 2,
        max_content: 10,
        search_size: 20,
        exclude_downloaded: true,
        exclude_requested: true,
        honor_seer_discovery: false,
        only_first_movie_in_collection: false,
        use_trakt_as_seed: true,
        use_trakt_as_exclusion: true
      },
      isUpdatingFromParent: false,
      localUserMode: 'all',
      selectedService: '',
      traktConfigured: false,
      traktMediaUsers: [],
      emptyClass: 'flex items-center justify-center gap-2 rounded-ctl border border-edge bg-white/3 p-6 text-[0.9rem] text-ink-4',
      userModes: [
        { value: 'all', label: 'All Users', icon: 'fas fa-users' },
        { value: 'specific', label: 'Specific Users', icon: 'fas fa-user-check' },
      ],
      sliders: [
        { key: 'max_similar_movie', label: 'Similar Movies Per Watched', fallback: 5, min: 1, max: 10, step: 1, help: 'How many similar movies to find for each watched movie' },
        { key: 'max_similar_tv', label: 'Similar TV Shows Per Watched', fallback: 2, min: 1, max: 10, step: 1, help: 'How many similar TV shows to find for each watched show' },
        { key: 'max_content', label: 'Max Content to Check', fallback: 10, min: 5, max: 50, step: 5, help: 'Maximum recently watched items to analyze per user' },
        { key: 'search_size', label: 'Search Size', fallback: 20, min: 10, max: 50, step: 5, help: 'Number of results to fetch per TMDb search' },
      ],
      behaviorToggles: [
        { key: 'exclude_downloaded', icon: 'fas fa-download', label: 'Exclude Downloaded Content', help: 'Skip content already in your library' },
        { key: 'exclude_requested', icon: 'fas fa-clock', label: 'Exclude Requested Content', help: 'Skip content already requested in Seer' },
        { key: 'honor_seer_discovery', icon: 'fas fa-compass', label: 'Honor Seer Discovery', help: "Respect Seer's discovery settings for requests" },
        { key: 'only_first_movie_in_collection', icon: 'fas fa-layer-group', label: 'Only First Movie in Collections', help: 'Skip sequels while still introducing new movie collections' },
        { key: 'use_trakt_as_seed', icon: 'fas fa-seedling', label: 'Use Trakt as Seed', help: 'Use linked Trakt watch history to find similar content', trakt: true },
        { key: 'use_trakt_as_exclusion', icon: 'fas fa-ban', label: 'Exclude Trakt Watched', help: 'Skip content already watched on Trakt', trakt: true },
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
    maxResults() {
      return this.modelValue.max_results || 20;
    },
    traktWarning() {
      if (!this.traktConfigured) return 'Trakt not configured — set Client ID / Secret in Connections';
      if (!this.traktUsable) return 'No linked Trakt accounts — link accounts in Connections > Trakt';
      return '';
    },
    traktUsable() {
      if (!this.traktConfigured || !this.traktMediaUsers.length) return false;
      if (this.userMode === 'all') {
        return this.traktMediaUsers.some(u => u.trakt?.connected);
      }
      const selectedIds = this.modelValue.user_ids || [];
      if (!selectedIds.length) return false;
      return this.traktMediaUsers.some(
        u => selectedIds.includes(u.external_user_id) && u.trakt?.connected
      );
    },
  },
  watch: {
    modelValue: {
      handler(newVal) {
        if (newVal.filters) {
          this.isUpdatingFromParent = true;
          this.localFilters = {
            use_llm: newVal.filters.use_llm ?? false,
            max_similar_movie: newVal.filters.max_similar_movie ?? 5,
            max_similar_tv: newVal.filters.max_similar_tv ?? 2,
            max_content: newVal.filters.max_content ?? 10,
            search_size: newVal.filters.search_size ?? 20,
            exclude_downloaded: newVal.filters.exclude_downloaded ?? true,
            exclude_requested: newVal.filters.exclude_requested ?? true,
            honor_seer_discovery: newVal.filters.honor_seer_discovery ?? false,
            only_first_movie_in_collection: newVal.filters.only_first_movie_in_collection ?? false,
            use_trakt_as_seed: newVal.filters.use_trakt_as_seed ?? true,
            use_trakt_as_exclusion: newVal.filters.use_trakt_as_exclusion ?? true
          };
          this.$nextTick(() => {
            this.isUpdatingFromParent = false;
          });
        }
        // Initialize user mode based on user_ids
        if (!this.isTraktSource && newVal.user_ids && newVal.user_ids.length > 0) {
          this.localUserMode = 'specific';
        }
      },
      deep: true,
      immediate: true
    },
    localFilters: {
      handler(newVal) {
        // Don't emit if the change came from the parent
        if (!this.isUpdatingFromParent) {
          this.updateFilters(newVal);
        }
      },
      deep: true
    }
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
        this.traktConfigured = statusResponse.data?.trakt_app_configured === true;
        if (this.traktConfigured) {
          try {
            const traktRes = await listTraktMediaUsers();
            this.traktMediaUsers = traktRes.data?.media_users || [];
          } catch {
            this.traktMediaUsers = [];
          }
        } else {
          this.traktMediaUsers = [];
        }
        if (this.isTraktSource && this.modelValue.user_ids?.length) {
          this.$emit('update:modelValue', {
            ...this.modelValue,
            user_ids: []
          });
        }
        if (this.isTraktSource) {
          return;
        }

        // Admin users can still populate configured media users when available.
        // /api/config/fetch is admin-only; non-admins receive a 403, which we
        // handle gracefully instead of treating it as a hard error.
        this.usersUnavailable = false;
        try {
          const response = await axios.get('/api/config/fetch');
          if (response.data?.SELECTED_SERVICE) {
            this.selectedService = String(response.data.SELECTED_SERVICE || '').toLowerCase();
          }
          if (response.data && response.data.SELECTED_USERS) {
            const users = response.data.SELECTED_USERS;
            this.availableUsers = users.map(u => {
              if (typeof u === 'string') {
                return { id: u, name: u };
              }
              return { id: u.id, name: u.name || u.id };
            });
          }
        } catch (err) {
          if (err.response?.status === 403) {
            // Non-admins can't list configured users; surface a note instead of an error.
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
        this.$emit('update:modelValue', {
          ...this.modelValue,
          user_ids: []
        });
      }
      // For 'specific', don't change user_ids - let user select
    },

    isUserSelected(userId) {
      return this.modelValue.user_ids && this.modelValue.user_ids.includes(userId);
    },

    toggleUser(userId) {
      const currentIds = this.modelValue.user_ids || [];
      let newIds;

      if (this.isUserSelected(userId)) {
        newIds = currentIds.filter(id => id !== userId);
      } else {
        newIds = [...currentIds, userId];
      }

      this.$emit('update:modelValue', {
        ...this.modelValue,
        user_ids: newIds
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
