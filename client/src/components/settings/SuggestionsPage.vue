<template>
  <section>
    <div class="suggestions-header">
      <div><h2>Suggestions</h2><p>Review content before it is sent to Seer.</p></div>
      <div class="suggestion-actions">
        <select v-model="jobId" aria-label="Manual job"><option :value="null">Choose job</option><option v-for="job in jobs" :key="job.id" :value="job.id">{{ job.name }}</option></select>
        <BaseButton :disabled="!jobId || running" @click="runJob">Force Run</BaseButton>
      </div>
    </div>
    <div class="suggestion-toolbar">
      <input v-model.trim="search" type="search" placeholder="Search title or TMDb ID" aria-label="Search suggestions" @input="reloadSoon" />
      <select v-model="status" aria-label="Suggestion status" @change="load(1)">
        <option v-for="option in statuses" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
      <span>{{ total }} items</span>
    </div>
    <div v-if="selected.length" class="bulk-bar">
      <strong>{{ selected.length }} selected</strong>
      <BaseButton v-if="status === 'awaiting_approval'" @click="confirmAction('approve')">Send to Seer</BaseButton>
      <BaseButton v-if="status === 'awaiting_approval'" variant="secondary" @click="confirmAction('reject')">Reject</BaseButton>
      <BaseButton v-if="status === 'awaiting_approval'" variant="danger" @click="confirmAction('blacklist')">Blacklist</BaseButton>
      <BaseButton v-if="status === 'failed'" @click="confirmAction('retry')">Retry</BaseButton>
    </div>
    <div v-if="loading">Loading…</div>
    <div v-else-if="!items.length">No suggestions in this state.</div>
    <div v-else class="suggestions-grid">
      <label v-for="item in items" :key="item.id" class="suggestion-card" :class="{ selected: selected.includes(item.id) }">
        <input v-model="selected" type="checkbox" :value="item.id" />
        <img v-if="item.poster_path" :src="`https://image.tmdb.org/t/p/w342${item.poster_path}`" :alt="item.title" />
        <div><strong>{{ item.title || `TMDb ${item.tmdb_id}` }}</strong><small>{{ item.name }} · {{ item.media_type }}</small><small>{{ item.seer_identity_mode }} · {{ profileLabel(item) }}</small><small v-if="item.status === 'failed'">{{ item.last_error || `Failed after ${item.retry_count} attempts` }}</small></div>
      </label>
    </div>
    <div v-if="pages > 1" class="pagination"><BaseButton :disabled="page <= 1" @click="load(page - 1)">Previous</BaseButton><span>{{ page }} / {{ pages }}</span><BaseButton :disabled="page >= pages" @click="load(page + 1)">Next</BaseButton></div>
    <div v-if="confirmation" class="confirm-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <div class="confirm-card"><h3 id="confirm-title">{{ confirmation.title }}</h3><p>{{ confirmation.message }}</p><div class="suggestion-actions"><BaseButton variant="secondary" @click="confirmation = null">Cancel</BaseButton><BaseButton :variant="confirmation.action === 'blacklist' ? 'danger' : 'primary'" @click="decide(confirmation.action)">Confirm</BaseButton></div></div>
    </div>
  </section>
</template>

<script>
import axios from 'axios';
import BaseButton from '@/components/ui/BaseButton.vue';
export default {
  name: 'SuggestionsPage', components: { BaseButton },
  data: () => ({ items: [], selected: [], jobs: [], jobId: null, loading: false, running: false, search: '', status: 'awaiting_approval', page: 1, pages: 1, total: 0, confirmation: null, searchTimer: null,
    statuses: [{ value: 'awaiting_approval', label: 'Awaiting approval' }, { value: 'queued', label: 'Queued' }, { value: 'submitted', label: 'Submitted' }, { value: 'rejected', label: 'Rejected' }, { value: 'failed', label: 'Failed' }] }),
  async mounted() { const response = await axios.get('/api/jobs'); this.jobs = (response.data.jobs || []).filter(job => job.delivery_mode === 'manual'); this.load(); },
  beforeUnmount() { clearTimeout(this.searchTimer); },
  methods: {
    async load(page = this.page) { this.loading = true; try { const data = (await axios.get('/api/jobs/suggestions', { params: { status: this.status, search: this.search, page, per_page: 24 } })).data; Object.assign(this, { items: data.items, total: data.total, page: data.page, pages: data.pages, selected: [] }); } finally { this.loading = false; } },
    reloadSoon() { clearTimeout(this.searchTimer); this.searchTimer = setTimeout(() => this.load(1), 250); },
    profileLabel(item) { const profile = item.request_profile || {}; return profile.profileId ? `profile ${profile.profileId}` : 'Seer default'; },
    confirmAction(action) { const labels = { approve: ['Send to Seer', `Send ${this.selected.length} selected items using the identity and profiles shown on each card?`], reject: ['Reject suggestions', `Archive ${this.selected.length} items without blacklisting them?`], blacklist: ['Blacklist suggestions', `Permanently prevent ${this.selected.length} items from being suggested again?`], retry: ['Retry failed requests', `Queue ${this.selected.length} failed items for another delivery attempt?`] }; this.confirmation = { action, title: labels[action][0], message: labels[action][1] }; },
    async decide(action) { await axios.post(`/api/jobs/suggestions/${action}`, { ids: this.selected }); this.confirmation = null; await this.load(); this.$toast.open({ message: 'Suggestions updated', type: 'success' }); },
    async runJob() { this.running = true; try { await axios.post(`/api/jobs/${this.jobId}/run`); await this.load(1); } finally { this.running = false; } }
  }
};
</script>

<style scoped>
.suggestions-header,.suggestion-actions,.suggestion-toolbar,.bulk-bar,.pagination{display:flex;justify-content:space-between;align-items:center;gap:var(--spacing-md)}
.suggestion-toolbar,.bulk-bar,.pagination{margin-top:var(--spacing-md)}
.suggestions-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:var(--spacing-md);margin-top:var(--spacing-lg)}
.suggestion-card{display:grid;gap:var(--spacing-sm);padding:var(--spacing-sm);border:1px solid var(--border-color);border-radius:var(--radius-md);cursor:pointer}.suggestion-card.selected{border-color:var(--primary-color)}.suggestion-card img{width:100%;border-radius:var(--radius-sm)}.suggestion-card small{display:block;color:var(--text-secondary)}
.confirm-overlay{position:fixed;inset:0;display:grid;place-items:center;background:var(--overlay-background);z-index:var(--z-modal)}.confirm-card{max-width:var(--modal-sm-width);padding:var(--spacing-lg);background:var(--surface-card);border-radius:var(--radius-lg)}
@media(max-width:768px){.suggestions-header,.suggestion-toolbar,.bulk-bar{align-items:flex-start;flex-direction:column}}
</style>
