<template>
  <div class="min-h-screen bg-canvas text-ink font-sans">
    <div v-if="currentUser" class="lg:flex">
      <!-- Mobile top bar -->
      <header class="lg:hidden sticky top-0 z-30 flex items-center gap-3 px-4 h-14 bg-side/95 backdrop-blur border-b border-edge">
        <img src="@/assets/logo.png" alt="" class="w-8 h-8 object-contain" />
        <span class="font-extrabold text-lg">SuggestArr</span>
      </header>

      <!-- Drawer backdrop (mobile) -->
      <div v-if="showMobileNav" class="lg:hidden fixed inset-0 z-40 bg-black/60" @click="showMobileNav = false"></div>

      <!-- Sidebar -->
      <nav
        aria-label="Main"
        class="fixed inset-y-0 left-0 z-50 w-64 shrink-0 flex flex-col gap-6 px-3.5 py-5 bg-side border-r border-edge overflow-y-auto transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0"
        :class="showMobileNav ? 'translate-x-0' : '-translate-x-full'"
      >
        <a
          href="https://github.com/giuseppe99barchetta/SuggestArr"
          target="_blank"
          rel="noopener noreferrer"
          class="flex items-center gap-2.5 px-2 py-1 text-ink no-underline"
        >
          <img src="@/assets/logo.png" alt="" class="w-[34px] h-[34px] object-contain" />
          <span class="font-extrabold text-lg tracking-tight">SuggestArr</span>
        </a>

        <div class="flex flex-col gap-0.5" data-tour-id="nav-tabs">
          <template v-for="group in navGroups" :key="group.label">
            <div v-if="group.label" class="px-3 pt-4 pb-1.5 text-[11px] font-bold uppercase tracking-widest text-ink-4">{{ group.label }}</div>
            <router-link
              v-for="tab in group.tabs"
              :key="tab.id"
              :to="{ name: 'DashboardTab', params: { tab: tab.id } }"
              :data-tour-id="tab.tourId || null"
              :aria-current="activeTab === tab.id ? 'page' : null"
              class="flex items-center gap-3 px-3 py-2.5 rounded-ctl text-sm font-medium no-underline transition-colors"
              :class="activeTab === tab.id ? 'bg-raised text-white' : 'text-ink-3 hover:bg-panel hover:text-ink'"
              @click="showMobileNav = false"
            >
              <i aria-hidden="true" :class="tab.icon" class="w-[18px] text-center"></i>
              <span>{{ tab.name }}</span>
              <span v-if="tab.isBeta" class="ml-auto text-[10px] font-bold tracking-wider text-brand-ink">BETA</span>
              <span v-if="tab.id === 'requests' && requestCount > 0" class="ml-auto text-[11px] font-bold px-2 py-0.5 rounded-full bg-brand text-white">{{ requestCount }}</span>
            </router-link>
          </template>
        </div>

        <div class="mt-auto flex flex-col gap-2.5">
          <a
            v-if="updateAvailable"
            :href="`https://github.com/giuseppe99barchetta/SuggestArr/releases/latest`"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-2 px-3 py-2.5 rounded-ctl bg-brand-soft/60 border border-brand-soft text-brand-ink text-[13px] font-semibold no-underline"
          >
            <i aria-hidden="true" class="fas fa-arrow-up"></i> Update available
          </a>
          <div class="flex items-center gap-2.5 p-2">
            <span class="w-8 h-8 shrink-0 rounded-full bg-raised flex items-center justify-center text-[13px] font-bold uppercase">{{ (currentUser.username || '?').charAt(0) }}</span>
            <div class="flex flex-col min-w-0">
              <router-link :to="{ name: 'DashboardTab', params: { tab: 'profile' } }" class="text-[13px] font-semibold truncate text-ink no-underline hover:text-white" title="Your profile" @click="showMobileNav = false">{{ currentUser.username }}</router-link>
              <button type="button" class="text-left text-xs text-ink-4 hover:text-ink-2 bg-transparent border-0 p-0 cursor-pointer" title="View changelog" @click="showChangelog">
                {{ currentUser.role === 'admin' ? 'Admin' : 'User' }} · {{ currentVersion }}<span v-if="currentImageTag === 'nightly'"> (nightly)</span>
              </button>
            </div>
            <button type="button" class="ml-auto w-9 h-9 shrink-0 rounded-[8px] text-ink-4 hover:text-ink hover:bg-panel bg-transparent border-0 cursor-pointer" aria-label="Replay the onboarding tour" title="Replay the onboarding tour" @click="restartTour">
              <i aria-hidden="true" class="fas fa-question-circle"></i>
            </button>
            <button v-if="authSetupComplete && authBypass" type="button" class="w-9 h-9 shrink-0 rounded-[8px] text-ink-4 hover:text-ink hover:bg-panel bg-transparent border-0 cursor-pointer" aria-label="Log out" title="Log out" @click="handleLogout">
              <i aria-hidden="true" class="fas fa-sign-out-alt"></i>
            </button>
          </div>
        </div>
      </nav>

      <!-- Content -->
      <main class="flex-1 min-w-0 px-4 sm:px-8 lg:px-12 pt-6 lg:pt-8 pb-28 lg:pb-12">
        <div class="max-w-[1240px] mx-auto">
          <transition name="fade-slide" mode="out-in">
            <component
              v-if="activeTabComponent"
              :key="activeTab"
              :is="activeTabComponent"
              :config="config"
              :current-user="currentUser"
              :section="activeTabSection"
              :isLoading="isLoading"
              :testingConnections="testingConnections"
              :getServiceStatus="getServiceStatus"
              :getServiceIcon="getServiceIcon"
              @save-section="saveSection"
              @test-connection="testConnection"
              @export-config="showExportModal = true"
              @import-config="importConfig"
              @reset-config="showResetModal = true"
            />
          </transition>
          <AppFooter />
        </div>
      </main>

      <!-- Mobile bottom navigation -->
      <nav aria-label="Quick" class="lg:hidden fixed bottom-0 inset-x-0 z-30 grid grid-flow-col auto-cols-fr px-2 pt-1.5 pb-[max(0.75rem,env(safe-area-inset-bottom))] bg-side border-t border-edge">
        <router-link
          v-for="tab in quickTabs"
          :key="tab.id"
          :to="{ name: 'DashboardTab', params: { tab: tab.id } }"
          class="relative flex flex-col items-center gap-1 py-2 text-[11px] font-semibold no-underline"
          :class="activeTab === tab.id ? 'text-brand-ink' : 'text-ink-3'"
        >
          <i aria-hidden="true" :class="tab.icon" class="text-lg"></i>
          {{ tab.name }}
          <span v-if="tab.id === 'requests' && requestCount > 0" class="absolute top-0.5 left-1/2 ml-2 text-[10px] font-bold px-1.5 rounded-full bg-brand text-white">{{ requestCount }}</span>
        </router-link>
        <button type="button" class="flex flex-col items-center gap-1 py-2 text-[11px] font-semibold text-ink-3 bg-transparent border-0 cursor-pointer" :aria-expanded="showMobileNav ? 'true' : 'false'" @click="showMobileNav = true">
          <i aria-hidden="true" class="fas fa-bars text-lg"></i>
          More
        </button>
      </nav>

      <!-- Loading Overlay -->
      <transition name="fade">
        <div v-if="isLoading" class="loading-overlay">
          <div class="loading-content">
            <div class="spinner"></div>
            <p>{{ loadingMessage }}</p>
          </div>
        </div>
      </transition>

      <AppDialog v-if="showChangelogModal" width="max-w-3xl" :title="`What's new in ${currentVersion}`" icon="fab fa-github" @close="showChangelogModal = false">
        <div v-if="isLoadingChangelog" class="flex items-center justify-center gap-2 py-10 text-sm text-ink-3">
          <i aria-hidden="true" class="fas fa-spinner fa-spin"></i>Loading changelog…
        </div>
        <div v-else-if="changelogError" class="flex flex-col items-center gap-3 py-10 text-center">
          <p class="ui-alert-bad">{{ changelogError }}</p>
          <button type="button" class="ui-btn" @click="showChangelog">Retry</button>
        </div>
        <div v-else-if="changelogData" class="changelog-content" v-html="changelogData"></div>
        <p v-else class="m-0 py-10 text-center text-sm text-ink-3">No changelog available for this version.</p>
        <template #footer>
          <a v-if="changelogData" :href="`https://github.com/giuseppe99barchetta/SuggestArr/releases/tag/${currentVersion}`" target="_blank" rel="noopener" class="ui-btn mr-auto no-underline">
            <i aria-hidden="true" class="fas fa-external-link-alt"></i>View on GitHub
          </a>
          <button type="button" class="ui-btn-primary" @click="showChangelogModal = false">Close</button>
        </template>
      </AppDialog>

      <!-- Hidden file input for import -->
      <input
        type="file"
        ref="fileInput"
        @change="handleFileImport"
        accept=".json"
        style="display: none"
      />

      <AppDialog v-if="showExportModal" title="Export configuration" subtitle="Download a JSON snapshot of your settings." icon="fas fa-download" @close="showExportModal = false">
        <div class="flex flex-col gap-4 text-sm leading-relaxed text-ink-2">
          <p class="m-0">Settings, media user identities and Trakt account metadata are included. Credentials are redacted unless you include them.</p>
          <label class="flex cursor-pointer items-start gap-3 rounded-ctl border border-edge-strong bg-panel-2 p-3">
            <input v-model="exportIncludeSecrets" type="checkbox" class="mt-1 accent-brand">
            <span class="font-semibold text-ink">Include secrets<span class="block text-xs font-normal text-ink-3">API keys, tokens and passwords, for a full backup.</span></span>
          </label>
          <p v-if="exportIncludeSecrets" class="ui-alert-bad" role="alert">
            <i aria-hidden="true" class="fas fa-exclamation-triangle mr-1 text-bad"></i>Keep this file private. Do not attach it to issues or share it for troubleshooting.
          </p>
        </div>
        <template #footer>
          <button type="button" class="ui-btn" @click="showExportModal = false">Cancel</button>
          <button type="button" class="ui-btn-primary" @click="confirmExportConfig"><i aria-hidden="true" class="fas fa-download"></i>Export</button>
        </template>
      </AppDialog>

      <AppDialog v-if="showResetModal" title="Reset all settings?" subtitle="This cannot be undone." icon="fas fa-exclamation-triangle" tone="danger" @close="showResetModal = false">
        <p class="m-0 mb-3 text-sm text-ink-2">Everything goes back to defaults:</p>
        <ul class="m-0 flex list-none flex-col gap-2 rounded-ctl border border-bad/30 bg-bad/5 p-4 text-sm text-ink-2">
          <li v-for="item in ['Service connections', 'Custom filters', 'Schedules', 'Database configuration']" :key="item">
            <i aria-hidden="true" class="fas fa-times mr-2 w-3 text-bad"></i>{{ item }}
          </li>
        </ul>
        <template #footer>
          <button type="button" class="ui-btn" @click="showResetModal = false">Cancel</button>
          <button type="button" class="ui-btn-danger" @click="confirmReset">Reset everything</button>
        </template>
      </AppDialog>

    </div>

    <div v-else>
      <div class="loading-overlay">
        <div class="loading-content">
          <div class="spinner"></div>
          <p>Loading dashboard...</p>
        </div>
      </div>
    </div>

    <!-- Onboarding Tour -->
    <OnboardingTour
      :active="showTour"
      :steps="tourSteps"
      @done="showTour = false"
    />
  </div>
