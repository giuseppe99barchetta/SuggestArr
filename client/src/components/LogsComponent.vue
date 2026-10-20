<template>
  <div class="flex flex-col gap-4">
    <PageHeader v-if="!embedded" title="Logs" subtitle="What SuggestArr is doing right now. Filter by message or severity to track down a problem." />

    <div class="flex flex-wrap items-center gap-3">
      <label class="relative min-w-[220px] flex-[1_1_280px]">
        <span class="sr-only">Filter logs by message</span>
        <i aria-hidden="true" class="fas fa-search pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs text-ink-4"></i>
        <input v-model="filterText" type="search" placeholder="Filter by message…" class="ui-input pl-9" />
      </label>

      <div role="radiogroup" aria-label="Severity" class="flex rounded-ctl border border-edge-strong bg-canvas p-1">
        <button
          v-for="option in severityOptions"
          :key="option.value"
          type="button"
          role="radio"
          :aria-checked="selectedSeverity === option.value ? 'true' : 'false'"
          class="h-8 cursor-pointer rounded-[7px] border-0 px-3 text-[13px] font-semibold"
          :class="selectedSeverity === option.value ? 'bg-raised text-ink' : 'bg-transparent text-ink-3 hover:text-ink'"
          @click="selectedSeverity = option.value"
        >{{ option.label }}</button>
      </div>

      <span class="ml-auto text-[13px] text-ink-3" aria-live="polite">
        {{ visibleLogs.length }}<template v-if="visibleLogs.length < filteredLogs.length"> of {{ filteredLogs.length }}</template> rows
      </span>
      <button type="button" class="ui-btn h-[42px]" :aria-pressed="autoUpdate ? 'true' : 'false'" @click="toggleAutoUpdate">
        <span v-if="autoUpdate" class="h-2 w-2 animate-pulse rounded-full bg-good"></span>
        <i v-else aria-hidden="true" class="fas fa-play text-xs"></i>
        {{ autoUpdate ? 'Live' : 'Paused' }}
      </button>
    </div>

    <div class="overflow-hidden rounded-card border border-edge bg-panel">
      <div ref="scroller" class="overflow-auto" :class="embedded ? 'max-h-[60vh]' : 'max-h-[calc(100dvh-260px)] min-h-[320px]'" @scroll="handleScroll">
        <table class="w-full border-collapse font-mono text-xs">
          <thead class="sticky top-0 z-[1] bg-panel-2 text-left font-sans text-[11px] font-bold uppercase tracking-wider text-ink-4">
            <tr>
              <th class="whitespace-nowrap px-4 py-2.5 font-bold">Time</th>
              <th class="px-2 py-2.5 font-bold">Level</th>
              <th class="px-2 py-2.5 font-bold max-sm:hidden">Source</th>
              <th class="w-full px-2 py-2.5 font-bold">Message</th>
              <th class="px-4 py-2.5"><span class="sr-only">Copy</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(log, index) in visibleLogs" :key="index" class="group border-t border-edge align-top hover:bg-panel-2" :class="rowTone(log.severity)">
              <td class="whitespace-nowrap py-2 pl-4 pr-2 text-ink-4 max-sm:pl-3" :title="log.dateTime">{{ log.time }}</td>
              <td class="px-2 py-2"><span class="inline-block min-w-[62px] rounded px-1.5 py-px text-center text-[10px] font-bold" :class="levelTone(log.severity)">{{ log.severity }}</span></td>
              <td class="max-w-[180px] truncate px-2 py-2 text-ink-3 max-sm:hidden" :title="log.tag">{{ log.tag }}</td>
              <td class="px-2 py-2 leading-relaxed break-words whitespace-pre-wrap text-ink-2">{{ log.message }}</td>
              <td class="py-1 pl-2 pr-3">
                <button type="button" class="h-7 w-7 cursor-pointer rounded-[6px] border-0 bg-transparent text-ink-4 opacity-0 hover:bg-raised hover:text-ink focus-visible:opacity-100 group-hover:opacity-100" aria-label="Copy log line" title="Copy log line" @click="copyLog(log)">
                  <i aria-hidden="true" class="fas fa-copy"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <p v-if="loadingMore" class="m-0 py-4 text-center text-[13px] text-ink-3"><i aria-hidden="true" class="fas fa-spinner fa-spin mr-2"></i>Loading more…</p>
        <div v-if="!visibleLogs.length" class="flex flex-col items-center gap-2 py-14 text-ink-3">
          <i aria-hidden="true" class="fas fa-inbox text-2xl text-ink-4"></i>
          <p class="m-0 text-sm">{{ logs.length ? 'No logs match these filters.' : 'No logs yet.' }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import PageHeader from '@/components/ui/PageHeader.vue';
import axios from 'axios';
import { parseLogs } from '@/utils/logs.js';
import { copyText } from '@/utils/clipboard.js';

const BATCH_SIZE = 100;

const LEVEL_TONES = {
  DEBUG: 'bg-raised text-ink-3',
  INFO: 'bg-notice/15 text-notice',
  WARNING: 'bg-caution/15 text-caution',
  ERROR: 'bg-bad/15 text-bad',
  CRITICAL: 'bg-bad/15 text-bad',
};

export default {
  name: 'LogsComponent',
  components: { PageHeader },
  // The dashboard shell passes props this page does not declare.
  inheritAttrs: false,
  props: {
    // True inside the setup wizard's log dialog, which has its own title.
    embedded: { type: Boolean, default: false },
  },
  data() {
    return {
      logs: [],
      filterText: '',
      selectedSeverity: '',
      autoUpdate: true,
      updateInterval: null,
      displayLimit: BATCH_SIZE,
      hasMoreLogs: true,
      fetchingLogs: false,
      loadingMore: false,
      severityOptions: [
        { value: '', label: 'All' },
        { value: 'DEBUG', label: 'Debug' },
        { value: 'INFO', label: 'Info' },
        { value: 'WARNING', label: 'Warning' },
        { value: 'ERROR', label: 'Error' },
      ],
    };
  },
  computed: {
    filteredLogs() {
      const text = this.filterText.trim().toLowerCase();
      if (!text && !this.selectedSeverity) return this.logs;
      return this.logs.filter(log =>
        (!text || log.message.toLowerCase().includes(text)) &&
        (!this.selectedSeverity || log.severity === this.selectedSeverity));
    },
    visibleLogs() {
      return this.filteredLogs.slice(0, this.displayLimit);
    },
  },
  watch: {
    filterText() { this.displayLimit = BATCH_SIZE; },
    selectedSeverity() { this.displayLimit = BATCH_SIZE; },
  },
  mounted() {
    this.startAutoUpdate();
  },
  beforeUnmount() {
    this.stopAutoUpdate();
  },
  methods: {
    /**
     * Fetches newest-first logs. A refresh reloads everything already paged in,
     * so the live update does not throw away what the user scrolled to.
     */
    async fetchLogs({ more = false } = {}) {
      if (this.fetchingLogs || (more && !this.hasMoreLogs)) return;
      this.fetchingLogs = true;
      const limit = more ? BATCH_SIZE : Math.max(BATCH_SIZE, this.logs.length);
      const offset = more ? this.logs.length : 0;
      try {
        const response = await axios.get('/api/logs', { params: { limit, offset } });
        const page = parseLogs(response.data).reverse();
        this.hasMoreLogs = response.data.length === limit;
        this.logs = more ? [...this.logs, ...page] : page;
      } catch (error) {
        console.error('Error fetching logs:', error);
      } finally {
        this.fetchingLogs = false;
      }
    },
    async handleScroll() {
      const el = this.$refs.scroller;
      if (!el || el.scrollTop + el.clientHeight < el.scrollHeight * 0.9 || this.loadingMore) return;
      if (this.displayLimit < this.filteredLogs.length) {
        this.displayLimit += BATCH_SIZE;
        return;
      }
      if (!this.hasMoreLogs) return;
      this.loadingMore = true;
      await this.fetchLogs({ more: true });
      this.displayLimit += BATCH_SIZE;
      this.loadingMore = false;
    },
    levelTone(severity) {
      return LEVEL_TONES[severity] || LEVEL_TONES.DEBUG;
    },
    rowTone(severity) {
      return severity === 'ERROR' || severity === 'CRITICAL' ? 'bg-bad/[0.04]' : '';
    },
    async copyLog(log) {
      const text = `${log.dateTime} - ${log.tag} - ${log.severity} - ${log.message}`;
      if (await copyText(text)) this.$toast.success('Log line copied.');
      else this.$toast.error('Failed to copy log to clipboard.');
    },
    startAutoUpdate() {
      this.fetchLogs();
      this.updateInterval = setInterval(this.fetchLogs, 5000);
      this.autoUpdate = true;
    },
    stopAutoUpdate() {
      clearInterval(this.updateInterval);
      this.updateInterval = null;
      this.autoUpdate = false;
    },
    toggleAutoUpdate() {
      if (this.autoUpdate) this.stopAutoUpdate();
      else this.startAutoUpdate();
    },
  },
};
</script>
