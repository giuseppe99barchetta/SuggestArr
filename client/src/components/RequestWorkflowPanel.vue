<template>
  <section class="flex flex-col gap-4">
    <div v-if="showHeader" class="flex flex-wrap items-center justify-between gap-3">
      <div><h2 class="m-0 text-lg font-bold text-ink">Request approval</h2><p class="m-0 text-sm text-ink-3">Review requests before they are sent to Seer.</p></div>
      <div class="flex gap-2">
        <select v-model="jobId" aria-label="Manual job" class="h-10 rounded-ctl border border-edge-strong bg-panel px-3 text-sm text-ink"><option :value="null">Choose job</option><option v-for="job in jobs" :key="job.id" :value="job.id">{{ job.name }}</option></select>
        <button type="button" class="h-10 cursor-pointer rounded-ctl border-0 bg-brand px-4 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50" :disabled="!jobId || running" @click="runJob">Run now</button>
      </div>
    </div>

    <div v-if="bulkMode" class="sticky top-16 z-20 flex flex-wrap items-center gap-2 rounded-card border border-brand-soft bg-panel/95 px-4 py-3 backdrop-blur lg:top-4">
      <span class="mr-auto text-sm font-semibold text-ink"><i aria-hidden="true" class="fas fa-check-double mr-1.5 text-brand-ink"></i>{{ selected.length }} selected</span>
      <button v-if="canApprove" type="button" class="h-9 cursor-pointer rounded-[8px] border-0 bg-brand px-3.5 text-[13px] font-bold text-white" @click="confirmAction('approve')">Approve</button>
      <button v-if="canApprove" type="button" class="h-9 cursor-pointer rounded-[8px] border border-edge-strong bg-transparent px-3.5 text-[13px] font-semibold text-ink-2" @click="confirmAction('reject')">Reject</button>
      <button v-if="canApprove" type="button" class="h-9 cursor-pointer rounded-[8px] border border-edge-strong bg-transparent px-3.5 text-[13px] font-semibold text-bad" @click="confirmAction('blacklist')">Blacklist</button>
      <button v-if="canRetry" type="button" class="h-9 cursor-pointer rounded-[8px] border-0 bg-brand-soft px-3.5 text-[13px] font-bold text-brand-ink" @click="confirmAction('retry')">Retry</button>
      <button v-if="canRequestAgain" type="button" class="h-9 cursor-pointer rounded-[8px] border-0 bg-brand-soft px-3.5 text-[13px] font-bold text-brand-ink" @click="confirmAction('request-again')">Request again</button>
      <span v-if="!selected.length" class="text-[13px] text-ink-4">Click cards to select them</span>
    </div>

    <MediaGridSkeleton v-if="loading && !items.length" :count="6" label="Loading requests…" />
    <div v-else-if="!items.length && showEmpty" class="py-10 text-center text-sm text-ink-3">No requests in this state.</div>
    <div v-else class="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-4">
      <MediaCard
        v-for="item in items"
        :key="item.id"
        :title="item.title || `TMDb ${item.tmdb_id}`"
        :poster="item.poster_path ? `https://image.tmdb.org/t/p/w342${item.poster_path}` : ''"
        :badge="statusLabel(item.status)"
        :tone="statusTone(item.status)"
        :selected="selected.includes(item.id)"
        @open="openItem(item)"
      >
        <template v-if="bulkMode" #overlay>
          <label class="absolute right-2.5 top-2.5 z-10 flex h-7 w-7 items-center justify-center rounded-md bg-canvas/80" @click.stop>
            <input v-model="selected" type="checkbox" :value="item.id" class="h-4 w-4 accent-brand" />
            <span class="sr-only">Select {{ item.title }}</span>
          </label>
        </template>
        <template v-if="!bulkMode && ['awaiting_approval', 'failed', 'rejected', 'blacklisted'].includes(item.status)" #actions>
          <template v-if="seenMenuId === item.id">
            <button v-for="option in seenOptions" :key="option.value" type="button" class="h-9 flex-1 cursor-pointer rounded-[8px] border border-edge-strong bg-panel-2 text-ink-2 hover:text-ink disabled:opacity-50" :disabled="actionLoading" :aria-label="option.label" :title="option.label" @click.stop="markSeen(item, option)"><i aria-hidden="true" :class="option.icon"></i></button>
            <button type="button" class="h-9 w-9 cursor-pointer rounded-[8px] border-0 bg-transparent text-ink-4 hover:text-ink" aria-label="Cancel" title="Cancel" @click.stop="seenMenuId = null"><i aria-hidden="true" class="fas fa-undo"></i></button>
          </template>
          <template v-else-if="item.status === 'awaiting_approval'">
            <button type="button" class="h-9 flex-1 cursor-pointer rounded-[8px] border-0 bg-brand text-[13px] font-bold text-white disabled:opacity-50" :disabled="actionLoading" aria-label="Approve request" @click.stop="decideOne('approve', item.id)">Approve</button>
            <button type="button" class="h-9 w-9 cursor-pointer rounded-[8px] border border-edge-strong bg-transparent text-ink-2 hover:text-ink disabled:opacity-50" :disabled="actionLoading" aria-label="Already seen it" title="Already seen it" @click.stop="seenMenuId = item.id"><i aria-hidden="true" class="fas fa-eye"></i></button>
            <button type="button" class="h-9 w-9 cursor-pointer rounded-[8px] border border-edge-strong bg-transparent text-ink-2 hover:text-bad disabled:opacity-50" :disabled="actionLoading" aria-label="Reject request" title="Reject" @click.stop="confirmSingle('reject', item.id)"><i aria-hidden="true" class="fas fa-times"></i></button>
          </template>
          <button v-else-if="item.status === 'failed'" type="button" class="h-9 flex-1 cursor-pointer rounded-[8px] border-0 bg-brand-soft text-[13px] font-bold text-brand-ink disabled:opacity-50" :disabled="actionLoading" @click.stop="decideOne('retry', item.id)"><i aria-hidden="true" class="fas fa-redo mr-1"></i>Retry</button>
          <button v-else type="button" class="h-9 flex-1 cursor-pointer rounded-[8px] border-0 bg-brand-soft text-[13px] font-bold text-brand-ink disabled:opacity-50" :disabled="actionLoading" @click.stop="confirmRequestAgain(item)">Request again</button>
        </template>
        <div class="media-card-body flex flex-col gap-1 text-xs">
          <span class="font-semibold text-ink-2">{{ item.media_type === 'movie' ? 'Movie' : 'TV' }}<template v-if="item.rating"> · <i aria-hidden="true" class="fas fa-star text-caution"></i> {{ formatRating(item.rating) }}</template></span>
          <span v-if="item.name" class="line-clamp-2 leading-snug text-ink-3">From {{ item.name }}</span>
          <span v-if="item.user_name || item.media_user_id" class="truncate text-ink-4" :title="`For ${item.user_name || item.media_user_id}`">For {{ item.user_name || item.media_user_id }}</span>
          <small v-if="item.status === 'failed'" class="text-bad">{{ item.last_error || `Failed after ${item.retry_count} attempts` }}</small>
        </div>
      </MediaCard>
    </div>
    <div v-if="page < pages" ref="loadMoreTrigger" class="py-8 text-center text-sm text-ink-4">Loading more requests…</div>

    <AppDialog v-if="confirmation" width="max-w-2xl" labelledby="confirm-title" @close="confirmation = null">
      <div class="flex flex-col gap-4 p-6">
        <div class="flex flex-col gap-1">
          <h3 id="confirm-title" class="m-0 text-lg font-bold" :class="confirmation.action === 'reject' || confirmation.action === 'blacklist' ? 'text-bad' : 'text-ink'"><i aria-hidden="true" :class="confirmation.icon" class="mr-2"></i>{{ confirmation.title }}</h3>
          <p class="m-0 text-sm text-ink-3">{{ confirmation.message }}</p>
        </div>
        <template v-if="confirmation.action === 'reject'">
          <ul class="m-0 flex max-h-72 list-none flex-col gap-2 overflow-y-auto p-0">
            <li v-for="item in confirmation.items" :key="item.id" class="flex items-center gap-3 rounded-ctl border border-edge bg-panel-2 p-2">
              <img v-if="item.poster_path" :src="`https://image.tmdb.org/t/p/w92${item.poster_path}`" alt="" class="h-14 w-10 rounded object-cover" />
              <span v-else class="flex h-14 w-10 items-center justify-center rounded bg-raised text-ink-4"><i aria-hidden="true" class="fas fa-film"></i></span>
              <span class="flex min-w-0 flex-col"><strong class="truncate text-sm text-ink">{{ item.title || `TMDb ${item.tmdb_id}` }}</strong><small class="text-ink-4">{{ item.media_type === 'movie' ? 'Movie' : 'TV' }}<template v-if="item.name"> · Suggested from {{ item.name }}</template></small></span>
            </li>
          </ul>
          <p class="m-0 rounded-ctl bg-panel-2 p-3 text-sm leading-relaxed text-ink-3"><i aria-hidden="true" class="fas fa-info-circle mr-1.5 text-brand-ink"></i>Rejected items are archived, not blacklisted. Filter requests by <strong>Rejected</strong> to find and request them again.</p>
        </template>
        <ApprovalProfileChoice v-if="confirmation.action === 'approve'" ref="profileChoice" :servers="servers" :media-types="confirmationMediaTypes" />
        <div class="mt-2 flex justify-end gap-2">
          <button type="button" class="h-10 cursor-pointer rounded-ctl border border-edge-strong bg-panel-2 px-4 text-sm font-semibold text-ink" @click="confirmation = null">Cancel</button>
          <button type="button" class="h-10 cursor-pointer rounded-ctl border-0 px-4 text-sm font-bold disabled:opacity-50" :class="confirmation.action === 'reject' || confirmation.action === 'blacklist' ? 'bg-bad text-on-bad' : 'bg-brand text-white'" :disabled="actionLoading" @click="decide">{{ confirmation.confirmLabel }}</button>
        </div>
      </div>
    </AppDialog>
  </section>
