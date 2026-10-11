<template>
  <AppDialog
    width="max-w-4xl"
    title="Run history"
    icon="fas fa-history"
    :subtitle="history.length ? `${history.length} runs · ${successRate}% completed` : 'No runs yet'"
    body-class="p-0"
    @close="$emit('close')"
  >
    <div class="sticky top-0 z-[1] flex flex-wrap items-center gap-3 border-b border-edge bg-panel px-6 py-3 max-sm:px-4">
      <div role="radiogroup" aria-label="Status" class="flex max-w-full overflow-x-auto rounded-ctl border border-edge-strong bg-canvas p-1">
        <button
          v-for="option in statusOptions"
          :key="option.value"
          type="button"
          role="radio"
          :aria-checked="filterStatus === option.value ? 'true' : 'false'"
          class="h-8 shrink-0 cursor-pointer whitespace-nowrap rounded-[7px] border-0 px-3 text-[13px] font-semibold max-sm:px-2"
          :class="filterStatus === option.value ? 'bg-raised text-ink' : 'bg-transparent text-ink-3 hover:text-ink'"
          @click="filterStatus = option.value"
        >{{ option.label }} <span class="text-ink-4">{{ countFor(option.value) }}</span></button>
      </div>
      <select v-if="jobNames.length > 1" v-model="filterJob" class="ui-input h-10 w-auto min-w-[180px] flex-1 sm:flex-none" aria-label="Job">
        <option value="">All jobs</option>
        <option v-for="name in jobNames" :key="name" :value="name">{{ name }}</option>
      </select>
    </div>

    <ul v-if="paginatedHistory.length" class="m-0 list-none p-0">
      <li v-for="exec in paginatedHistory" :key="exec.id" class="border-b border-edge last:border-b-0">
        <component
          :is="exec.error_message ? 'button' : 'div'"
          :type="exec.error_message ? 'button' : null"
          :aria-expanded="exec.error_message ? String(expandedId === exec.id) : null"
          class="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 border-0 bg-transparent px-6 py-3 text-left text-sm max-sm:px-4"
          :class="exec.error_message ? 'cursor-pointer hover:bg-panel-2' : ''"
          @click="exec.error_message && toggle(exec.id)"
        >
          <span class="h-2.5 w-2.5 rounded-full" :class="statusTone(exec.status).dot" :title="statusTone(exec.status).label"></span>
          <span class="min-w-0">
            <span class="block truncate font-semibold text-ink">{{ exec.job_name }}</span>
            <span class="block text-xs text-ink-3">{{ formatDate(exec.started_at) }} · {{ formatDuration(exec) }}</span>
          </span>
          <span class="flex items-center gap-3 text-right text-[13px]">
            <span v-if="exec.status === 'failed'" class="font-semibold text-bad">Failed</span>
            <span v-else-if="exec.status === 'running'" class="font-semibold text-notice"><i aria-hidden="true" class="fas fa-spinner fa-spin mr-1"></i>Running</span>
            <span v-else class="text-ink-2"><strong class="text-ink">{{ exec.requested_count }}</strong> requested <span class="text-ink-4 max-sm:hidden">/ {{ exec.results_count }} found</span></span>
            <i v-if="exec.error_message" aria-hidden="true" class="fas fa-chevron-down text-xs text-ink-4 transition-transform" :class="{ 'rotate-180': expandedId === exec.id }"></i>
          </span>
        </component>

        <div v-if="expandedId === exec.id" class="px-6 pb-4 max-sm:px-4">
          <div class="relative rounded-ctl border border-bad/30 bg-bad/5">
            <pre class="m-0 max-h-64 overflow-auto whitespace-pre-wrap break-words p-3 pr-12 font-mono text-xs leading-relaxed text-ink-2">{{ exec.error_message }}</pre>
            <button type="button" class="absolute right-2 top-2 grid h-8 w-8 cursor-pointer place-items-center rounded-[8px] border-0 bg-transparent text-ink-3 hover:bg-raised hover:text-ink" aria-label="Copy error" title="Copy error" @click="copyError(exec)">
              <i aria-hidden="true" class="fas fa-copy"></i>
            </button>
          </div>
        </div>
      </li>
    </ul>

    <div v-else class="flex flex-col items-center gap-2 py-14 text-ink-3">
      <i aria-hidden="true" class="fas fa-inbox text-2xl text-ink-4"></i>
      <p class="m-0 text-sm">{{ history.length ? 'No runs match these filters.' : 'No runs yet.' }}</p>
    </div>

    <template v-if="totalPages > 1" #footer>
      <span class="mr-auto text-[13px] text-ink-3">Page {{ currentPage }} of {{ totalPages }}</span>
      <button type="button" class="ui-btn w-10 px-0" aria-label="Previous page" :disabled="currentPage === 1" @click="currentPage--"><i aria-hidden="true" class="fas fa-chevron-left"></i></button>
      <button type="button" class="ui-btn w-10 px-0" aria-label="Next page" :disabled="currentPage === totalPages" @click="currentPage++"><i aria-hidden="true" class="fas fa-chevron-right"></i></button>
    </template>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import { copyText } from '@/utils/clipboard.js';

