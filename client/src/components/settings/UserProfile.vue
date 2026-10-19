<template>
  <div class="flex flex-col gap-5" data-profile-page>
    <PageHeader title="My profile" subtitle="Your account, preferences, API keys and the accounts SuggestArr learns from." />

    <div class="grid gap-5 lg:grid-cols-2">
      <SectionCard icon="fas fa-user-circle" title="Account" description="The name you sign in with and your password.">
        <div class="mb-5 flex items-center gap-3 border-b border-edge pb-5">
          <UserAvatar :user="profileUser" class="h-16 w-16 text-[64px]" />
          <div class="min-w-0">
            <p class="m-0 truncate font-semibold text-ink">{{ profileUser?.username }}</p>
            <p class="m-0 mt-1 text-xs leading-relaxed text-ink-3">Your linked account photo, or a cinema avatar picked for you.</p>
          </div>
        </div>
        <form class="flex flex-col gap-3" @submit.prevent="saveUsername">
          <label class="ui-label" for="newUsername">New username</label>
          <div class="flex gap-2">
            <input id="newUsername" v-model="usernameForm.value" type="text" class="ui-input" :placeholder="profileUser?.username || 'Current username'" maxlength="64" :disabled="isSavingUsername" />
            <button type="submit" class="ui-btn shrink-0" :disabled="isSavingUsername || !usernameForm.value.trim()">
              <i v-if="isSavingUsername" aria-hidden="true" class="fas fa-spinner fa-spin"></i>{{ isSavingUsername ? 'Saving…' : 'Rename' }}
            </button>
          </div>
          <p v-if="usernameError" role="alert" class="ui-alert-bad">{{ usernameError }}</p>
          <p v-if="usernameSuccess" role="status" class="ui-alert-good">{{ usernameSuccess }}</p>
        </form>

        <form class="mt-5 flex flex-col gap-3 border-t border-edge pt-5" @submit.prevent="savePassword">
          <h3 class="m-0 text-sm font-bold text-ink">Change password</h3>
          <label class="ui-label">Current password<input id="currentPassword" v-model="passwordForm.current" type="password" class="ui-input" autocomplete="current-password" :disabled="isSavingPassword" /></label>
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="ui-label">New password<input id="newPassword" v-model="passwordForm.new" type="password" class="ui-input" placeholder="At least 8 characters" autocomplete="new-password" :disabled="isSavingPassword" /></label>
            <label class="ui-label">Confirm new password<input id="confirmPassword" v-model="passwordForm.confirm" type="password" class="ui-input" autocomplete="new-password" :disabled="isSavingPassword" /></label>
          </div>
          <p v-if="passwordError" role="alert" class="ui-alert-bad">{{ passwordError }}</p>
          <p v-if="passwordSuccess" role="status" class="ui-alert-good">{{ passwordSuccess }}</p>
          <button type="submit" class="ui-btn self-start" :disabled="isSavingPassword || !passwordForm.current || !passwordForm.new || !passwordForm.confirm">
            <i aria-hidden="true" :class="isSavingPassword ? 'fas fa-spinner fa-spin' : 'fas fa-lock'"></i>{{ isSavingPassword ? 'Saving…' : 'Change password' }}
          </button>
        </form>
      </SectionCard>

      <div class="flex min-w-0 flex-col gap-5">
        <SectionCard icon="fas fa-language" title="Title language" description="Titles and descriptions of suggestions and requests are shown in this language.">
          <form class="flex flex-col gap-3" @submit.prevent="saveLanguage">
            <div class="flex gap-2">
              <label class="sr-only" for="titleLanguage">Language</label>
              <select id="titleLanguage" v-model="languageForm.value" class="ui-input" :disabled="isSavingLanguage">
                <option v-for="option in languageChoices" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <button type="submit" class="ui-btn shrink-0" :disabled="isSavingLanguage">
                <i v-if="isSavingLanguage" aria-hidden="true" class="fas fa-spinner fa-spin"></i>{{ isSavingLanguage ? 'Saving…' : 'Save' }}
              </button>
            </div>
            <p v-if="!languageForm.value && displayLanguage" class="m-0 text-xs text-ink-4">Currently shown in {{ displayLanguageLabel }}.</p>
            <p v-if="languageError" role="alert" class="ui-alert-bad">{{ languageError }}</p>
            <p v-if="languageSuccess" role="status" class="ui-alert-good">{{ languageSuccess }}</p>
          </form>
        </SectionCard>

        <ApiKeysPanel class="flex-1" />
      </div>
    </div>

    <RecapPreferences v-if="profileUser?.role === 'admin'" />

    <SectionCard v-if="isLinkableService" icon="fas fa-link" title="Linked accounts" description="SuggestArr reads your watch history from these accounts to personalise suggestions.">
      <div class="grid items-start gap-5 md:grid-cols-2">
        <div class="flex min-w-0 flex-col gap-3 rounded-ctl border border-edge bg-panel-2 p-4">
          <h3 class="m-0 flex items-center gap-2 text-sm font-bold text-ink"><i aria-hidden="true" :class="providerIcon"></i>{{ providerLabel }} account</h3>

          <div v-if="currentLink" class="flex items-center gap-3">
            <span class="flex h-9 w-9 items-center justify-center rounded-full bg-good/15 text-good"><i aria-hidden="true" class="fas fa-check"></i></span>
            <span class="flex min-w-0 flex-1 flex-col">
              <span class="truncate text-sm font-semibold text-ink">{{ currentLink.external_username }}</span>
              <span class="text-xs text-ink-4">Linked {{ providerLabel }} account</span>
            </span>
            <button type="button" class="ui-btn h-9 px-3 text-[13px]" :disabled="isUnlinking" @click="unlinkAccount">
              <i aria-hidden="true" :class="isUnlinking ? 'fas fa-spinner fa-spin' : 'fas fa-unlink'"></i>Unlink
            </button>
          </div>

          <template v-else>
            <div v-if="isPlexService" class="flex flex-col gap-3">
              <p class="m-0 text-[13px] text-ink-3">Sign in with Plex in a new window to link your account.</p>
              <p v-if="linkError" role="alert" class="ui-alert-bad">{{ linkError }}</p>
              <button type="button" class="ui-btn-primary self-start" :disabled="isLinking" @click="linkPlexWithOAuth">
                <i aria-hidden="true" :class="isLinking ? 'fas fa-spinner fa-spin' : 'fas fa-link'"></i>{{ isLinking ? 'Waiting for Plex…' : 'Link Plex account' }}
              </button>
            </div>

            <form v-else class="flex flex-col gap-3" @submit.prevent="linkAccount">
              <label v-if="isDirectoryBackedService" class="ui-label">
                Your {{ providerLabel }} user
                <select id="linkServerUser" v-model="selectedServerUserId" class="ui-input" :disabled="isLinking || isLoadingServerUsers">
                  <option value="" disabled>{{ isLoadingServerUsers ? `Loading ${providerLabel} users…` : 'Select your account' }}</option>
                  <option v-for="option in serverUserOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select>
              </label>
              <label v-else class="ui-label">
                {{ providerLabel }} username
                <input id="linkUsername" v-model="linkForm.username" type="text" class="ui-input" autocomplete="username" :disabled="isLinking" />
              </label>
              <label class="ui-label">
                {{ providerLabel }} password
                <input id="linkPassword" v-model="linkForm.password" type="password" class="ui-input" autocomplete="current-password" :disabled="isLinking" />
              </label>
              <p v-if="linkError" role="alert" class="ui-alert-bad">{{ linkError }}</p>
              <button type="submit" class="ui-btn-primary self-start" :disabled="isLinking || !canSubmitLink">
                <i aria-hidden="true" :class="isLinking ? 'fas fa-spinner fa-spin' : 'fas fa-link'"></i>{{ isLinking ? 'Linking…' : `Link ${providerLabel} account` }}
              </button>
            </form>
          </template>
        </div>

        <div class="flex min-w-0 flex-col gap-3 rounded-ctl border border-edge bg-panel-2 p-4">
          <h3 class="m-0 flex items-center gap-2 text-sm font-bold text-ink"><i aria-hidden="true" class="fas fa-tv"></i>Trakt account</h3>
          <TraktMediaUsers mode="self" :trakt-configured="isTraktAppConfigured" />
        </div>
      </div>
    </SectionCard>

    <WatchedMediaHistory v-if="isLinkableService" />

    <SectionCard v-if="!isLinkableService && hasProviderContext" icon="fas fa-plug" title="Linked accounts" description="No linkable media server is configured yet. An admin must set up Jellyfin, Emby or Plex in Connections first." />
  </div>