</template>

<script>
import axios from 'axios';
import AppDialog from '@/components/ui/AppDialog.vue';
import MediaCard from '@/components/ui/MediaCard.vue';
import MediaGridSkeleton from '@/components/ui/MediaGridSkeleton.vue';
import ApprovalProfileChoice from '@/components/ApprovalProfileChoice.vue';
import { approvalNeedsDialog, loadSeerServers, mediaTypesOf } from '@/utils/requestProfiles.js';
import { SEEN_OPTIONS, saveSeenFeedback } from '@/utils/suggestionFeedback.js';
import { notifyRequestsChanged } from '@/utils/requestEvents.js';
export default {
  name: 'RequestWorkflowPanel', components: { AppDialog, MediaCard, MediaGridSkeleton, ApprovalProfileChoice },
  emits: ['open', 'update:total'],
  props: { statusFilter: { type: String, default: 'all' }, searchQuery: { type: String, default: '' }, mediaType: { type: String, default: 'all' }, requestedFor: { type: String, default: 'all' }, showHeader: { type: Boolean, default: true }, showEmpty: { type: Boolean, default: true }, bulkMode: { type: Boolean, default: false } },
  data() { return { items: [], selected: [], actionLoading: false, seenMenuId: null, seenOptions: SEEN_OPTIONS, jobs: [], jobId: null, loading: false, running: false, search: '', status: this.statusFilter, page: 1, pages: 1, total: 0, confirmation: null, searchTimer: null, observer: null, servers: null,
    statuses: [{ value: 'awaiting_approval', label: 'Awaiting approval' }, { value: 'queued', label: 'Queued' }, { value: 'submitted', label: 'Submitted' }, { value: 'rejected', label: 'Rejected' }, { value: 'failed', label: 'Failed' }, { value: 'blacklisted', label: 'Blacklisted' }] }; },
  computed: {
    selectedItems() { return this.items.filter(item => this.selected.includes(item.id)); },
    canApprove() { return this.selectedItems.length > 0 && this.selectedItems.every(item => item.status === 'awaiting_approval'); },
    canRetry() { return this.selectedItems.length > 0 && this.selectedItems.every(item => item.status === 'failed'); },
    canRequestAgain() { return this.selectedItems.length > 0 && this.selectedItems.every(item => ['rejected', 'blacklisted'].includes(item.status)); },
    confirmationMediaTypes() { return mediaTypesOf(this.confirmation?.items); }
  },
  watch: {
    statusFilter(value) { this.status = value; this.load(1); },
    searchQuery(value) { this.search = value; this.reloadSoon(); },
    mediaType() { this.load(1); },
    requestedFor() { this.load(1); },
    bulkMode(value) { if (!value) this.selected = []; this.seenMenuId = null; }
  },
  async mounted() { const requested = this.$route.query.status; if (this.statuses.some(option => option.value === requested)) this.status = requested; const response = await axios.get('/api/jobs'); this.jobs = (response.data.jobs || []).filter(job => job.delivery_mode === 'manual'); this.load(); this.servers = await loadSeerServers(axios); },
  beforeUnmount() { clearTimeout(this.searchTimer); this.observer?.disconnect(); },
  methods: {
    async load(page = this.page) {
      if (this.loading) return;
      this.loading = true;
      try {
        const data = (await axios.get('/api/automation/requests/workflow', { params: { status: this.status, search: this.search, media_type: this.mediaType, user_id: this.requestedFor === 'all' ? undefined : this.requestedFor, page, per_page: 24 } })).data;
        this.items = page === 1 ? data.items : [...this.items, ...data.items];
        Object.assign(this, { total: data.total, page: data.page, pages: data.pages });
        this.$emit('update:total', data.total);
        if (page === 1) this.selected = [];
        this.$nextTick(this.observeLoadMore);
      } finally { this.loading = false; }
    },
    observeLoadMore() {
      this.observer?.disconnect();
      if (this.page >= this.pages || !this.$refs.loadMoreTrigger) return;
      this.observer = new IntersectionObserver(entries => {
        if (entries[0].isIntersecting) this.load(this.page + 1);
      }, { rootMargin: '300px' });
      this.observer.observe(this.$refs.loadMoreTrigger);
    },
    reloadSoon() { clearTimeout(this.searchTimer); this.searchTimer = setTimeout(() => this.load(1), 250); },
    statusTone(status) { return { awaiting_approval: 'caution', queued: 'notice', submitting: 'notice', failed: 'bad', blacklisted: 'bad' }[status] || 'neutral'; },
    statusLabel(status) { return { awaiting_approval: 'Needs approval', queued: 'Queued', submitting: 'Sending', rejected: 'Rejected', failed: 'Failed', blacklisted: 'Blacklisted' }[status] || status; },
    formatRating(value) { if (value === null || value === undefined || value === '') return 'N/A'; const rating = Number(value); return Number.isFinite(rating) ? rating.toFixed(1) : 'N/A'; },
    openItem(item) {
      if (!this.bulkMode) {
        this.$emit('open', item);
        return;
      }
      const index = this.selected.indexOf(item.id);
      if (index === -1) this.selected.push(item.id);
      else this.selected.splice(index, 1);
    },
    // Record that the user has already watched a suggestion, then take it out of the
    // queue. The feedback is what stops it coming back; the reject only clears the card.
    async markSeen(item, option) {
      this.actionLoading = true;
      try {
        await saveSeenFeedback(axios, item.id, option, item);
      } catch (error) {
        this.$toast.open({ message: error.response?.data?.message || 'Could not save feedback', type: 'error' });
        this.actionLoading = false;
        return;
      } finally { this.seenMenuId = null; }
      this.actionLoading = false;
      await this.decideOne('reject', item.id);
    },
    async decideOne(action, id) {
      // Approving is the one action that spends bandwidth and disk and cannot
      // be taken back, so when there is a profile to pick it asks first —
      // rejecting already does. Only a loaded, empty server list skips it.
      if (action === 'approve' && approvalNeedsDialog(this.servers)) { this.confirmSingle('approve', id); return; }
      this.actionLoading = true;
      try {
        await axios.post(`/api/automation/requests/workflow/${action}`, { ids: [id] });
        notifyRequestsChanged();
        await this.load();
        this.$toast.open({ message: action === 'approve' ? 'Request queued for Seer' : 'Request updated', type: 'success' });
      } finally { this.actionLoading = false; }
    },
    confirmAction(action) { const labels = { approve: ['Send to Seer', `Send ${this.selected.length} selected items using the identity and profiles shown on each card?`, 'fas fa-paper-plane', 'Send'], reject: ['Reject requests', `${this.selected.length} selected items will be removed from the approval queue.`, 'fas fa-archive', 'Reject requests'], blacklist: ['Blacklist requests', `Permanently prevent ${this.selected.length} items from being suggested again?`, 'fas fa-ban', 'Blacklist'], retry: ['Retry failed requests', `Queue ${this.selected.length} failed items for another delivery attempt?`, 'fas fa-redo', 'Retry'], 'request-again': ['Request again', `Remove any blacklist and send ${this.selected.length} selected items to Seer?`, 'fas fa-paper-plane', 'Request again'] }; this.confirmation = { action, ids: [...this.selected], items: [...this.selectedItems], removeBlacklist: action === 'request-again' && this.selectedItems.some(item => item.status === 'blacklisted'), title: labels[action][0], message: labels[action][1], icon: labels[action][2], confirmLabel: labels[action][3] }; },
    confirmSingle(action, id) {
      const item = this.items.find(request => request.id === id);
      this.confirmation = action === 'approve'
        ? { action, ids: [id], items: [item], title: 'Send to Seer', message: `Send ${item?.title || 'this item'} to Seer?`, icon: 'fas fa-paper-plane', confirmLabel: 'Send' }
        : { action, ids: [id], items: [item], title: 'Reject request', message: 'This item will be removed from the approval queue.', icon: 'fas fa-archive', confirmLabel: 'Reject request' };
    },
    confirmRequestAgain(item) { this.confirmation = { action: 'request-again', ids: [item.id], removeBlacklist: item.status === 'blacklisted', title: 'Request again', message: item.status === 'blacklisted' ? 'Remove this item from the blacklist and send it to Seer?' : 'Send this rejected item to Seer?', icon: 'fas fa-paper-plane', confirmLabel: 'Request again' }; },
    async decide() {
      const { action, ids, removeBlacklist } = this.confirmation;
      const profile = action === 'approve' ? this.$refs.profileChoice?.payload() : null;
      this.actionLoading = true;
      try {
        await axios.post(`/api/automation/requests/workflow/${action}`, { ids, remove_blacklist: removeBlacklist, ...(profile ? { profile } : {}) });
        notifyRequestsChanged();
        this.confirmation = null;
        await this.load();
        this.$toast.open({ message: 'Requests updated', type: 'success' });
      } catch (error) {
        // A rejected profile comes back as 400 with a reason. Swallowing it
        // would leave the dialog looking as if nothing had happened.
        this.$toast.open({ message: error.response?.data?.message || 'Could not update requests', type: 'error' });
      } finally { this.actionLoading = false; }
    },
    async runJob() { this.running = true; try { await axios.post(`/api/jobs/${this.jobId}/run`); await this.load(1); } finally { this.running = false; } }
  }
};
</script>

