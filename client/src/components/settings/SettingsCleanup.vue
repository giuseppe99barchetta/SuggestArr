<template>
  <div class="cleanup-page">
    <div class="section-header">
      <h2><i class="fas fa-broom"></i> Cleanup Automation</h2>
      <p>Automatically delete SuggestArr requests and their files when the item has not been favorited (Plex heart) within a grace period.</p>
    </div>

    <div class="warning-banner">
      <i class="fas fa-exclamation-triangle"></i>
      <div class="warning-content">
        <strong>Destructive action</strong>
        <span>When enabled and not in dry-run, this will delete media files via Radarr/Sonarr (through Seer). Always run in dry-run first to verify the candidate list.</span>
      </div>
    </div>

    <div v-if="loading" class="placeholder">Loading…</div>

    <div v-else class="settings-card">
      <label class="toggle-option">
        <span class="toggle-label">
          <i class="fas fa-power-off"></i>
          Enable cleanup automation
          <span class="toggle-hint">Runs daily at 04:15 server-time. When off, no scans happen.</span>
        </span>
        <div class="toggle-switch" :class="{ on: form.enabled }" @click="form.enabled = !form.enabled">
          <div class="toggle-knob"></div>
        </div>
      </label>

      <label class="toggle-option">
        <span class="toggle-label">
          <i class="fas fa-vial"></i>
          Dry-run mode
          <span class="toggle-hint">Logs what would be deleted without actually touching files. Strongly recommended before flipping to real deletion.</span>
        </span>
        <div class="toggle-switch" :class="{ on: form.dry_run }" @click="form.dry_run = !form.dry_run">
          <div class="toggle-knob"></div>
        </div>
      </label>

      <div class="number-option">
        <span class="toggle-label">
          <i class="fas fa-hourglass-half"></i>
          Grace period (days)
          <span class="toggle-hint">If a requested item has not been favorited (Plex heart) within this many days of being requested, it becomes a deletion candidate.</span>
        </span>
        <input v-model.number="form.grace_days" type="number" min="1" max="365" class="number-input" />
      </div>

      <div class="actions-row">
        <button class="btn btn-primary" :disabled="saving" @click="save">
          <i :class="saving ? 'fas fa-spinner fa-spin' : 'fas fa-save'"></i>
          {{ saving ? 'Saving…' : 'Save settings' }}
        </button>
        <button class="btn" :disabled="running" @click="runNow(true)">
          <i :class="running && lastTrigger === 'dry' ? 'fas fa-spinner fa-spin' : 'fas fa-vial'"></i>
          Run now (dry-run)
        </button>
        <button class="btn btn-danger" :disabled="running || !form.enabled" @click="runNow(false)" title="Performs real deletions">
          <i :class="running && lastTrigger === 'real' ? 'fas fa-spinner fa-spin' : 'fas fa-trash-alt'"></i>
          Run now (real)
        </button>
      </div>

      <div v-if="lastResult" class="result-banner" :class="{ ok: lastResult.status === 'success', err: lastResult.status === 'error' }">
        <i :class="lastResult.status === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle'"></i>
        <span>{{ lastResult.message }}</span>
      </div>

      <div v-if="settings && settings.last_run_at" class="last-run-info">
        <span><strong>Last run:</strong> {{ formatTs(settings.last_run_at) }} · {{ settings.last_run_status || '—' }}</span>
        <div v-if="settings.last_run_summary" class="last-run-summary">{{ settings.last_run_summary }}</div>
      </div>
    </div>

    <div class="settings-card">
      <div class="card-header-row">
        <h3><i class="fas fa-history"></i> Audit log</h3>
        <button class="btn btn-link" @click="loadLog" :disabled="loadingLog">
          <i :class="loadingLog ? 'fas fa-spinner fa-spin' : 'fas fa-sync'"></i> Refresh
        </button>
      </div>
      <div v-if="!log.length" class="placeholder">No cleanup actions logged yet.</div>
      <table v-else class="log-table">
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
          <tr v-for="row in log" :key="row.id" :class="actionClass(row.action)">
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
    </div>
  </div>
