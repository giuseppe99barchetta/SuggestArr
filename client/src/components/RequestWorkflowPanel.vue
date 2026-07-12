<template>
  <section class="request-workflow">
    <div v-if="showHeader" class="suggestions-header">
      <div><h2>Request approval</h2><p>Review requests before they are sent to Seer.</p></div>
      <div class="suggestion-actions">
        <select v-model="jobId" aria-label="Manual job"><option :value="null">Choose job</option><option v-for="job in jobs" :key="job.id" :value="job.id">{{ job.name }}</option></select>
        <BaseButton :disabled="!jobId || running" @click="runJob">Force Run</BaseButton>
      </div>
    </div>
    <div v-if="bulkMode" class="workflow-toolbar workflow-toolbar--active">
      <span class="workflow-toolbar-title"><i class="fas fa-check-double"></i> Bulk mode active</span>
      <span class="badge badge-media">{{ selected.length }} selected</span>
      <button v-if="canApprove" type="button" class="btn btn-icon bulk-action bulk-action--approve" aria-label="Approve selected requests" title="Approve selected" @click="confirmAction('approve')"><i class="fas fa-check"></i></button>
      <button v-if="canApprove" type="button" class="btn btn-icon bulk-action bulk-action--reject" aria-label="Reject selected requests" title="Reject selected" @click="confirmAction('reject')"><i class="fas fa-times"></i></button>
      <button v-if="canApprove" type="button" class="btn btn-icon bulk-action bulk-action--blacklist" aria-label="Blacklist selected requests" title="Blacklist selected" @click="confirmAction('blacklist')"><i class="fas fa-ban"></i></button>
      <button v-if="canRetry" type="button" class="btn btn-icon bulk-action bulk-action--retry" aria-label="Retry selected requests" title="Retry selected" @click="confirmAction('retry')"><i class="fas fa-redo"></i></button>
      <button v-if="canRequestAgain" type="button" class="btn btn-icon bulk-action bulk-action--retry" aria-label="Request selected items again" title="Request again" @click="confirmAction('request-again')"><i class="fas fa-paper-plane"></i></button>
    </div>
    <div v-if="loading">Loading…</div>
    <div v-else-if="!items.length && showEmpty">No requests in this state.</div>
    <div v-else class="requests-grid">
      <article v-for="item in items" :key="item.id" class="request-card card card--column card--interactive card--padding-none" :class="{ 'card--selected': selected.includes(item.id) }" tabindex="0" @click="openItem(item)" @keydown.enter="openItem(item)">
        <label v-if="bulkMode" class="workflow-checkbox tabs-checkboxes" @click.stop><input v-model="selected" type="checkbox" :value="item.id" /><span class="sr-only">Select {{ item.title }}</span></label>
        <div class="request-card-poster"><img v-if="item.poster_path" :src="`https://image.tmdb.org/t/p/w342${item.poster_path}`" :alt="item.title" class="poster-image" /><div v-else class="poster-placeholder"><i class="fas fa-image"></i></div><div v-if="!bulkMode && item.status === 'awaiting_approval'" class="poster-actions"><button type="button" class="poster-action poster-action--approve" :disabled="actionLoading" aria-label="Approve request" title="Approve" @click.stop="decideOne('approve', item.id)"><i class="fas fa-check"></i></button><button type="button" class="poster-action poster-action--reject" :disabled="actionLoading" aria-label="Reject request" title="Reject" @click.stop="confirmSingle('reject', item.id)"><i class="fas fa-times"></i></button></div><div v-else-if="!bulkMode && item.status === 'failed'" class="poster-actions"><button type="button" class="poster-action poster-action--retry" :disabled="actionLoading" aria-label="Retry request" title="Retry" @click.stop="decideOne('retry', item.id)"><i class="fas fa-redo"></i></button></div><div v-else-if="!bulkMode && (item.status === 'rejected' || item.status === 'blacklisted')" class="poster-actions"><button type="button" class="poster-action poster-action--retry" :disabled="actionLoading" aria-label="Request again" title="Request again" @click.stop="confirmRequestAgain(item)"><i class="fas fa-paper-plane"></i></button></div></div>
        <div class="request-card-body"><h3 class="request-card-title">{{ item.title || `TMDb ${item.tmdb_id}` }}</h3><div class="badge-container"><span class="badge badge-media">{{ item.media_type.toUpperCase() }}</span><span class="badge badge-rating"><i class="fas fa-star"></i> {{ formatRating(item.rating) }}</span><span class="badge badge-requested">{{ statusLabel(item.status) }}</span></div><div class="source-link"><span>From: <strong>{{ item.name }}</strong></span></div><small v-if="item.status === 'failed'">{{ item.last_error || `Failed after ${item.retry_count} attempts` }}</small></div>
      </article>
    </div>
    <div v-if="page < pages" ref="loadMoreTrigger" class="load-more-trigger"><div class="spinner-small"></div><p>Loading more requests...</p></div>
    <Teleport to="body">
      <div v-if="confirmation" class="modal-overlay" @click.self="confirmation = null">
        <div class="modal modal--md workflow-confirm" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
          <div class="modal-header" :class="{ 'modal-header--danger': confirmation.action === 'reject' || confirmation.action === 'blacklist' }"><div class="modal-title-wrap"><h3 id="confirm-title" class="modal-title"><i :class="confirmation.icon"></i>{{ confirmation.title }}</h3><p class="modal-subtitle">{{ confirmation.message }}</p></div><button type="button" class="modal-close" aria-label="Close confirmation" @click="confirmation = null"><i class="fas fa-times"></i></button></div>
          <div class="modal-body"><template v-if="confirmation.action === 'reject'"><p class="workflow-confirm-label">Requests to reject</p><div class="workflow-confirm-items"><div v-for="item in confirmation.items" :key="item.id" class="workflow-confirm-item"><img v-if="item.poster_path" :src="`https://image.tmdb.org/t/p/w92${item.poster_path}`" alt="" /><span v-else class="workflow-confirm-placeholder"><i class="fas fa-film"></i></span><div><strong>{{ item.title || `TMDb ${item.tmdb_id}` }}</strong><small>{{ item.media_type.toUpperCase() }}<template v-if="item.name"> · Suggested from {{ item.name }}</template></small></div></div></div><div class="workflow-confirm-note"><i class="fas fa-info-circle" aria-hidden="true"></i><p>These items will be archived, not blacklisted. You can find them later by filtering requests by <strong>Rejected</strong> and request them again.</p></div></template><div v-else class="workflow-confirm-message"><i :class="confirmation.icon" aria-hidden="true"></i><p>{{ confirmation.message }}</p></div></div>
          <div class="modal-footer"><BaseButton variant="secondary" @click="confirmation = null">Cancel</BaseButton><BaseButton :variant="confirmation.action === 'approve' ? 'success' : 'danger'" @click="decide">{{ confirmation.confirmLabel }}</BaseButton></div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script>
