<template>
  <section class="watched-media-history">
    <h3><i class="fas fa-book-open"></i> Recommendation history</h3>
    <p class="card-desc">
      Add titles you have watched but that are no longer in your media server. They are excluded from future suggestions and used to personalise recommendations.
    </p>

    <div class="account-form-section">
      <h4 class="subsection-title">Import CSV</h4>
      <p class="form-help">UTF-8 CSV with these headers: <code>tmdb_id,media_type,title,year,rating</code>. Rating is optional and ranges from 0 to 10.</p>
      <input ref="file" type="file" accept=".csv,text/csv" class="form-control" :disabled="isImporting" @change="onFileChange">
      <button type="button" class="btn btn-outline btn-sm" :disabled="!importFile || isImporting" @click="importCsv">
        <i :class="isImporting ? 'fas fa-spinner fa-spin' : 'fas fa-file-import'"></i>
        {{ isImporting ? 'Importing…' : 'Import CSV' }}
      </button>
    </div>

    <div class="section-divider"></div>

    <div class="account-form-section">
      <h4 class="subsection-title">Add a title</h4>
      <div class="form-group">
        <label for="watchedSearch">Search TMDb</label>
        <div class="form-row">
          <input id="watchedSearch" v-model.trim="query" class="form-control" type="search" placeholder="Movie or series title" @keyup.enter="search">
          <select v-model="searchType" class="form-control" aria-label="Media type">
            <option value="both">Movies and TV</option>
            <option value="movie">Movies</option>
            <option value="tv">TV shows</option>
          </select>
          <button type="button" class="btn btn-outline btn-sm" :disabled="query.length < 2 || isSearching" @click="search">
            <i :class="isSearching ? 'fas fa-spinner fa-spin' : 'fas fa-search'"></i> Search
          </button>
        </div>
      </div>
      <div v-if="searchResults.length" class="history-search-results">
        <div v-for="result in searchResults" :key="`${result.media_type}:${result.tmdb_id}`" class="user-row">
          <span>{{ result.title }} <small>({{ result.year || '—' }}) · {{ result.media_type }}</small></span>
          <div class="form-row">
            <input v-model.number="ratings[`${result.media_type}:${result.tmdb_id}`]" class="form-control" type="number" min="0" max="10" step="0.5" placeholder="Rating">
            <button type="button" class="btn btn-outline btn-sm" :disabled="addingKey === `${result.media_type}:${result.tmdb_id}`" @click="addResult(result)">
              <i :class="addingKey === `${result.media_type}:${result.tmdb_id}` ? 'fas fa-spinner fa-spin' : 'fas fa-plus'"></i> Add
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="section-divider"></div>

    <div class="account-form-section">
      <h4 class="subsection-title">Your seeds <span v-if="items.length">({{ items.length }})</span></h4>
      <p v-if="isLoading" class="form-help">Loading watched titles…</p>
      <p v-else-if="!items.length" class="form-help">No CSV or manual titles yet.</p>
      <div v-else class="table-responsive">
        <table class="table">
          <thead><tr><th>Title</th><th>Type</th><th>Rating</th><th>Source</th><th></th></tr></thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td>{{ item.title }} <small v-if="item.year">({{ item.year }})</small></td>
              <td>{{ item.media_type }}</td>
              <td>{{ item.rating ?? '—' }}</td>
              <td>{{ item.source === 'csv_import' ? 'CSV import' : 'Manual' }}</td>
              <td><button type="button" class="btn btn-danger btn-sm icon-btn" title="Remove" @click="remove(item)"><i class="fas fa-trash"></i></button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script>
import {
  addMyWatchedMedia,
  deleteMyWatchedMedia,
  importMyWatchedMedia,
  listMyWatchedMedia,
  searchMyWatchedMedia,
} from '@/api/api';

export default {
  name: 'WatchedMediaHistory',
  data() {
    return {
      items: [], importFile: null, query: '', searchType: 'both', searchResults: [], ratings: {},
      isLoading: false, isImporting: false, isSearching: false, addingKey: '',
    };
  },
  mounted() { this.load(); },
  methods: {
    async load() {
      this.isLoading = true;
      try { this.items = (await listMyWatchedMedia()).data.items || []; }
      catch (error) {
        if (error.response?.status !== 404) this.$toast.error(error.response?.data?.message || 'Could not load recommendation history');
      } finally { this.isLoading = false; }
    },
    onFileChange(event) { [this.importFile] = event.target.files || []; },
    async importCsv() {
      if (!this.importFile) return;
      this.isImporting = true;
      try {
        const result = (await importMyWatchedMedia(this.importFile)).data;
        this.$toast.success(result.message);
        if (result.errors?.length) this.$toast.error(`${result.errors.length} row(s) could not be imported`);
        this.importFile = null;
        this.$refs.file.value = '';
        await this.load();
      } catch (error) { this.$toast.error(error.response?.data?.message || 'CSV import failed'); }
      finally { this.isImporting = false; }
    },
    async search() {
      if (this.query.length < 2) return;
      this.isSearching = true;
      try { this.searchResults = (await searchMyWatchedMedia(this.query, this.searchType)).data.results || []; }
      catch (error) { this.$toast.error(error.response?.data?.message || 'TMDb search failed'); }
      finally { this.isSearching = false; }
    },
    async addResult(result) {
      const key = `${result.media_type}:${result.tmdb_id}`;
      this.addingKey = key;
      try {
        await addMyWatchedMedia({ ...result, rating: this.ratings[key] ?? null });
        this.$toast.success(`${result.title} added to your recommendation history`);
        await this.load();
      } catch (error) { this.$toast.error(error.response?.data?.message || 'Could not add title'); }
      finally { this.addingKey = ''; }
    },
    async remove(item) {
      if (!confirm(`Remove ${item.title} from your recommendation history?`)) return;
      try { await deleteMyWatchedMedia(item.id); this.items = this.items.filter(entry => entry.id !== item.id); }
      catch (error) { this.$toast.error(error.response?.data?.message || 'Could not remove title'); }
    },
  },
};
</script>
