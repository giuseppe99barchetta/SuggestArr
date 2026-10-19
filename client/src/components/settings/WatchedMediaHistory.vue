<template>
  <SectionCard id="profile-history-content" icon="fas fa-book-open" title="Recommendation history" description="Titles you watched outside your media server. They personalise suggestions and are never suggested again.">
    <div class="grid gap-5 md:grid-cols-2">
      <div class="flex min-w-0 flex-col gap-3 rounded-ctl border border-edge bg-panel-2 p-4">
        <h3 class="m-0 text-sm font-bold text-ink">Import a CSV</h3>
        <p class="m-0 text-[13px] leading-relaxed text-ink-3">UTF-8 with the columns <code>tmdb_id,media_type,title,year,rating</code>. Rating is optional, from 0 to 10.</p>
        <div class="flex flex-wrap items-center gap-2">
          <input ref="file" type="file" hidden accept=".csv,text/csv" :disabled="isImporting" @change="onFileChange">
          <button type="button" class="ui-btn" :disabled="isImporting" @click="$refs.file.click()">
            <i aria-hidden="true" class="fas fa-folder-open"></i>Choose CSV
          </button>
          <span class="min-w-0 flex-1 truncate text-[13px] text-ink-3" aria-live="polite" :title="importFile?.name">{{ importFile?.name || 'No file selected' }}</span>
          <button type="button" class="ui-btn-primary" :disabled="!importFile || isImporting" @click="importCsv">
            <i aria-hidden="true" :class="isImporting ? 'fas fa-spinner fa-spin' : 'fas fa-file-import'"></i>{{ isImporting ? 'Importing…' : 'Import' }}
          </button>
        </div>
      </div>

      <div class="flex min-w-0 flex-col gap-3 rounded-ctl border border-edge bg-panel-2 p-4">
        <h3 class="m-0 text-sm font-bold text-ink">Add a title</h3>
        <form class="flex flex-wrap gap-2" role="search" @submit.prevent="search">
          <label class="sr-only" for="watchedSearch">Search TMDb</label>
          <input id="watchedSearch" v-model.trim="query" type="search" class="ui-input flex-[1_1_180px]" placeholder="Movie or series title">
          <label class="sr-only" for="watchedSearchType">Media type</label>
          <select id="watchedSearchType" v-model="searchType" class="ui-input w-auto">
            <option v-for="option in searchTypeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
          <button type="submit" class="ui-btn" :disabled="query.length < 2 || isSearching">
            <i aria-hidden="true" :class="isSearching ? 'fas fa-spinner fa-spin' : 'fas fa-search'"></i>Search
          </button>
        </form>
        <ul v-if="searchResults.length" class="m-0 flex max-h-64 list-none flex-col gap-1.5 overflow-y-auto p-0">
          <li v-for="result in searchResults" :key="`${result.media_type}:${result.tmdb_id}`" class="flex flex-wrap items-center gap-2 rounded-[8px] bg-canvas px-3 py-2">
            <span class="min-w-0 flex-1 text-sm text-ink">{{ result.title }} <small class="text-ink-4">({{ result.year || '—' }}) · {{ result.media_type === 'tv' ? 'TV' : 'Movie' }}</small></span>
            <label class="sr-only" :for="`rating-${result.media_type}-${result.tmdb_id}`">Your rating for {{ result.title }}</label>
            <input :id="`rating-${result.media_type}-${result.tmdb_id}`" v-model.number="ratings[`${result.media_type}:${result.tmdb_id}`]" class="ui-input h-9 w-24" type="number" min="0" max="10" step="0.5" placeholder="Rating">
            <button type="button" class="ui-btn h-9 px-3" :disabled="addingKey === `${result.media_type}:${result.tmdb_id}`" @click="addResult(result)">
              <i aria-hidden="true" :class="addingKey === `${result.media_type}:${result.tmdb_id}` ? 'fas fa-spinner fa-spin' : 'fas fa-plus'"></i>Add
            </button>
          </li>
        </ul>
      </div>
    </div>

    <h3 class="m-0 mb-2 mt-5 text-sm font-bold text-ink">Your titles <span v-if="items.length" class="font-normal text-ink-4">({{ items.length }})</span></h3>
    <p v-if="isLoading" class="m-0 text-[13px] text-ink-4">Loading watched titles…</p>
    <p v-else-if="!items.length" class="m-0 rounded-ctl border border-dashed border-edge-strong px-4 py-6 text-center text-[13px] text-ink-4">Nothing added yet. Imported and manually added titles show up here, private to your linked account.</p>
    <div v-else class="overflow-x-auto rounded-ctl border border-edge">
      <table class="w-full min-w-[520px] border-collapse text-sm">
        <thead><tr class="text-left text-xs text-ink-4"><th class="px-3 py-2.5 font-semibold">Title</th><th class="px-3 py-2.5 font-semibold">Type</th><th class="px-3 py-2.5 font-semibold">Rating</th><th class="px-3 py-2.5 font-semibold">Source</th><th class="px-3 py-2.5"><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>
          <tr v-for="item in items" :key="item.id" class="border-t border-edge">
            <td class="px-3 py-2 text-ink">{{ item.title }} <small v-if="item.year" class="text-ink-4">({{ item.year }})</small></td>
            <td class="px-3 py-2 text-ink-2">{{ item.media_type === 'tv' ? 'TV' : 'Movie' }}</td>
            <td class="px-3 py-2 text-ink-2">{{ item.rating ?? '—' }}</td>
            <td class="px-3 py-2 text-ink-2">{{ item.source === 'csv_import' ? 'CSV import' : 'Manual' }}</td>
            <td class="px-3 py-1 text-right"><button type="button" class="ui-btn-icon-danger" :aria-label="`Remove ${item.title}`" title="Remove" @click="remove(item)"><i aria-hidden="true" class="fas fa-trash"></i></button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </SectionCard>
</template>
<script>
import {
  addMyWatchedMedia,
  deleteMyWatchedMedia,
  importMyWatchedMedia,
  listMyWatchedMedia,
  searchMyWatchedMedia,
} from '@/api/api';
import SectionCard from '@/components/ui/SectionCard.vue';
import { confirmDialog } from '@/utils/confirmDialog';

export default {
  name: 'WatchedMediaHistory',
  components: { SectionCard },
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
      if (!(await confirmDialog({ title: `Remove ${item.title}?`, message: 'It no longer shapes your recommendations.', confirmLabel: 'Remove', danger: true }))) return;
      try { await deleteMyWatchedMedia(item.id); this.items = this.items.filter(entry => entry.id !== item.id); }
      catch (error) { this.$toast.error(error.response?.data?.message || 'Could not remove title'); }
    },
  },
};
</script>