import axios from 'axios';
import BaseButton from '@/components/ui/BaseButton.vue';
export default {
  name: 'RequestWorkflowPanel', components: { BaseButton },
  emits: ['open', 'update:total'],
  props: { statusFilter: { type: String, default: 'all' }, searchQuery: { type: String, default: '' }, mediaType: { type: String, default: 'all' }, showHeader: { type: Boolean, default: true }, showEmpty: { type: Boolean, default: true }, bulkMode: { type: Boolean, default: false } },
  data() { return { items: [], selected: [], actionLoading: false, jobs: [], jobId: null, loading: false, running: false, search: '', status: this.statusFilter, page: 1, pages: 1, total: 0, confirmation: null, searchTimer: null, observer: null,
    statuses: [{ value: 'awaiting_approval', label: 'Awaiting approval' }, { value: 'queued', label: 'Queued' }, { value: 'submitted', label: 'Submitted' }, { value: 'rejected', label: 'Rejected' }, { value: 'failed', label: 'Failed' }, { value: 'blacklisted', label: 'Blacklisted' }] }; },
  computed: {
    selectedItems() { return this.items.filter(item => this.selected.includes(item.id)); },
    canApprove() { return this.selectedItems.length > 0 && this.selectedItems.every(item => item.status === 'awaiting_approval'); },
    canRetry() { return this.selectedItems.length > 0 && this.selectedItems.every(item => item.status === 'failed'); },
    canRequestAgain() { return this.selectedItems.length > 0 && this.selectedItems.every(item => ['rejected', 'blacklisted'].includes(item.status)); }
  },
  watch: {
    statusFilter(value) { this.status = value; this.load(1); },
    searchQuery(value) { this.search = value; this.reloadSoon(); },
    mediaType() { this.load(1); },
    bulkMode(value) { if (!value) this.selected = []; }
  },
  async mounted() { const requested = this.$route.query.status; if (this.statuses.some(option => option.value === requested)) this.status = requested; const response = await axios.get('/api/jobs'); this.jobs = (response.data.jobs || []).filter(job => job.delivery_mode === 'manual'); this.load(); },
  beforeUnmount() { clearTimeout(this.searchTimer); this.observer?.disconnect(); },
  methods: {
    async load(page = this.page) {
      if (this.loading) return;
      this.loading = true;
      try {
        const data = (await axios.get('/api/automation/requests/workflow', { params: { status: this.status, search: this.search, media_type: this.mediaType, page, per_page: 24 } })).data;
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
    statusLabel(status) { return { awaiting_approval: 'Waiting approval', queued: 'Queued', submitting: 'Sending', rejected: 'Rejected', failed: 'Failed', blacklisted: 'Blacklisted' }[status] || status; },
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
    async decideOne(action, id) { this.actionLoading = true; try { await axios.post(`/api/automation/requests/workflow/${action}`, { ids: [id] }); await this.load(); this.$toast.open({ message: action === 'approve' ? 'Request queued for Seer' : 'Request updated', type: 'success' }); } finally { this.actionLoading = false; } },
    confirmAction(action) { const labels = { approve: ['Send to Seer', `Send ${this.selected.length} selected items using the identity and profiles shown on each card?`, 'fas fa-paper-plane', 'Send'], reject: ['Reject requests', `${this.selected.length} selected items will be removed from the approval queue.`, 'fas fa-archive', 'Reject requests'], blacklist: ['Blacklist requests', `Permanently prevent ${this.selected.length} items from being suggested again?`, 'fas fa-ban', 'Blacklist'], retry: ['Retry failed requests', `Queue ${this.selected.length} failed items for another delivery attempt?`, 'fas fa-redo', 'Retry'], 'request-again': ['Request again', `Remove any blacklist and send ${this.selected.length} selected items to Seer?`, 'fas fa-paper-plane', 'Request again'] }; this.confirmation = { action, ids: [...this.selected], items: [...this.selectedItems], removeBlacklist: action === 'request-again' && this.selectedItems.some(item => item.status === 'blacklisted'), title: labels[action][0], message: labels[action][1], icon: labels[action][2], confirmLabel: labels[action][3] }; },
    confirmSingle(action, id) { const item = this.items.find(request => request.id === id); this.confirmation = { action, ids: [id], items: [item], title: 'Reject request', message: 'This item will be removed from the approval queue.', icon: 'fas fa-archive', confirmLabel: 'Reject request' }; },
    confirmRequestAgain(item) { this.confirmation = { action: 'request-again', ids: [item.id], removeBlacklist: item.status === 'blacklisted', title: 'Request again', message: item.status === 'blacklisted' ? 'Remove this item from the blacklist and send it to Seer?' : 'Send this rejected item to Seer?', icon: 'fas fa-paper-plane', confirmLabel: 'Request again' }; },
    async decide() { const { action, ids, removeBlacklist } = this.confirmation; await axios.post(`/api/automation/requests/workflow/${action}`, { ids, remove_blacklist: removeBlacklist }); this.confirmation = null; await this.load(); this.$toast.open({ message: 'Requests updated', type: 'success' }); },
    async runJob() { this.running = true; try { await axios.post(`/api/jobs/${this.jobId}/run`); await this.load(1); } finally { this.running = false; } }
  }
};
</script>

<style scoped>
.suggestions-header,.suggestion-actions,.workflow-toolbar{display:flex;align-items:center;gap:var(--spacing-sm)}
.suggestions-header{justify-content:space-between}
.workflow-toolbar{justify-content:flex-end;min-height:var(--btn-height-md);margin-top:var(--spacing-lg);margin-bottom:var(--spacing-xl)}
.workflow-toolbar--active{padding:var(--spacing-md);background:var(--surface-elevated);border:1px solid var(--color-border-light);border-radius:var(--radius-lg);box-shadow:var(--shadow-sm)}
.workflow-toolbar-title{margin-right:auto;display:flex;align-items:center;gap:var(--spacing-sm);color:var(--color-text-primary);font-weight:var(--font-weight-semibold)}
.request-workflow{margin-top:var(--spacing-lg)}.request-card{position:relative}.request-card.card--selected{border:2px solid var(--color-text-primary);box-shadow:var(--shadow-lg)}.request-card small{display:block;color:var(--color-text-secondary)}
.workflow-checkbox{position:absolute;top:var(--spacing-sm);left:var(--spacing-sm);z-index:2}
.bulk-action{color:var(--color-text-primary)}.bulk-action--approve{background:var(--color-success)}.bulk-action--reject{background:var(--color-error)}.bulk-action--blacklist{background:var(--color-warning)}.bulk-action--retry{background:var(--color-primary)}
.poster-actions{position:absolute;right:var(--spacing-sm);bottom:var(--spacing-sm);display:flex;gap:var(--spacing-sm);z-index:2}.poster-action{display:grid;place-items:center;width:var(--btn-height-md);height:var(--btn-height-md);border:1px solid var(--color-border-medium);border-radius:var(--radius-full);color:var(--color-text-primary);cursor:pointer;box-shadow:var(--shadow-md);transition:var(--transition-base)}.poster-action:hover:not(:disabled){transform:translateY(calc(var(--spacing-2xs) * -1));box-shadow:var(--shadow-lg)}.poster-action--approve{background:var(--color-success)}.poster-action--reject{background:var(--color-error)}.poster-action--retry{background:var(--color-primary)}.poster-action:disabled{opacity:0.5;cursor:not-allowed}
.workflow-confirm-message{display:flex;align-items:center;gap:var(--spacing-md);padding:var(--spacing-md);background:var(--color-error-alpha-10);border:1px solid var(--color-error-alpha-20);border-radius:var(--radius-md)}
.workflow-confirm-message>i{display:grid;place-items:center;flex:0 0 var(--btn-height-md);height:var(--btn-height-md);border-radius:var(--radius-full);background:var(--color-error-alpha-20);color:var(--color-error-light)}
.workflow-confirm-message p{margin:0;color:var(--color-text-primary);line-height:var(--line-height-relaxed)}
.workflow-confirm .modal-title{font-size:var(--font-size-lg)}
.workflow-confirm .modal-title-wrap{gap:var(--spacing-xs)}
.workflow-confirm-label{margin:0;color:var(--color-text-muted);font-size:var(--font-size-sm);font-weight:var(--font-weight-semibold);text-transform:uppercase}
.workflow-confirm-items{display:grid;gap:var(--spacing-sm);max-height:calc(var(--btn-height-lg) * 5);overflow-y:auto}
.workflow-confirm-item{display:flex;align-items:center;gap:var(--spacing-md);padding:var(--spacing-sm);background:var(--surface-interactive);border:1px solid var(--color-border-light);border-radius:var(--radius-md)}
.workflow-confirm-item img,.workflow-confirm-placeholder{width:var(--btn-height-lg);height:var(--btn-height-lg);flex:0 0 var(--btn-height-lg);border-radius:var(--radius-sm);object-fit:cover}
.workflow-confirm-placeholder{display:grid;place-items:center;background:var(--surface-hover);color:var(--color-text-muted)}
.workflow-confirm-item div{display:grid;gap:var(--spacing-2xs);min-width:0}.workflow-confirm-item strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--color-text-primary)}.workflow-confirm-item small{color:var(--color-text-muted)}
.workflow-confirm-note{display:flex;align-items:center;gap:var(--spacing-sm);padding:var(--spacing-md);background:var(--surface-interactive);border-radius:var(--radius-md);color:var(--color-text-secondary)}
.workflow-confirm-note i{color:var(--color-primary)}.workflow-confirm-note p{margin:0;line-height:var(--line-height-relaxed)}
@media(max-width:768px){.suggestions-header,.suggestion-toolbar,.bulk-bar{align-items:flex-start;flex-direction:column}}
</style>
