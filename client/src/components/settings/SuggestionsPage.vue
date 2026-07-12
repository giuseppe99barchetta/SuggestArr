<template>
  <section>
    <div class="suggestions-header">
      <div><h2>Suggestions</h2><p>Review content before it is sent to Seer.</p></div>
      <div class="suggestion-actions">
        <select v-model="jobId" aria-label="Manual job">
          <option :value="null">Choose job</option>
          <option v-for="job in jobs" :key="job.id" :value="job.id">{{ job.name }}</option>
        </select>
        <BaseButton :disabled="!jobId || running" @click="runJob">Force Run</BaseButton>
        <BaseButton :disabled="!selected.length" @click="decide('approve')">Send to Seer</BaseButton>
        <BaseButton variant="danger" :disabled="!selected.length" @click="decide('blacklist')">Blacklist</BaseButton>
      </div>
    </div>
    <div v-if="loading">Loading…</div>
    <div v-else-if="!items.length">No suggestions awaiting approval.</div>
    <div v-else class="suggestions-grid">
      <label v-for="item in items" :key="item.id" class="suggestion-card" :class="{ selected: selected.includes(item.id) }">
        <input v-model="selected" type="checkbox" :value="item.id" />
        <img v-if="item.poster_path" :src="`https://image.tmdb.org/t/p/w342${item.poster_path}`" :alt="item.title" />
        <div><strong>{{ item.title || `TMDb ${item.tmdb_id}` }}</strong><small>{{ item.name }} · {{ item.media_type }}</small></div>
      </label>
    </div>
  </section>
</template>

<script>
import axios from 'axios';
import BaseButton from '@/components/common/BaseButton.vue';
export default {
  name: 'SuggestionsPage', components: { BaseButton },
  data: () => ({ items: [], selected: [], jobs: [], jobId: null, loading: false, running: false }),
  async mounted() {
    const response = await axios.get('/api/jobs');
    this.jobs = (response.data.jobs || []).filter(job => job.delivery_mode === 'manual');
    this.load();
  },
  methods: {
    async load() { this.loading = true; try { this.items = (await axios.get('/api/jobs/suggestions')).data.items; } finally { this.loading = false; } },
    async decide(action) {
      await axios.post(`/api/jobs/suggestions/${action}`, { ids: this.selected });
      this.selected = []; await this.load();
      this.$toast.open({ message: action === 'approve' ? 'Queued for Seer' : 'Added to blacklist', type: 'success' });
    },
    async runJob() {
      this.running = true;
      try { await axios.post(`/api/jobs/${this.jobId}/run`); await this.load(); }
      finally { this.running = false; }
    }
  }
};
</script>

<style scoped>
.suggestions-header,.suggestion-actions{display:flex;justify-content:space-between;align-items:center;gap:var(--spacing-md)}
.suggestions-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:var(--spacing-md);margin-top:var(--spacing-lg)}
.suggestion-card{display:grid;gap:var(--spacing-sm);padding:var(--spacing-sm);border:1px solid var(--border-color);border-radius:var(--radius-md);cursor:pointer}
.suggestion-card.selected{border-color:var(--primary-color)}
.suggestion-card img{width:100%;border-radius:var(--radius-sm)}
.suggestion-card small{display:block;color:var(--text-secondary)}
@media(max-width:768px){.suggestions-header{align-items:flex-start;flex-direction:column}}
</style>
