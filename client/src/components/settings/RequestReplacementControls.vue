<template>
  <div class="mt-4 border-t border-edge pt-4">
    <button type="button" class="ui-btn" :disabled="disabled || !enabled || running" @click="run">
      <i aria-hidden="true" class="fas fa-sync-alt" :class="{ 'fa-spin': running }"></i>
      {{ running ? 'Checking…' : 'Check rejections now' }}
    </button>
    <p v-if="disabled" class="m-0 mt-2 text-xs text-ink-4">Save your changes before checking rejections.</p>
    <p v-if="summary" role="status" class="m-0 mt-3 text-sm text-ink-3">{{ summary }}</p>
    <p v-if="runError" role="alert" class="ui-alert-bad mt-3">{{ runError }}</p>
    <details class="mt-4 rounded-ctl border border-edge bg-panel-2/40">
      <summary class="cursor-pointer px-3 py-2 text-sm text-ink-2">Recent replacement decisions</summary>
      <div class="border-t border-edge p-3">
        <button type="button" class="ui-btn mb-3 h-8 px-3 text-xs" :disabled="loading" @click="loadLog">Refresh</button>
        <p v-if="logError" role="alert" class="ui-alert-bad">{{ logError }}</p>
        <p v-if="loading" role="status" class="m-0 text-sm text-ink-4">Loading decisions…</p>
        <p v-else-if="!log.length && !logError" class="m-0 text-sm text-ink-4">No decisions recorded yet.</p>
        <ul v-else class="m-0 max-h-64 list-none space-y-2 overflow-y-auto p-0" aria-label="Request replacement log">
          <li v-for="entry in log" :key="entry.delivery_id" class="rounded-ctl bg-panel-2 p-3 text-sm">
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-ink">
              <span>Seerr #{{ entry.seer_request_id }}</span>
              <span class="text-xs text-ink-3">{{ entry.media_type }} · TMDb {{ entry.tmdb_id }}</span>
              <span class="ml-auto rounded-md bg-raised px-2 py-0.5 text-xs">{{ entry.status }}</span>
            </div>
            <p class="m-0 mt-2 break-words text-xs text-ink-3">{{ entry.reason }}<span v-if="entry.replacement_delivery_id"> · Alternative #{{ entry.replacement_delivery_id }}</span></p>
            <time class="mt-1 block text-xs text-ink-4">{{ entry.checked_at }}</time>
          </li>
        </ul>
      </div>
    </details>
  </div>
</template>

<script>
import { getRequestReplacementLog, runRequestReplacements } from '@/api/api.js';

export default {
  name: 'RequestReplacementControls',
  props: { enabled: Boolean, disabled: Boolean },
  data() {
    return { log: [], logError: '', runError: '', loading: false, running: false, summary: '' };
  },
  mounted() {
    this.loadLog();
  },
  methods: {
    async loadLog() {
      this.loading = true;
      this.logError = '';
      try {
        const { data } = await getRequestReplacementLog();
        this.log = data.log || [];
      } catch (error) {
        this.logError = error.response?.data?.message || 'Unable to fetch replacement log.';
      } finally {
        this.loading = false;
      }
    },
    async run() {
      if (this.running || this.disabled || !this.enabled) return;
      this.running = true;
      this.runError = '';
      try {
        const { data } = await runRequestReplacements();
        const r = data.result;
        this.summary = `Requests checked: ${r.checked}. Alternatives queued: ${r.queued}. Deferred: ${r.pending}. Without candidates: ${r.exhausted}. Errors: ${r.errors}.`;
        if (r.errors) this.$toast.error('Check finished with errors. See the server log.');
        else this.$toast.success('Rejection check complete.');
        await this.loadLog();
      } catch (error) {
        this.runError = error.response?.data?.message || 'Replacement check failed.';
        this.$toast.error(this.runError);
      } finally {
        this.running = false;
      }
    },
  },
};
</script>
