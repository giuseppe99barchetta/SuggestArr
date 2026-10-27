<template>
  <div class="flex flex-col gap-5">
    <PageHeader title="Cleanup" subtitle="Delete SuggestArr requests and their files when the title was not favorited in your media server within a grace period." />

    <div role="alert" class="flex items-start gap-3 rounded-card border border-caution/40 bg-caution/10 px-4 py-3.5">
      <i aria-hidden="true" class="fas fa-exclamation-triangle mt-0.5 text-caution"></i>
      <p class="m-0 text-sm text-ink-2"><strong class="block text-ink">Destructive action</strong>When enabled and not in dry-run, this asks Seer to delete the matched media files. Always run in dry-run first to verify the candidate list.</p>
    </div>

    <p v-if="loading" class="m-0 py-2 text-sm italic text-ink-4">Loading…</p>

    <SectionCard v-else icon="fas fa-broom" title="Cleanup automation" description="Runs daily at 04:15 server-time.">
      <div class="flex flex-col gap-2.5">
        <button
          v-for="toggle in toggles"
          :key="toggle.key"
          type="button"
          role="switch"
          :aria-checked="form[toggle.key] ? 'true' : 'false'"
          class="flex cursor-pointer items-center gap-3 rounded-ctl border border-edge bg-panel-2 p-3.5 text-left hover:border-edge-strong"
          @click="form[toggle.key] = !form[toggle.key]"
        >
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-ctl bg-raised text-ink-3"><i aria-hidden="true" :class="toggle.icon"></i></span>
          <span class="flex min-w-0 flex-1 flex-col gap-0.5">
            <span class="text-sm font-semibold text-ink">{{ toggle.title }}</span>
            <span class="text-xs leading-snug text-ink-4">{{ toggle.hint }}</span>
          </span>
          <span class="relative inline-block h-[22px] w-10 shrink-0 rounded-full transition-colors" :class="form[toggle.key] ? 'bg-brand' : 'bg-edge-strong'"><span class="absolute top-[3px] h-4 w-4 rounded-full bg-white transition-all" :class="form[toggle.key] ? 'left-[21px]' : 'left-[3px]'"></span></span>
        </button>

        <label class="flex items-center gap-3 rounded-ctl border border-edge bg-panel-2 p-3.5">
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-ctl bg-raised text-ink-3"><i aria-hidden="true" class="fas fa-hourglass-half"></i></span>
          <span class="flex min-w-0 flex-1 flex-col gap-0.5">
            <span class="text-sm font-semibold text-ink">Grace period (days)</span>
            <span class="text-xs leading-snug text-ink-4">If a requested item has not been favorited in Plex, Jellyfin, or Emby within this many days of being requested, it becomes a deletion candidate. Plex counts only a 5-star rating from the server owner's account; Jellyfin and Emby count favorites of the users selected in Connections (all users when none are selected).</span>
          </span>
          <input v-model.number="form.grace_days" type="number" min="1" max="365" class="ui-input h-9 w-20 shrink-0 px-2.5" />
        </label>
      </div>

      <div class="mt-4 flex flex-wrap gap-2">
        <button type="button" class="ui-btn-primary" :disabled="saving" @click="save">
          <i aria-hidden="true" :class="saving ? 'fas fa-spinner fa-spin' : 'fas fa-save'"></i>
          {{ saving ? 'Saving…' : 'Save settings' }}
        </button>
        <button type="button" class="ui-btn" :disabled="running" @click="runNow(true)">
          <i aria-hidden="true" :class="running && lastTrigger === 'dry' ? 'fas fa-spinner fa-spin' : 'fas fa-vial'"></i>
          Run now (dry-run)
        </button>
        <button type="button" class="ui-btn-danger" :disabled="running || !form.enabled" title="Performs real deletions" @click="runNow(false)">
          <i aria-hidden="true" :class="running && lastTrigger === 'real' ? 'fas fa-spinner fa-spin' : 'fas fa-trash-alt'"></i>
          Run now (real)
        </button>
      </div>

      <p v-if="lastResult" class="mt-3 flex items-center gap-2" :class="lastResult.status === 'success' ? 'ui-alert-good' : 'ui-alert-bad'">
        <i aria-hidden="true" :class="lastResult.status === 'success' ? 'fas fa-check-circle text-good' : 'fas fa-exclamation-circle text-bad'"></i>
        <span>{{ lastResult.message }}</span>
      </p>

      <div v-if="settings && settings.last_run_at" class="mt-3 text-sm text-ink-4">
        <span><strong>Last run:</strong> {{ formatTs(settings.last_run_at) }} · {{ settings.last_run_status || '—' }}</span>
        <div v-if="settings.last_run_summary" class="mt-1 font-mono text-[0.82rem]">{{ settings.last_run_summary }}</div>
      </div>
    </SectionCard>

    <section class="overflow-x-auto rounded-card border border-edge bg-panel p-5">
      <div class="mb-2 flex items-center justify-between gap-3">
        <button type="button" class="inline-flex cursor-pointer items-center gap-2.5 border-0 bg-transparent py-1 text-base font-semibold text-ink" :aria-expanded="(!logCollapsed).toString()" @click="logCollapsed = !logCollapsed">
          <i aria-hidden="true" :class="logCollapsed ? 'fas fa-chevron-right' : 'fas fa-chevron-down'"></i>
          <span class="inline-flex items-center gap-2"><i aria-hidden="true" class="fas fa-history"></i> Audit log</span>
          <span v-if="log.length" class="min-w-6 rounded-full bg-white/8 px-2 py-0.5 text-center text-[0.78rem] font-semibold text-ink-4">{{ log.length }}</span>
        </button>
        <button type="button" class="inline-flex cursor-pointer items-center gap-1.5 border-0 bg-transparent px-2 py-1 text-sm text-brand-ink disabled:opacity-50" :disabled="loadingLog" @click="loadLog">
          <i aria-hidden="true" :class="loadingLog ? 'fas fa-spinner fa-spin' : 'fas fa-sync'"></i> Refresh
        </button>
      </div>
      <p v-if="!logCollapsed && !log.length" class="m-0 py-2 text-sm italic text-ink-4">No cleanup actions logged yet.</p>
      <table v-else-if="!logCollapsed" class="w-full border-collapse text-[0.85rem] [&_td]:border-b [&_td]:border-edge [&_td]:px-2 [&_td]:py-1.5 [&_th]:border-b [&_th]:border-edge [&_th]:px-2 [&_th]:py-1.5 [&_th]:text-left [&_th]:font-semibold [&_th]:text-ink-4">
        <thead>
          <tr>
            <th>When</th>
            <th>Title</th>
            <th>Type</th>
            <th>Action</th>
            <th>Mode</th>
            <th>★</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in paginatedLog" :key="row.id" :class="actionClass(row.action)">
            <td>{{ formatTs(row.ran_at) }}</td>
            <td>{{ row.title || ('tmdb:' + row.tmdb_id) }}</td>
            <td>{{ row.media_type === 'tv' ? 'TV' : 'Movie' }}</td>
            <td>{{ row.action }}</td>
            <td>{{ row.was_dry_run ? 'dry' : 'real' }}</td>
            <td>{{ row.user_rating ?? '—' }}</td>
            <td>{{ row.reason }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!logCollapsed && totalLogPages > 1" class="mt-3 flex items-center justify-end gap-3 text-[0.85rem] text-ink-4">
        <button type="button" class="ui-btn h-8 px-3 text-[0.82rem]" :disabled="logPage <= 1" @click="logPage -= 1">
          <i aria-hidden="true" class="fas fa-chevron-left"></i>
          Previous
        </button>
        <span>Page {{ logPage }} of {{ totalLogPages }}</span>
        <button type="button" class="ui-btn h-8 px-3 text-[0.82rem]" :disabled="logPage >= totalLogPages" @click="logPage += 1">
          Next
          <i aria-hidden="true" class="fas fa-chevron-right"></i>
        </button>
      </div>
    </section>
  </div>
</template>

<script>
import PageHeader from '@/components/ui/PageHeader.vue';
import SectionCard from '@/components/ui/SectionCard.vue';
import { getCleanupSettings, setCleanupSettings, runCleanupNow, getCleanupLog } from '@/api/api.js';

export default {
  components: { PageHeader, SectionCard },
  name: 'SettingsCleanup',

  data() {
    return {
      loading: true,
      loadingLog: false,
      saving: false,
      running: false,
      lastTrigger: null,
      settings: null,
      form: { enabled: false, dry_run: true, grace_days: 7 },
      log: [],
      logCollapsed: true,
      logPage: 1,
      logPageSize: 25,
      lastResult: null,
      toggles: [
        { key: 'enabled', icon: 'fas fa-power-off', title: 'Enable cleanup automation', hint: 'When off, no scans happen.' },
        { key: 'dry_run', icon: 'fas fa-vial', title: 'Dry-run mode', hint: 'Logs which items would be sent to Seer for deletion without touching files. Strongly recommended before flipping to real deletion.' },
      ],
    };
  },

  computed: {
    totalLogPages() {
      return Math.max(1, Math.ceil(this.log.length / this.logPageSize));
    },

    paginatedLog() {
      const start = (this.logPage - 1) * this.logPageSize;
      return this.log.slice(start, start + this.logPageSize);
    },
  },

  methods: {
    async loadSettings() {
      this.loading = true;
      try {
        const res = await getCleanupSettings();
        this.settings = res.data.settings;
        this.form = {
          enabled: !!this.settings.enabled,
          dry_run: !!this.settings.dry_run,
          grace_days: Number(this.settings.grace_days) || 7,
        };
      } catch (err) {
        this.lastResult = { status: 'error', message: err.response?.data?.message || 'Failed to load settings.' };
      } finally {
        this.loading = false;
      }
    },

    async save() {
      this.saving = true;
      this.lastResult = null;
      try {
        const res = await setCleanupSettings(this.form);
        this.settings = res.data.settings;
        this.lastResult = { status: 'success', message: 'Settings saved.' };
      } catch (err) {
        this.lastResult = { status: 'error', message: err.response?.data?.message || 'Failed to save.' };
      } finally {
        this.saving = false;
      }
    },

    async runNow(dryRun) {
      if (this.running) return;
      this.running = true;
      this.lastTrigger = dryRun ? 'dry' : 'real';
      this.lastResult = null;
      try {
        const res = await runCleanupNow(dryRun);
        const r = res.data.result || {};
        this.lastResult = { status: 'success', message: `Run complete (${dryRun ? 'dry-run' : 'real'}): ${r.summary || r.message || 'done'}` };
        await this.loadSettings();
        await this.loadLog();
      } catch (err) {
        this.lastResult = { status: 'error', message: err.response?.data?.message || 'Run failed.' };
      } finally {
        this.running = false;
        this.lastTrigger = null;
      }
    },

    async loadLog() {
      this.loadingLog = true;
      try {
        const res = await getCleanupLog(200);
        this.log = res.data.log || [];
        if (this.logPage > this.totalLogPages) {
          this.logPage = this.totalLogPages;
        }
      } catch {
        // non-fatal
      } finally {
        this.loadingLog = false;
      }
    },

    formatTs(ts) {
      if (!ts) return '—';
      const raw = String(ts).trim();
      const hasTimezone = /(?:z|gmt|[+-]\d{2}:?\d{2})$/i.test(raw);
      const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T');
      const date = new Date(hasTimezone ? normalized : `${normalized}Z`);
      if (Number.isNaN(date.getTime())) {
        return raw;
      }
      return date.toLocaleString();
    },

    actionClass(action) {
      if (action === 'deleted' || action === 'would_delete') return 'text-caution';
      if (action === 'kept_favorited') return 'text-good';
      if (action === 'error' || action === 'delete_failed') return 'text-bad';
      return '';
    },
  },

  mounted() {
    this.loadSettings();
    this.loadLog();
  },
};
</script>