const STATUS_TONES = {
  completed: { label: 'Completed', dot: 'bg-good' },
  failed: { label: 'Failed', dot: 'bg-bad' },
  running: { label: 'Running', dot: 'bg-notice animate-pulse' },
};

export default {
  name: 'JobHistoryModal',
  components: { AppDialog },
  props: {
    history: { type: Array, default: () => [] },
  },
  emits: ['close'],
  data() {
    return {
      filterStatus: '',
      filterJob: '',
      currentPage: 1,
      perPage: 20,
      expandedId: null,
      statusOptions: [
        { value: '', label: 'All' },
        { value: 'completed', label: 'Completed' },
        { value: 'failed', label: 'Failed' },
        { value: 'running', label: 'Running' },
      ],
    };
  },
  computed: {
    jobNames() {
      return [...new Set(this.history.map(exec => exec.job_name))].sort();
    },
    byJob() {
      return this.filterJob ? this.history.filter(exec => exec.job_name === this.filterJob) : this.history;
    },
    filteredHistory() {
      return this.filterStatus ? this.byJob.filter(exec => exec.status === this.filterStatus) : this.byJob;
    },
    totalPages() {
      return Math.ceil(this.filteredHistory.length / this.perPage);
    },
    paginatedHistory() {
      const start = (this.currentPage - 1) * this.perPage;
      return this.filteredHistory.slice(start, start + this.perPage);
    },
    successRate() {
      const finished = this.history.filter(exec => exec.status !== 'running');
      if (!finished.length) return 0;
      return Math.round(finished.filter(exec => exec.status === 'completed').length / finished.length * 100);
    },
  },
  watch: {
    filterStatus() { this.currentPage = 1; },
    filterJob() { this.currentPage = 1; },
  },
  methods: {
    countFor(status) {
      return status ? this.byJob.filter(exec => exec.status === status).length : this.byJob.length;
    },
    statusTone(status) {
      return STATUS_TONES[status] || { label: status, dot: 'bg-ink-4' };
    },
    toggle(id) {
      this.expandedId = this.expandedId === id ? null : id;
    },
    formatDate(dateStr) {
      return dateStr ? new Date(dateStr).toLocaleString() : 'N/A';
    },
    formatDuration(exec) {
      if (!exec.started_at || !exec.finished_at) {
        return exec.status === 'running' ? 'in progress' : '—';
      }
      const durationMs = new Date(exec.finished_at) - new Date(exec.started_at);
      if (durationMs < 1000) return `${durationMs}ms`;
      if (durationMs < 60000) return `${Math.round(durationMs / 1000)}s`;
      const mins = Math.floor(durationMs / 60000);
      const secs = Math.round((durationMs % 60000) / 1000);
      return `${mins}m ${secs}s`;
    },
    async copyError(exec) {
      if (await copyText(exec.error_message)) this.$toast.success('Error copied.');
      else this.$toast.error('Copy failed.');
    },
  },
};
</script>