</template>

<script>
import axios from 'axios';
import AppFooter from './AppFooter.vue';
import AppDialog from './ui/AppDialog.vue';
import OnboardingTour from './OnboardingTour.vue';
import { useVersionCheck } from '@/composables/useVersionCheck';
import { useAuth } from '@/composables/useAuth';
import '@/assets/styles/dashboardPage.css';
// ponytail: legacy sheets still styling the job dialogs; drop once those are rebuilt.
import '@/assets/styles/aiSearchPage.css';
import '@/assets/styles/requestsPage.css';

// Import tab components
import SettingsServices from './settings/SettingsServices.vue';
import SettingsDatabase from './settings/SettingsDatabase.vue';
import SettingsAdvanced from './settings/SettingsAdvanced.vue';
import SettingsWebhooks from './settings/SettingsWebhooks.vue';
import SettingsCleanup from './settings/SettingsCleanup.vue';
import HomePage from './HomePage.vue';
import RequestsPage from './RequestsPage.vue';
import SettingsJobs from './settings/SettingsJobs.vue';
import AiSearchPage from './settings/AiSearchPage.vue';
import LogsComponent from './LogsComponent.vue';
import UserManagement from './settings/UserManagement.vue';
import UserProfile from './settings/UserProfile.vue';
import { exportConfig, importConfig } from '@/api/api';
import { getReleaseByTag } from '@/api/githubReleasesApi';

