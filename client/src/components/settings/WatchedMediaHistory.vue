<template>
  <section id="profile-history-content" class="watched-media-history">
    <h3><i class="fas fa-book-open" aria-hidden="true"></i> Recommendation history</h3>
    <p class="card-desc">Add watched titles no longer in your media server to personalise recommendations and exclude them from future suggestions.</p>
    <div class="history-content">
    <div class="history-tools">
    <div class="history-section">
      <div class="history-section__heading">
        <h4>Import CSV</h4>
        <p>Use UTF-8 CSV with <code>tmdb_id,media_type,title,year,rating</code>. Rating is optional and ranges from 0 to 10.</p>
      </div>
      <div class="history-import-controls">
        <div class="history-file-field">
        <span id="history-file-label" class="history-field-label">CSV file</span>
        <div class="history-file-control">
          <input ref="file" type="file" hidden accept=".csv,text/csv" :disabled="isImporting" @change="onFileChange">
          <button type="button" class="btn btn-secondary btn-sm" aria-describedby="history-file-label" :disabled="isImporting" @click="$refs.file.click()">
            <i class="fas fa-folder-open" aria-hidden="true"></i> Choose CSV
          </button>
          <span class="history-filename" aria-live="polite" :title="importFile?.name">{{ importFile?.name || 'No file selected' }}</span>
        </div>
        </div>
        <button type="button" class="btn btn-outline btn-sm" :disabled="!importFile || isImporting" @click="importCsv">
          <i :class="isImporting ? 'fas fa-spinner fa-spin' : 'fas fa-file-import'"></i>
          {{ isImporting ? 'Importing…' : 'Import CSV' }}
        </button>
      </div>
    </div>

    <div class="history-section">
      <div class="history-section__heading">
        <h4>Add a title</h4>
        <p>Search TMDb, then optionally add a personal rating.</p>
      </div>
      <div class="history-search">
        <BaseInput v-model.trim="query" label="Search TMDb" type="search" placeholder="Movie or series title" icon="search" size="lg" @keyup.enter="search" />
        <div class="history-search__controls">
          <BaseDropdown
            id="watchedSearchType"
            v-model="searchType"
            class="history-dropdown"
            :options="searchTypeOptions"
            label="Media type"
          />
          <button type="button" class="btn btn-outline btn-sm" :disabled="query.length < 2 || isSearching" @click="search">
            <i :class="isSearching ? 'fas fa-spinner fa-spin' : 'fas fa-search'"></i> Search
          </button>
        </div>
      </div>
      <div v-if="searchResults.length" class="history-search-results">
        <div v-for="result in searchResults" :key="`${result.media_type}:${result.tmdb_id}`" class="history-result">
          <span class="history-result__title">{{ result.title }} <small>({{ result.year || '—' }}) · {{ result.media_type }}</small></span>
          <div class="history-result__actions">
            <input v-model.number="ratings[`${result.media_type}:${result.tmdb_id}`]" class="form-control" type="number" min="0" max="10" step="0.5" placeholder="Rating">
            <button type="button" class="btn btn-outline btn-sm" :disabled="addingKey === `${result.media_type}:${result.tmdb_id}`" @click="addResult(result)">
              <i :class="addingKey === `${result.media_type}:${result.tmdb_id}` ? 'fas fa-spinner fa-spin' : 'fas fa-plus'"></i> Add
            </button>
          </div>
        </div>
      </div>
    </div>

    </div>
    <div class="history-divider"></div>

    <div class="history-section">
      <div class="history-section__heading">
        <h4>Your seeds <span v-if="items.length">({{ items.length }})</span></h4>
        <p>These titles are private to your linked media-server account.</p>
      </div>
      <p v-if="isLoading" class="history-empty">Loading watched titles…</p>
      <p v-else-if="!items.length" class="history-empty"><i class="fas fa-film" aria-hidden="true"></i> No CSV or manual titles yet.</p>
      <div v-else class="history-table-wrap">
        <table class="history-table">
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
import BaseDropdown from '@/components/common/BaseDropdown.vue';
import BaseInput from '@/components/ui/BaseInput.vue';

