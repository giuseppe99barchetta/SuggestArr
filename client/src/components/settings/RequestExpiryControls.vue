<template>
  <div class="mt-4 border-t border-edge pt-4">
    <div class="grid gap-2 sm:flex sm:flex-wrap">
      <button type="button" class="ui-btn" :disabled="disabled || !enabled || running" @click="run(true)">Preview now</button>
      <button type="button" class="ui-btn border-bad/40 bg-bad/10 text-bad hover:border-bad" :disabled="disabled || !enabled || dryRun || running" @click="run(false)">{{ running ? 'Running…' : 'Decline expired requests' }}</button>
    </div>
    <p v-if="disabled" class="mt-2 text-xs text-ink-4">Save your changes before running expiry.</p>
    <p v-if="summary" role="status" class="mt-3 text-sm text-ink-2">{{ summary }}</p>
    <details class="group mt-3 rounded-ctl border border-edge">
      <summary class="flex min-h-10 cursor-pointer list-none items-center gap-2 px-3 text-[13px] font-semibold text-ink-2 hover:text-ink [&::-webkit-details-marker]:hidden">
        <i aria-hidden="true" class="fas fa-chevron-right text-[10px] text-ink-4 group-open:rotate-90"></i>
        Activity log
        <span class="ml-auto text-xs font-normal tabular-nums text-ink-4">{{ log.length }} recent</span>
      </summary>
      <div class="border-t border-edge p-3">
        <div class="mb-3 flex items-center justify-between gap-3">
          <span class="text-xs text-ink-4">Latest expiry checks</span>
          <button type="button" class="ui-btn h-8 px-3 text-xs" :disabled="loading || running" @click="loadLog">Refresh log</button>
        </div>
        <p v-if="logError" role="alert" class="ui-alert-bad">{{ logError }}</p>
        <p v-if="loading" role="status" class="m-0 text-sm text-ink-4">Loading expiry log…</p>
        <p v-else-if="!log.length && !logError" class="m-0 py-3 text-center text-xs text-ink-4">No expiry actions logged yet.</p>
        <ul v-else class="m-0 max-h-64 list-none space-y-2 overflow-y-auto p-0" aria-label="Seerr request expiry log">
          <li v-for="entry in log" :key="entry.id" class="rounded-ctl bg-panel-2 p-3 text-sm">
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1 font-medium text-ink">
              <span>Seerr #{{ entry.seer_request_id }}</span>
              <span class="text-xs font-normal text-ink-3">{{ entry.media_type }} · TMDb {{ entry.tmdb_id }}</span>
              <span class="ml-auto rounded-md bg-raised px-2 py-0.5 text-xs text-ink-2">{{ entry.action }}{{ entry.dry_run ? ' (preview)' : '' }}</span>
            </div>
            <p class="m-0 mt-2 break-words text-xs text-ink-3">{{ entry.reason }}</p>
            <time class="mt-1 block text-xs tabular-nums text-ink-4">{{ entry.created_at }}</time>
          </li>
        </ul>
      </div>
    </details>
  </div>
</template>

<script>
import { getRequestExpiryLog, runRequestExpiry } from '@/api/api.js';

export default {
  name: 'RequestExpiryControls',
  props: {
    enabled: Boolean,
    dryRun: { type: Boolean, default: true },
    disabled: Boolean,
  },
  data() {
    return { log: [], loading: false, running: false, summary: '', logError: '' };
  },
  mounted() {
    this.loadLog();
  },
  methods: {
    async loadLog() {
      this.loading = true;
      this.logError = '';
      try {
        const { data } = await getRequestExpiryLog();
        this.log = data.log;
      } catch (error) {
        this.logError = error.response?.data?.message || 'Unable to fetch expiry log.';
      } finally {
        this.loading = false;
      }
    },
    async run(dryRun) {
      if (this.running || this.disabled || !this.enabled || (!dryRun && this.dryRun)) return;
      this.running = true;
      try {
        const { data } = await runRequestExpiry(dryRun);
        const r = data.result;
        this.summary = `${dryRun ? 'Preview' : 'Expiry'} (${r.status}): ${r.candidates} candidates, ${r.simulated} simulated, ${r.declined} declined, ${r.skipped} skipped, ${r.errors} errors.`;
        if (r.errors) this.$toast.error('Expiry finished with errors. Check the log.');
        else this.$toast.success('Expiry run complete.');
        await this.loadLog();
      } catch (error) {
        this.$toast.error(error.response?.data?.message || 'Request expiry failed.');
      } finally {
        this.running = false;
      }
    },
  },
};
</script>