const TOUR_STORAGE_KEY = 'suggestarr_tour_done';

export default {
  name: 'SettingsPage',
  components: {
    AppDialog,
    AppFooter,
    OnboardingTour,
    SettingsServices,
    SettingsDatabase,
    SettingsAdvanced,
    SettingsWebhooks,
    SettingsCleanup,
    HomePage,
    RequestsPage,
    SettingsJobs,
    AiSearchPage,
    LogsComponent,
    UserManagement,
    UserProfile,
  },
  setup() {
    const { currentVersion, currentImageTag, currentBuildDate, updateAvailable, checkForUpdates } = useVersionCheck();
    const { authSetupComplete, authBypass, logout } = useAuth();

    return {
      currentVersion,
      currentImageTag,
      currentBuildDate,
      updateAvailable,
      checkForUpdates,
      authSetupComplete,
      authBypass,
      logout,
    };
  },
    data() {
    return {
      currentUser: null,
      config: {},
      isLoading: false,
      loadingMessage: 'Processing...',
      showResetModal: false,
      showExportModal: false,
      exportIncludeSecrets: false,
      showChangelogModal: false,
      changelogData: null,
      isLoadingChangelog: false,
      changelogError: null,
      requestCount: 0,
      showMobileNav: false,
      showTour: false,
      // Cache per migliorare performance
      testingConnections: {
        tmdb: false,
        plex: false,
        jellyfin: false,
        seer: false,
        database: false,
      },
      tabs: [
        { id: 'home',      name: 'Home',        icon: 'fas fa-home',        group: 'main',     permission: 'requests' },
        { id: 'requests',  name: 'Requests',    icon: 'fas fa-inbox',       group: 'main',     tourId: 'tab-requests' },
        { id: 'ai_search', name: 'AI Search',   icon: 'fas fa-magic',       group: 'main',     tourId: 'tab-ai-search', isBeta: true },
        { id: 'jobs',      name: 'Jobs',        icon: 'fas fa-clock',       group: 'main',     tourId: 'tab-jobs' },
        { id: 'services',    name: 'Connections', icon: 'fas fa-plug',          group: 'settings', tourId: 'tab-services', adminOnly: true },
        { id: 'ai_provider', name: 'AI provider', icon: 'fas fa-robot',         group: 'settings', tourId: 'tab-advanced', adminOnly: true, section: 'ai' },
        { id: 'approvals',   name: 'Approvals',   icon: 'fas fa-user-check',    group: 'settings', adminOnly: true, section: 'workflow' },
        { id: 'users',       name: 'Users',       icon: 'fas fa-users',         group: 'settings', adminOnly: true },
        { id: 'profile',     name: 'Profile',     icon: 'fas fa-user-circle',   group: 'settings' },
        { id: 'webhooks',    name: 'Webhooks',    icon: 'fas fa-link',          group: 'system',   adminOnly: true },
        { id: 'cleanup',     name: 'Cleanup',     icon: 'fas fa-broom',         group: 'system',   adminOnly: true },
        { id: 'database',    name: 'Database',    icon: 'fas fa-database',      group: 'system',   tourId: 'tab-database', adminOnly: true },
        { id: 'system',      name: 'System',      icon: 'fas fa-sliders-h',     group: 'system',   adminOnly: true, section: 'system' },
        { id: 'logs',        name: 'Logs',        icon: 'fas fa-terminal',      group: 'system',   tourId: 'tab-logs', adminOnly: true },
      ],
      tourSteps: [
        {
          targetId: 'nav-tabs',
          title: 'Welcome to SuggestArr!',
          description: 'This menu gives you access to every feature. Let\'s take a quick look at each one.',
          position: 'right',
        },
        {
          targetId: 'tab-requests',
          title: 'Requests',
          description: 'Every time SuggestArr runs, it submits content requests to Seer. You can track them all here — what was requested, when, and for which user.',
          position: 'right',
        },
        {
          targetId: 'tab-jobs',
          title: 'Jobs',
          description: 'Jobs control when and how SuggestArr runs. You can create multiple jobs with different schedules, filters, media types, and user selections.',
          position: 'right',
        },
        {
          targetId: 'tab-services',
          title: 'Connections',
          description: 'Update your API keys and connection settings for TMDB, your media server (Jellyfin, Plex…), and Seer here.',
          position: 'right',
        },
        {
          targetId: 'tab-ai-search',
          title: 'AI Search',
          description: 'Describe what you\'re in the mood for in plain language — "a tense thriller set in space" — and SuggestArr uses an LLM to find and request matching titles for you.',
          position: 'right',
        },
        {
          targetId: 'tab-database',
          title: 'Database',
          description: 'By default SuggestArr uses SQLite (zero setup). Switch here to PostgreSQL, MySQL, or MariaDB if you need a shared or more scalable database.',
          position: 'right',
        },
        {
          targetId: 'tab-advanced',
          title: 'AI provider',
          description: 'Connect a language model for AI Search and AI recommendations. Approvals, webhooks, cleanup and system settings each have their own page below.',
          position: 'right',
        },
        {
          targetId: 'tab-logs',
          title: 'Logs',
          description: 'View real-time application logs to debug issues, monitor job execution, or check why a specific request was skipped.',
          position: 'right',
        },
      ],
    };
  },
  computed: {
    visibleTabs() {
      if (!this.currentUser) {
        return [];
      }

      const isAdmin = this.currentUser.role === 'admin';
      const allowedTabs = new Set(
        String(this.currentUser.visible_tabs || '')
          .split(',')
          .map(tab => this.normalizeTabId(tab.trim()))
          .filter(Boolean)
      );

      return this.tabs.filter(tab => {
        if (tab.adminOnly && !isAdmin) return false;
        if (!isAdmin && allowedTabs.size > 0 && !allowedTabs.has(tab.permission || tab.id)) return false;
        return true;
      });
    },
    activeTabComponent() {
      // Never resolve a component for a tab the current user cannot access.
      if (!this.visibleTabs.some(tab => tab.id === this.activeTab)) {
        return null;
      }
      const componentMap = {
        home: 'HomePage',
        requests: 'RequestsPage',
        services: 'SettingsServices',
        jobs: 'SettingsJobs',
        database: 'SettingsDatabase',
        ai_provider: 'SettingsAdvanced',
        approvals: 'SettingsAdvanced',
        system: 'SettingsAdvanced',
        webhooks: 'SettingsWebhooks',
        cleanup: 'SettingsCleanup',
        logs: 'LogsComponent',
        ai_search: 'AiSearchPage',
        users: 'UserManagement',
        profile: 'UserProfile',
      };
      return componentMap[this.activeTab] ?? null;
    },
    activeTabSection() {
      return this.tabs.find(tab => tab.id === this.activeTab)?.section;
    },
    activeTab() {
      const requested = this.normalizeTabId(this.$route.params.tab);
      if (requested && this.visibleTabs.some(tab => tab.id === requested)) return requested;
      return this.visibleTabs[0]?.id ?? 'requests';
    },
    navGroups() {
      return [
        { label: '', tabs: this.visibleTabs.filter(tab => tab.group === 'main') },
        { label: 'Settings', tabs: this.visibleTabs.filter(tab => tab.group === 'settings') },
        { label: 'System', tabs: this.visibleTabs.filter(tab => tab.group === 'system') },
      ].filter(group => group.tabs.length);
    },
    quickTabs() {
      return this.visibleTabs.filter(tab => tab.group === 'main');
    },
  },
  watch: {
    'config.ENABLE_VISUAL_EFFECTS': {
      immediate: true,
      handler(newValue) {
        if (newValue === false) {
          document.body.classList.add('no-blur');
        } else {
          document.body.classList.remove('no-blur');
        }
      }
    }
  },
  async mounted() {
    try {
      // Ensure auth is fully initialized before making protected API calls
      const { waitForAuthReady } = await import("@/composables/useAuth");
      await waitForAuthReady();

      await this.fetchMe();

      if (!this.currentUser) {
        return;
      }

      if (this.currentUser?.role === 'admin') {
        await this.loadConfig();
      }

      this.loadRequestCount();

      // Auto-start tour on first visit or when ?tour=1 is in the URL
      const tourDone = localStorage.getItem(TOUR_STORAGE_KEY);
      const tourForced = window.location.search.includes('tour=1');
      if (!tourDone || tourForced) {
        setTimeout(() => { this.showTour = true; }, 900);
      }
    } catch (error) {
      if (error?.response?.status !== 403) {
        console.error('Error during component mount:', error);
      }
      this.isLoading = false;
    }
  },
  methods: {
    normalizeTabId(tabId) {
      if (!tabId) return '';
      if (tabId === 'suggestions') return 'requests';
      // The Advanced page was split into its own sections.
      if (tabId === 'advanced') return 'ai_provider';
      if (tabId === 'ai-search') {
        return 'ai_search';
      }
      return tabId;
    },

    async fetchMe() {
      try {
        const response = await axios.get('/api/auth/me', {
          withCredentials: true,
          timeout: 10000,
        });
        this.currentUser = response.data;
        return this.currentUser;
      } catch {
        this.currentUser = null;

        // In local bypass mode there may be no JWT token; rely on public
        // auth status to avoid an incorrect redirect loop to /login.
        try {
          const statusRes = await axios.get('/api/auth/status', {
            _skipAuth: true,
            timeout: 5000,
          });

          if (statusRes?.data?.authenticated) {
            const retryRes = await axios.get('/api/auth/me', {
              withCredentials: true,
              timeout: 10000,
            });
            this.currentUser = retryRes.data;
            return this.currentUser;
          }
        } catch {
          // Fall through to login redirect below when status/me cannot be resolved.
        }

        this.$router.push('/login');
        return null;
      }
    },
    async handleLogout() {
      await this.logout();
      this.$router.push('/login');
    },
    restartTour() {
      localStorage.removeItem(TOUR_STORAGE_KEY);
      this.showTour = true;
    },
    async loadConfig() {
      this.loadingMessage = 'Loading configuration...';
      this.isLoading = true;
      try {
        const response = await axios.get('/api/config/fetch', {
          timeout: 10000 // 10 second timeout
        });
        this.config = response.data;
      } catch (error) {
        if (error?.response?.status === 403) {
          return;
        }
        this.$toast.open({
          message: 'Failed to load configuration',
          type: 'error',
          duration: 5000,
          position: 'top-right'
        });
        console.error('Error loading config:', error);
        if (error.code === 'ECONNABORTED') {
          this.$toast.open({
            message: 'Configuration loading timed out. Please check your connection.',
            type: 'warning',
            duration: 5000,
            position: 'top-right'
          });
        }
      } finally {
        this.isLoading = false;
      }
    },

    async loadRequestCount() {
      try {
        const jobs = await axios.get('/api/jobs', { timeout: 5000 });
        if (!(jobs.data.jobs || []).some(job => job.delivery_mode === 'manual')) {
          this.requestCount = 0;
          return;
        }
        const response = await axios.get('/api/automation/requests/workflow', {
          params: { status: 'awaiting_approval', page: 1, per_page: 1 },
          timeout: 5000 // 5 second timeout
        });
        this.requestCount = response.data.total || 0;
      } catch (error) {
        console.error('Error loading request count:', error);
      }
    },

    async showChangelog() {
      this.showChangelogModal = true;
      this.changelogError = null;
      
      if (!this.changelogData) {
        this.isLoadingChangelog = true;
        try {
          // Get release info from GitHub API
          const response = await getReleaseByTag(this.currentVersion);
          
          if (response.data && response.data.body) {
            // Convert markdown to basic HTML
            this.changelogData = this.parseMarkdown(response.data.body);
          } else {
            this.changelogData = null;
          }
        } catch (error) {
          console.error('Error fetching changelog:', error);
          this.changelogError = 'Failed to load changelog from GitHub. Please check your internet connection.';
        } finally {
          this.isLoadingChangelog = false;
        }
      }
    },

    parseMarkdown(markdown) {
      if (!markdown) return '';

      // Escape HTML entities first to prevent XSS
      const escaped = markdown
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');

      // Basic markdown to HTML conversion (on escaped input)
      return escaped
        // Headers
        .replace(/^### (.*$)/gim, '<h4>$1</h4>')
        .replace(/^## (.*$)/gim, '<h3>$1</h3>')
        .replace(/^# (.*$)/gim, '<h2>$1</h2>')
        // Bold
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // Italic
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // Links (href is already entity-encoded from the escape step)
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
        // Line breaks
        .replace(/\n/g, '<br>')
        // Lists (basic)
        .replace(/^- (.+)$/gim, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    },

    async saveSection({ section, data }) {
      this.loadingMessage = `Saving ${section} settings...`;
      this.isLoading = true;
      const oldSubpath = (this.config.SUBPATH || '').replace(/\/$/, '');
      try {
        await axios.post(`/api/config/section/${section}`, data);
        Object.assign(this.config, data);

        // After saving advanced settings, sync use_llm flag on all recommendation jobs
        if (section === 'advanced' && 'ENABLE_ADVANCED_ALGORITHM' in data) {
          axios.post('/api/jobs/sync-ai-setting').catch(() => {});
        }

        // If SUBPATH changed, redirect the browser to the new base URL so the
        // router re-initialises with the correct history base.
        if (section === 'advanced' && 'SUBPATH' in data) {
          const newSubpath = (data.SUBPATH || '').replace(/\/$/, '');
          if (newSubpath !== oldSubpath) {
            this.$toast.open({
              message: 'Settings saved! Redirecting to new base URL…',
              type: 'success',
              duration: 2000,
              position: 'top-right'
            });
            setTimeout(() => {
              window.location.href = (newSubpath || '') + '/';
            }, 1500);
            return;
          }
        }

        this.$toast.open({
          message: `Settings saved successfully!`,
          type: 'success',
          duration: 3000,
          position: 'top-right'
        });
      } catch (error) {
        this.$toast.open({
          message: `Failed to save settings, see logs for details.`,
          type: 'error',
          duration: 5000,
          position: 'top-right'
        });
        console.error('Error saving section:', error);
      } finally {
        this.isLoading = false;
      }
    },
    async testConnection(service, config) {
      this.testingConnections[service] = true;
    
      try {
        let endpoint = '';
        let payload = {};
      
        switch (service) {
          case 'tmdb':
            endpoint = '/api/tmdb/test';
            payload = { api_key: config.api_key };
            break;
          case 'plex':
            endpoint = '/api/plex/test';
            payload = { token: config.token, api_url: config.api_url };
            break;
          case 'jellyfin':
            endpoint = '/api/jellyfin/test';
            payload = { 
              api_url: config.api_url,
              token: config.token 
            };
            break;
          case 'emby':
            endpoint = '/api/jellyfin/test';
            payload = { 
              api_url: config.api_url,
              token: config.token 
            };
            break;
          case 'seer':
            endpoint = '/api/seer/test';
            payload = { 
              api_url: config.api_url, 
              token: config.token 
            };
            break;
          case 'database':
            endpoint = '/api/config/test-db-connection';
            payload = {
              DB_TYPE: config.DB_TYPE,
              DB_HOST: config.DB_HOST,
              DB_PORT: config.DB_PORT,
              DB_NAME: config.DB_NAME,
              DB_USER: config.DB_USER,
              DB_PASSWORD: config.DB_PASSWORD,
            };
            break;
          default:
            throw new Error('Unknown service');
        }
      
        const response = await axios.post(endpoint, payload);
      
        if (this.$toast) {
          this.$toast.success(
            response.data.message || `${service.toUpperCase()} connection successful!`,
            {
              position: 'top-right',
              duration: 3000
            }
          );
        } else {
          alert(response.data.message || `${service.toUpperCase()} connection successful!`);
        }
      
        return response.data;
      
      } catch (error) {
        console.error(`${service} connection test failed:`, error);
      
        let errorMessage;
      
        if (error.response) {
          const status = error.response.status;
          const data = error.response.data;
        
          if (status === 400) {
            errorMessage = data?.message || 'Invalid credentials or server unreachable. Please check your URL and token.';
          } else if (status === 401) {
            errorMessage = 'Invalid authentication token. Please check your API token.';
          } else if (status === 404) {
            errorMessage = 'Server not found. Please check your URL.';
          } else if (status === 500) {
            errorMessage = 'Server error. Please check server logs.';
          } else if (status === 503) {
            errorMessage = 'Service unavailable. The server might be down.';
          } else {
            errorMessage = data?.message || `Error ${status}: Connection failed`;
          }
        } else if (error.request) {
          errorMessage = 'No response from server. Check your network connection and server URL.';
        } else {
          errorMessage = error.message || 'Request configuration error';
        }
      
        if (this.$toast) {
          this.$toast.error(errorMessage, {
            position: 'top-right',
            duration: 5000
          });
        } else {
          alert(`Error: ${errorMessage}`);
        }
      
        return {
          status: 'error',
          message: errorMessage
        };
      
      } finally {
        this.testingConnections[service] = false;
      }
    },
    getServiceStatus() {
      const service = this.config.SELECTED_SERVICE;
      if (!service) return 'status-disconnected';
      
      if (service === 'plex' && this.config.PLEX_TOKEN) return 'status-connected';
      if ((service === 'jellyfin' || service === 'emby') && this.config.JELLYFIN_TOKEN) return 'status-connected';
      
      return 'status-warning';
    },

    getServiceIcon() {
      const icons = {
        plex: 'fas fa-play-circle',
        jellyfin: 'fas fa-server',
        emby: 'fas fa-server',
      };
      return icons[this.config.SELECTED_SERVICE] || 'fas fa-question-circle';
    },

    goToDashboard() {
      this.$router.push({ name: 'Home' });
    },

    async confirmExportConfig() {
      const includeSecrets = this.exportIncludeSecrets;
      this.showExportModal = false;
      this.exportIncludeSecrets = false;
      await this.exportConfig(includeSecrets);
    },

    async exportConfig(includeSecrets = false) {
      this.loadingMessage = 'Exporting configuration...';
      this.isLoading = true;
    
      try {
        const response = await exportConfig(includeSecrets);
        const configData = response.data;
      
        const blob = new Blob(
          [JSON.stringify(configData, null, 2)],
          { type: 'application/json' }
        );
      
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `suggestarr-config-${new Date().toISOString().split('T')[0]}.json`;
        link.click();
        URL.revokeObjectURL(url);
      
        const warnings = configData.warnings || [];
        this.$toast.open({
          message: warnings.length
            ? warnings[0]
            : 'Configuration exported successfully!',
          type: warnings.length ? 'warning' : 'success',
          duration: warnings.length ? 8000 : 3000,
          position: 'top-right'
        });
      
      } catch (error) {
        this.$toast.open({
          message: 'Failed to export configuration',
          type: 'error',
          duration: 5000,
          position: 'top-right'
        });
      
        console.error('Error exporting config:', error);
      } finally {
        this.isLoading = false;
      }
    },

    importConfig() {
      this.$refs.fileInput.click();
    },

    async handleFileImport(event) {
      const file = event.target.files[0];
      if (!file) return;

      this.loadingMessage = 'Importing configuration...';
      this.isLoading = true;

      try {
        const text = await file.text();
        const configData = JSON.parse(text);

        await importConfig(configData);

        await this.loadConfig();

        this.$toast.open({
          message: 'Configuration imported successfully!',
          type: 'success',
          duration: 3000,
          position: 'top-right',
        });
      } catch (error) {
        this.$toast.open({
          message: 'Failed to import configuration',
          type: 'error',
          duration: 5000,
          position: 'top-right',
        });
        console.error('Error importing config:', error);
      } finally {
        this.isLoading = false;
        event.target.value = '';
      }
    },

    async confirmReset() {
      this.showResetModal = false;
      this.loadingMessage = 'Resetting configuration...';
      this.isLoading = true;

      try {
        await axios.post('/api/config/reset');
        this.$toast.open({
          message: 'Configuration reset successfully!',
          type: 'success',
          duration: 3000,
          position: 'top-right'
        });

        setTimeout(() => {
          this.$router.push({ name: 'Setup' });
        }, 1000);
      } catch (error) {
        this.$toast.open({
          message: 'Failed to reset configuration',
          type: 'error',
          duration: 5000,
          position: 'top-right'
        });
        console.error('Error resetting config:', error);
      } finally {
        this.isLoading = false;
      }
    },
  },
};
</script>