export default {
  name: 'WatchedMediaHistory',
  components: { BaseDropdown, BaseInput },
  data() {
    return {
      items: [], importFile: null, query: '', searchType: 'both', searchResults: [], ratings: {},
      isLoading: false, isImporting: false, isSearching: false, addingKey: '',
      searchTypeOptions: [
        { value: 'both', label: 'Movies and TV' },
        { value: 'movie', label: 'Movies' },
        { value: 'tv', label: 'TV shows' },
      ],
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

<style scoped>
.history-content { display: flex; flex-direction: column; gap: var(--spacing-lg); }
.history-tools { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: var(--spacing-xl); row-gap: var(--spacing-sm); }
.history-tools > .history-section { display: grid; grid-template-rows: subgrid; grid-row: span 3; }
.history-tools > .history-section + .history-section { border-left: 1px solid var(--color-border-light); padding-left: var(--spacing-xl); }
.history-tools > * { min-width: 0; }
.history-section h4 { margin: 0; color: var(--color-text-secondary); }
.history-section__heading p, .history-empty { margin: var(--spacing-xs) 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); line-height: var(--line-height-normal); }
.history-section__heading code { overflow-wrap: anywhere; }
.history-section { display: flex; flex-direction: column; gap: var(--spacing-sm); }
.history-section h4 { font-size: var(--font-size-base); font-weight: var(--font-weight-semibold); }
.history-divider { height: 1px; background: var(--surface-glass-light); }
.history-import-controls, .history-search__controls, .history-result__actions { display: grid; align-items: center; gap: var(--spacing-sm); }
.history-import-controls { display: flex; flex-direction: column; align-items: flex-start; justify-content: space-between; gap: var(--spacing-md); }
.history-import-controls > .btn { min-height: var(--input-height-lg); }
.history-file-field { width: 100%; min-width: 0; }
.history-field-label { display: block; margin-bottom: var(--spacing-xs); font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--color-text-secondary); }
.history-file-control { display: flex; align-items: center; gap: var(--spacing-md); width: 100%; min-width: 0; min-height: var(--input-height-lg); padding: var(--spacing-xs); background: var(--surface-glass-subtle); border: 1px solid var(--color-border-light); border-radius: var(--radius-sm); }
.history-file-control .btn { flex-shrink: 0; min-height: var(--input-height-sm); padding-block: var(--spacing-xs); }
.history-filename { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--color-text-muted); font-size: var(--font-size-sm); }
.history-search { display: flex; flex-direction: column; gap: var(--spacing-md); }
.history-search__controls { grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: var(--spacing-md); }
.history-search__controls > .btn { min-height: var(--input-height-lg); }
.history-dropdown { min-width: 0; }
.history-empty { display: flex; align-items: center; justify-content: center; gap: var(--spacing-sm); padding: var(--spacing-xl) var(--spacing-md); border: 1px dashed var(--color-border-light); border-radius: var(--radius-sm); }
.history-search .form-control, .history-result__actions .form-control { min-width: 0; min-height: var(--input-height-lg); }
.history-search-results { display: flex; flex-direction: column; gap: var(--spacing-sm); }
.history-result { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: var(--spacing-md); padding: var(--spacing-sm) var(--spacing-md); background: var(--surface-glass-subtle); border: 1px solid var(--color-border-light); border-radius: var(--radius-sm); }
.history-result__title { min-width: 0; color: var(--color-text-primary); font-weight: var(--font-weight-medium); }
.history-result small, .history-table td small { color: var(--color-text-muted); font-size: var(--font-size-xs); }
.history-result__actions { grid-template-columns: minmax(calc(var(--spacing-3xl) * 1.25), 1fr) auto; }
.history-table-wrap { overflow-x: auto; border: 1px solid var(--color-border-light); border-radius: var(--radius-sm); }
.history-table { width: 100%; border-collapse: collapse; color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.history-table th, .history-table td { padding: var(--spacing-sm) var(--spacing-md); text-align: left; border-bottom: 1px solid var(--surface-glass-light); }
.history-table th { color: var(--color-text-muted); font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold); text-transform: uppercase; }
.history-table tbody tr:last-child td { border-bottom: 0; }
.history-table td:last-child { width: 1%; }
@media (max-width: 700px) {
  .history-tools { row-gap: var(--spacing-lg); }
  .history-tools > .history-section { display: flex; grid-row: auto; }
  .history-tools, .history-import-controls, .history-search__controls, .history-result { grid-template-columns: minmax(0, 1fr); }
  .history-tools > .history-section + .history-section { border-left: 0; padding-left: 0; border-top: 1px solid var(--color-border-light); padding-top: var(--spacing-lg); }
  .history-result__actions { grid-template-columns: minmax(0, 1fr) auto; }
}
</style>