</template>

<script>
import { getCleanupSettings, setCleanupSettings, runCleanupNow, getCleanupLog } from '@/api/api.js';

export default {
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
      lastResult: null,
    };
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
      } catch (err) {
        // non-fatal
      } finally {
        this.loadingLog = false;
      }
    },

    formatTs(ts) {
      if (!ts) return '—';
      try {
        return new Date(ts.endsWith('Z') ? ts : ts + 'Z').toLocaleString();
      } catch {
        return ts;
      }
    },

    actionClass(action) {
      if (action === 'deleted' || action === 'would_delete') return 'row-delete';
      if (action === 'kept_favorited') return 'row-kept';
      if (action === 'error' || action === 'delete_failed') return 'row-error';
      return '';
    },
  },

  mounted() {
    this.loadSettings();
    this.loadLog();
  },
};
</script>

<style scoped>
.cleanup-page { padding: 0; }
.section-header h2 { font-size: 1.6rem; margin-bottom: 0.25rem; }
.section-header p { color: var(--color-text-muted, #aaa); }

.warning-banner {
  display: flex; gap: 12px; align-items: flex-start;
  background: rgba(231, 138, 0, 0.1); border: 1px solid rgba(231, 138, 0, 0.4);
  padding: 12px; border-radius: 8px; margin: 16px 0;
}
.warning-banner i { color: #e78a00; font-size: 1.1rem; margin-top: 2px; }
.warning-content strong { display: block; margin-bottom: 2px; }

.settings-card {
  background: var(--color-card, #2a2a2a);
  border: 1px solid var(--color-border, #444);
  border-radius: 8px; padding: 16px; margin-bottom: 20px;
}

.toggle-option, .number-option {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 0; border-bottom: 1px solid var(--color-border-soft, #333);
}
.toggle-option:last-of-type, .number-option:last-of-type { border-bottom: none; }
.toggle-label { display: flex; flex-direction: column; gap: 4px; max-width: 70%; }
.toggle-hint { color: var(--color-text-muted, #888); font-size: 0.85rem; }

.number-input {
  width: 90px; padding: 6px 8px;
  background: var(--color-bg, #1f1f1f); border: 1px solid var(--color-border, #444);
  border-radius: 6px; color: var(--color-text-primary, white);
}

.actions-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
.btn {
  padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 0.9rem;
  border: 1px solid var(--color-border, #444); background: transparent; color: var(--color-text-primary, #ddd);
  display: inline-flex; align-items: center; gap: 6px;
}
.btn:hover:not(:disabled) { border-color: #888; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3498db; border-color: #3498db; color: white; }
.btn-danger { background: #c0392b; border-color: #c0392b; color: white; }
.btn-link { background: transparent; border: none; color: #3498db; padding: 4px 8px; }

.result-banner {
  margin-top: 12px; padding: 10px; border-radius: 6px;
  display: flex; gap: 8px; align-items: center;
}
.result-banner.ok { background: rgba(46, 204, 113, 0.12); border: 1px solid #2ecc71; color: #2ecc71; }
.result-banner.err { background: rgba(231, 76, 60, 0.12); border: 1px solid #e74c3c; color: #e74c3c; }

.last-run-info { margin-top: 12px; font-size: 0.9rem; color: var(--color-text-muted, #aaa); }
.last-run-summary { margin-top: 4px; font-family: monospace; font-size: 0.82rem; }

.card-header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.placeholder { color: var(--color-text-muted, #888); padding: 8px 0; font-style: italic; }

.log-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.log-table th, .log-table td {
  text-align: left; padding: 6px 8px;
  border-bottom: 1px solid var(--color-border-soft, #333);
}
.log-table th { color: var(--color-text-muted, #aaa); font-weight: 600; }
.log-table .row-delete { color: #e67e22; }
.log-table .row-kept { color: #2ecc71; }
.log-table .row-error { color: #e74c3c; }
</style>