</template>

<script>
import RecapPreferences from '@/components/recap/RecapPreferences.vue';
import PageHeader from '@/components/ui/PageHeader.vue';
import axios from 'axios';
import { useAuth } from '@/composables/useAuth';
import {
  getMediaServerUsers,
  getMyLinks,
  linkJellyfinIntegration,
  linkEmbyIntegration,
  plexOAuthPoll,
  plexOAuthStart,
  unlinkProvider,
  updateMyProfile,
} from '@/api/api';
import SectionCard from '@/components/ui/SectionCard.vue';
import TraktMediaUsers from './TraktMediaUsers.vue';
import WatchedMediaHistory from './WatchedMediaHistory.vue';
import ApiKeysPanel from './ApiKeysPanel.vue';
import UserAvatar from '@/components/ui/UserAvatar.vue';
import { refreshUserAvatar } from '@/composables/useUserAvatar';
import { languageOptions, languagePayload } from '@/utils/titleLanguage.js';

const PROVIDER_META = {
  jellyfin: { label: 'Jellyfin', icon: 'fas fa-server' },
  emby:     { label: 'Emby',     icon: 'fas fa-server' },
  plex:     { label: 'Plex',     icon: 'fas fa-play-circle' },
};

export default {
  name: 'UserProfile',
  emits: ['profile-updated'],

  components: { PageHeader, SectionCard, TraktMediaUsers, WatchedMediaHistory, ApiKeysPanel, RecapPreferences, UserAvatar },

  // The dashboard shell passes props this page does not declare.
  inheritAttrs: false,

  props: {
    currentUser: Object,
    config: Object,
    isLoading: Boolean,
  },

  setup() {
    const { currentUser: authUser, accessToken } = useAuth();
    return { authUser, accessToken };
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

      // Jellyfin / Emby users fetched from API
      serverUsers: [],
      selectedServerUserId: '',
      isLoadingServerUsers: false,

      // Provider availability for non-admin users
      configStatus: {
        selected_service: '',
        trakt_app_configured: false,
      },

      // Credential-based link form
      linkForm: { username: '', password: '' },

      // Linking / unlinking state
      isLinking: false,
      isUnlinking: false,
      linkError: null,

      // Title language
      languages: [],
      languageForm: { value: '' },
      displayLanguage: '',
      isSavingLanguage: false,
      languageError: null,
      languageSuccess: null,

    };
  },

  computed: {
    profileUser() {
      return this.currentUser || this.authUser;
    },
    languageChoices() {
      return languageOptions(this.languages);
    },

    displayLanguageLabel() {
      const match = this.languageChoices.find(option => option.value === this.displayLanguage);
      return match ? match.label : this.displayLanguage;
    },

    selectedService() {
      return (
        this.config?.SELECTED_SERVICE
        || this.configStatus?.selected_service
        || ''
      ).toLowerCase();
    },

    isLinkableService() {
      return ['jellyfin', 'emby', 'plex'].includes(this.selectedService);
    },

    isDirectoryBackedService() {
      return ['jellyfin', 'emby'].includes(this.selectedService);
    },

    isPlexService() {
      return this.selectedService === 'plex';
    },

    hasProviderContext() {
      return this.config?.SELECTED_SERVICE !== undefined
        || this.configStatus?.selected_service !== undefined;
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

    isTraktAppConfigured() {
      return !!this.config?.TRAKT_CLIENT_ID || this.configStatus?.trakt_app_configured === true;
    },

    serverUserOptions() {
      return this.serverUsers.map((user) => ({
        label: user.name,
        value: user.id,
      }));
    },

    selectedServerUser() {
      // A native <select> hands back strings; Plex ids are numbers.
      return this.serverUsers.find((user) => String(user.id) === String(this.selectedServerUserId)) || null;
    },

    canSubmitLink() {
      if (this.isPlexService) {
        return true;
      }

      if (!this.linkForm.password) {
        return false;
      }

      if (this.isDirectoryBackedService) {
        return !!this.selectedServerUserId;
      }

      return !!this.linkForm.username.trim();
    },
  },

  async mounted() {
    this.loadLanguage();
    await this.loadConfigStatus();
    await this.loadLinks();
    await this.loadServerUsers();
  },

  watch: {
    selectedService: {
      immediate: false,
      async handler() {
        this.linkError = null;
        this.linkForm.username = '';
        this.linkForm.password = '';
        this.selectedServerUserId = '';
        this.serverUsers = [];
        await this.loadServerUsers();
      },
    },
  },

  methods: {
    // ── Title language ─────────────────────────────────────────────────────

    async loadLanguage() {
      try {
        const [me, list] = await Promise.allSettled([
          axios.get('/api/auth/me', { withCredentials: true, timeout: 10000 }),
          axios.get('/api/tmdb/languages', { timeout: 10000 }),
        ]);
        if (me.status === 'fulfilled') {
          this.languageForm.value = me.value.data?.language || '';
          this.displayLanguage = me.value.data?.display_language || '';
        }
        if (list.status === 'fulfilled') this.languages = list.value.data?.languages || [];
      } catch (err) {
        console.error('Failed to load title language', err);
      }
    },

    async saveLanguage() {
      this.languageError = null;
      this.languageSuccess = null;
      this.isSavingLanguage = true;
      try {
        await updateMyProfile(languagePayload(this.languageForm.value));
        this.languageSuccess = 'Language saved.';
        await this.loadLanguage();
      } catch (err) {
        this.languageError = err.response?.data?.error || 'Could not save the language.';
      } finally {
        this.isSavingLanguage = false;
      }
    },

    // ── Links ──────────────────────────────────────────────────────────────

    async loadConfigStatus() {
      try {
        const res = await axios.get('/api/config/status', {
          withCredentials: true,
          timeout: 10000,
        });
        this.configStatus = res.data || { selected_service: '' };
      } catch (err) {
        console.error('Failed to load config status', err);
      }
    },

    async loadLinks(refreshAvatar = false) {
      try {
        const res = await getMyLinks();
        this.links = res.data;
        if (refreshAvatar) refreshUserAvatar(this.profileUser?.id);
      } catch (err) {
        console.error('Failed to load media links', err);
      }
    },

    async loadServerUsers() {
      if (!this.isDirectoryBackedService) {
        this.serverUsers = [];
        this.selectedServerUserId = '';
        return;
      }

      this.isLoadingServerUsers = true;
      try {
        const res = await getMediaServerUsers(this.selectedService);
        this.serverUsers = Array.isArray(res.data) ? res.data : [];
      } catch (err) {
        this.serverUsers = [];
        this.linkError = err.response?.data?.error || `Failed to load ${this.providerLabel} users`;
      } finally {
        this.isLoadingServerUsers = false;
      }
    },

    async linkAccount() {
      if (!this.canSubmitLink) return;
      this.linkError = null;
      this.isLinking = true;
      try {
        const resolvedUsername = this.isDirectoryBackedService
          ? this.selectedServerUser?.name || ''
          : this.linkForm.username.trim();
        const payload = {
          username: resolvedUsername,
          password: this.linkForm.password,
        };

        let response;
        if (this.selectedService === 'jellyfin') {
          response = await linkJellyfinIntegration(payload);
        } else if (this.selectedService === 'emby') {
          response = await linkEmbyIntegration(payload);
        }

        const linkedName = response?.data?.external_username || this.linkForm.username.trim();
        this.$toast.success(`${this.providerLabel} account linked as ${linkedName}`);
        this.linkForm.username = '';
        this.linkForm.password = '';
        this.selectedServerUserId = '';
        await this.loadLinks(true);
      } catch (err) {
        this.linkError = err.response?.data?.error || `Failed to link ${this.providerLabel} account`;
      } finally {
        this.isLinking = false;
      }
    },

    async linkPlexWithOAuth() {
      this.linkError = null;
      this.isLinking = true;
      try {
        const start = await plexOAuthStart();
        const { pin_id: pinId, auth_url: authUrl } = start.data || {};
        if (!pinId || !authUrl) {
          throw new Error('Invalid Plex OAuth response');
        }

        window.open(authUrl, 'plex-oauth', 'width=600,height=760');

        for (let attempt = 0; attempt < 60; attempt += 1) {
          await new Promise(resolve => setTimeout(resolve, 2000));
          const poll = await plexOAuthPoll(pinId);
          if (poll.data?.status === 'linked') {
            const linkedName = poll.data.external_username || 'Plex';
            this.$toast.success(`${this.providerLabel} account linked as ${linkedName}`);
            await this.loadLinks(true);
            return;
          }
        }

        this.linkError = 'Plex authorization timed out. Please try again.';
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
        await this.loadLinks(true);
      } catch (err) {
        this.$toast.error(err.response?.data?.error || `Failed to unlink ${this.providerLabel}`);
      } finally {
        this.isUnlinking = false;
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
        if (this.authUser) this.authUser.username = newName;
        if (res.data.access_token) this.accessToken = res.data.access_token;
        this.$emit('profile-updated');
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

