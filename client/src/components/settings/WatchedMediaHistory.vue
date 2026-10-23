<template>
  <SectionCard id="ratings-content" icon="fas fa-star" title="Watch history" description="Everything you played on your media server, plus titles you watched elsewhere. Watched titles are never suggested again.">
    <template #actions>
      <button type="button" class="ui-btn" @click="showImport = true"><i aria-hidden="true" class="fas fa-file-import"></i>Import CSV</button>
    </template>

    <form class="flex flex-wrap gap-2" role="search" @submit.prevent="search">
      <label class="sr-only" for="watchedSearch">Search TMDb</label>
      <input id="watchedSearch" v-model.trim="query" type="search" class="ui-input flex-[1_1_220px]" placeholder="Add a movie or series you watched elsewhere">
      <label class="sr-only" for="watchedSearchType">Media type</label>
      <select id="watchedSearchType" v-model="searchType" class="ui-input w-auto">
        <option v-for="option in searchTypeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
      <button type="submit" class="ui-btn-primary" :disabled="query.length < 2 || isSearching">
        <i aria-hidden="true" :class="isSearching ? 'fas fa-spinner fa-spin' : 'fas fa-search'"></i>Search
      </button>
    </form>
    <ul v-if="searchResults.length" class="m-0 mt-3 flex max-h-64 list-none flex-col gap-1.5 overflow-y-auto p-0">
      <li v-for="result in searchResults" :key="`${result.media_type}:${result.tmdb_id}`" class="flex flex-wrap items-center gap-2 rounded-[8px] border border-edge bg-panel-2 px-3 py-2">
        <span class="min-w-0 flex-1 text-sm text-ink">{{ result.title }} <small class="text-ink-4">({{ result.year || '—' }}) · {{ result.media_type === 'tv' ? 'TV' : 'Movie' }}</small></span>
        <label class="sr-only" :for="`rating-${result.media_type}-${result.tmdb_id}`">Your rating for {{ result.title }}</label>
        <input :id="`rating-${result.media_type}-${result.tmdb_id}`" v-model.number="ratings[`${result.media_type}:${result.tmdb_id}`]" class="ui-input h-9 w-24" type="number" min="0" max="10" step="0.5" placeholder="Rating">
        <button type="button" class="ui-btn h-9 px-3" :disabled="addingKey === `${result.media_type}:${result.tmdb_id}`" @click="addResult(result)">
          <i aria-hidden="true" :class="addingKey === `${result.media_type}:${result.tmdb_id}` ? 'fas fa-spinner fa-spin' : 'fas fa-plus'"></i>Add
        </button>
      </li>
    </ul>

    <AppDialog v-if="showImport" title="Import a CSV" icon="fas fa-file-import" @close="closeImport">
      <div class="flex flex-col gap-3">
        <p class="m-0 text-sm leading-relaxed text-ink-2">UTF-8 file with a header row and these columns:</p>
        <code class="block rounded-ctl border border-edge bg-canvas px-3 py-2 font-mono text-[13px] text-ink">tmdb_id,media_type,title,year,rating</code>
        <p class="m-0 text-xs text-ink-4"><code>media_type</code> is <code>movie</code> or <code>tv</code>. Rating is optional, from 0 to 10.</p>
        <div class="flex items-center gap-2">
          <input ref="file" type="file" hidden accept=".csv,text/csv" :disabled="isImporting" @change="onFileChange">
          <button type="button" class="ui-btn shrink-0" :disabled="isImporting" @click="$refs.file.click()">
            <i aria-hidden="true" class="fas fa-folder-open"></i>Choose file
          </button>
          <span class="min-w-0 flex-1 truncate text-[13px] text-ink-3" aria-live="polite" :title="importFile?.name">{{ importFile?.name || 'No file selected' }}</span>
        </div>
      </div>
      <template #footer>
        <button type="button" class="ui-btn" :disabled="isImporting" @click="closeImport">Cancel</button>
        <button type="button" class="ui-btn-primary" :disabled="!importFile || isImporting" @click="importCsv">
          <i aria-hidden="true" :class="isImporting ? 'fas fa-spinner fa-spin' : 'fas fa-file-import'"></i>{{ isImporting ? 'Importing…' : 'Import' }}
        </button>
      </template>
    </AppDialog>

    <div class="mb-2 mt-5 flex flex-wrap items-center gap-2">
      <h3 class="m-0 mr-auto text-sm font-bold text-ink">Your titles <span v-if="items.length" class="font-normal text-ink-4">({{ filteredItems.length }}<template v-if="filteredItems.length !== items.length"> of {{ items.length }}</template>)</span></h3>
      <template v-if="mediaUsers.length">
        <label class="sr-only" for="ratingsProfile">Profile</label>
        <select id="ratingsProfile" v-model="mediaUser" class="ui-input h-9 w-auto" @change="load">
          <option value="">My profile</option>
          <option v-for="user in mediaUsers" :key="user.external_user_id" :value="user.external_user_id">{{ user.external_username || user.external_user_id }}</option>
        </select>
      </template>
      <label class="sr-only" for="ratingsFilter">Filter titles</label>
      <input id="ratingsFilter" v-model.trim="filterText" type="search" class="ui-input h-9 w-48" placeholder="Filter titles">
      <label class="sr-only" for="ratingsFilterType">Media type</label>
      <select id="ratingsFilterType" v-model="filterType" class="ui-input h-9 w-auto">
        <option v-for="option in filterTypeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
      <label class="sr-only" for="ratingsFilterState">Rating state</label>
      <select id="ratingsFilterState" v-model="filterState" class="ui-input h-9 w-auto">
        <option v-for="option in filterStateOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
    </div>
    <p v-if="isSyncing || serverNote" class="m-0 mb-2 text-xs text-ink-4" aria-live="polite">
      <template v-if="isSyncing"><i aria-hidden="true" class="fas fa-spinner fa-spin"></i> Checking your media server for new plays…</template>
      <template v-else>{{ serverNote }}</template>
    </p>
    <p v-if="isLoading" class="m-0 text-[13px] text-ink-4">Loading your watch history…</p>
    <p v-else-if="notLinked" class="m-0 rounded-ctl border border-dashed border-edge-strong px-4 py-6 text-center text-[13px] text-ink-4">Link your media server account in <router-link :to="{ name: 'DashboardTab', params: { tab: 'profile' } }">Profile</router-link> to rate your titles.</p>
    <p v-else-if="!items.length" class="m-0 rounded-ctl border border-dashed border-edge-strong px-4 py-6 text-center text-[13px] text-ink-4">Nothing watched yet. Titles you play on your media server, import or add here show up in this list.</p>
    <p v-else-if="!filteredItems.length" class="m-0 rounded-ctl border border-dashed border-edge-strong px-4 py-6 text-center text-[13px] text-ink-4">No titles match these filters.</p>
    <div v-else class="overflow-x-auto rounded-ctl border border-edge">
      <table class="w-full min-w-[640px] border-collapse text-sm">
        <thead><tr class="text-left text-xs text-ink-4"><th class="px-3 py-2.5 font-semibold">Title</th><th class="px-3 py-2.5 font-semibold">Type</th><th class="px-3 py-2.5 font-semibold">Rating</th><th class="px-3 py-2.5 font-semibold">Source</th><th class="px-3 py-2.5 font-semibold">Use for suggestions</th><th class="px-3 py-2.5"><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>
          <tr v-for="item in shownItems" :key="rowKey(item)" class="border-t border-edge" :class="{ 'opacity-60': item.excluded }">
            <td class="px-3 py-2 text-ink">{{ item.title }} <small v-if="item.year" class="text-ink-4">({{ item.year }})</small></td>
            <td class="px-3 py-2 text-ink-2">{{ item.media_type === 'tv' ? 'TV' : 'Movie' }}</td>
            <td class="px-3 py-1">
              <label class="sr-only" :for="`saved-rating-${rowKey(item)}`">Your rating for {{ item.title }}</label>
              <input :id="`saved-rating-${rowKey(item)}`" :value="item.rating" class="ui-input h-9 w-24" type="number" min="0" max="10" step="0.5" placeholder="—" :disabled="savingKey === rowKey(item)" @change="saveRating(item, $event.target)">
            </td>
            <td class="px-3 py-2 text-ink-2">{{ sourceLabels[item.source] || 'Manual' }}</td>
            <td class="px-3 py-2">
              <input type="checkbox" class="h-4 w-4 cursor-pointer accent-brand" :checked="!item.excluded" :disabled="savingKey === rowKey(item)" :aria-label="`Use ${item.title} for suggestions`" title="Off: still counts as watched, but says nothing about your taste" @change="update(item, { excluded: !$event.target.checked })">
            </td>
            <td class="px-3 py-1 text-right">
              <!-- Media-server plays come back on the next sync, so only titles added here can be removed. -->
              <button v-if="item.source !== 'server'" type="button" class="ui-btn-icon-danger" :aria-label="`Remove ${item.title}`" title="Remove" @click="remove(item)"><i aria-hidden="true" class="fas fa-trash"></i></button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <button v-if="filteredItems.length > shownItems.length" type="button" class="ui-btn mt-3" @click="pageSize += 100">Show more ({{ filteredItems.length - shownItems.length }} left)</button>
  </SectionCard>
</template>
<script>
import {
  addMyWatchedMedia,
  deleteMyWatchedMedia,
  importMyWatchedMedia,
  listMyWatchedMedia,
  listTraktMediaUsers,
  searchMyWatchedMedia,
  syncMyWatchedMedia,
  updateMyWatchedMedia,
} from '@/api/api';
import AppDialog from '@/components/ui/AppDialog.vue';
import SectionCard from '@/components/ui/SectionCard.vue';
import { confirmDialog } from '@/utils/confirmDialog';

export default {
  name: 'WatchedMediaHistory',
  components: { AppDialog, SectionCard },
  props: { currentUser: { type: Object, default: null } },
  data() {
    return {
      items: [], importFile: null, query: '', searchType: 'both', searchResults: [], ratings: {},
      isLoading: false, isImporting: false, showImport: false, isSearching: false, addingKey: '', savingKey: '', notLinked: false,
      mediaUser: '', mediaUsers: [], serverStatus: '', isSyncing: false, filterText: '', filterType: 'all', filterState: 'all', pageSize: 100,
      sourceLabels: { csv_import: 'CSV import', manual: 'Manual', server: 'Media server' },
      filterTypeOptions: [
        { value: 'all', label: 'Movies and TV' },
        { value: 'movie', label: 'Movies' },
        { value: 'tv', label: 'TV shows' },
      ],
      filterStateOptions: [
        { value: 'all', label: 'All titles' },
        { value: 'unrated', label: 'Unrated' },
        { value: 'rated', label: 'Rated' },
        { value: 'excluded', label: 'Not used for suggestions' },
      ],
      searchTypeOptions: [
        { value: 'both', label: 'Movies and TV' },
        { value: 'movie', label: 'Movies' },
        { value: 'tv', label: 'TV shows' },
      ],
    };
  },
  computed: {
    filteredItems() {
      const text = this.filterText.toLowerCase();
      return this.items.filter(item => (this.filterType === 'all' || item.media_type === this.filterType)
        && (!text || String(item.title).toLowerCase().includes(text))
        && (this.filterState === 'all'
          || (this.filterState === 'excluded' ? item.excluded : (this.filterState === 'rated') === (item.rating != null))));
    },
    shownItems() { return this.filteredItems.slice(0, this.pageSize); },
    serverNote() {
      return {
        partial: 'Only your most recent plays could be loaded from the media server.',
        unavailable: 'The media server could not be reached, so only titles saved here are shown.',
      }[this.serverStatus] || '';
    },
  },
  watch: {
    filterText() { this.pageSize = 100; },
    filterType() { this.pageSize = 100; },
    filterState() { this.pageSize = 100; },
  },
  mounted() {
    this.load();
    if (this.currentUser?.role === 'admin') {
      listTraktMediaUsers().then(response => { this.mediaUsers = response.data.media_users || []; }).catch(() => {});
    }
  },
  methods: {
    rowKey(item) { return `${item.media_type}:${item.tmdb_id}`; },
    async load() {
      this.isLoading = true;
      this.pageSize = 100;
      this.serverStatus = '';
      const user = this.mediaUser;
      try {
        this.items = (await listMyWatchedMedia(user)).data.items || [];
        this.notLinked = false;
      } catch (error) {
        this.items = [];
        this.notLinked = error.response?.status === 404;
        if (!this.notLinked) this.$toast.error(error.response?.data?.message || 'Could not load recommendation history');
        return;
      } finally { this.isLoading = false; }
      this.sync(user);
    },
    async sync(user) {
      // Saved titles are already on screen; only new plays need the media server.
      this.isSyncing = true;
      try {
        const data = (await syncMyWatchedMedia(user)).data;
        if (user !== this.mediaUser) return;
        this.serverStatus = data.server_status || '';
        if (data.updated) this.items = (await listMyWatchedMedia(user)).data.items || [];
      } catch {
        if (user === this.mediaUser) this.serverStatus = 'unavailable';
      } finally { this.isSyncing = false; }
    },
    closeImport() { this.showImport = false; this.importFile = null; },
    onFileChange(event) { [this.importFile] = event.target.files || []; },
    async importCsv() {
      if (!this.importFile) return;
      this.isImporting = true;
      try {
        const result = (await importMyWatchedMedia(this.importFile, this.mediaUser)).data;
        this.$toast.success(result.message);
        if (result.errors?.length) this.$toast.error(`${result.errors.length} row(s) could not be imported`);
        this.closeImport();
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
        await addMyWatchedMedia({ ...result, rating: this.ratings[key] ?? null }, this.mediaUser);
        this.$toast.success(`${result.title} added to your recommendation history`);
        await this.load();
      } catch (error) { this.$toast.error(error.response?.data?.message || 'Could not add title'); }
      finally { this.addingKey = ''; }
    },
    saveRating(item, input) {
      const rating = input.value === '' ? null : Number(input.value);
      if (rating !== null && !(rating >= 0 && rating <= 10)) {
        input.value = item.rating ?? '';
        this.$toast.error('Rating must be a number from 0 to 10');
        return;
      }
      if (rating !== item.rating) this.update(item, { rating });
    },
    async update(item, changes) {
      const key = this.rowKey(item);
      this.savingKey = key;
      try {
        const saved = (await updateMyWatchedMedia(item.id, changes, this.mediaUser)).data.item;
        this.items = this.items.map(entry => (this.rowKey(entry) === key ? saved : entry));
      } catch (error) {
        this.$toast.error(error.response?.data?.message || 'Could not update title');
        await this.load();
      } finally { this.savingKey = ''; }
    },
    async remove(item) {
      if (!(await confirmDialog({ title: `Remove ${item.title}?`, message: 'It no longer shapes your recommendations.', confirmLabel: 'Remove', danger: true }))) return;
      try { await deleteMyWatchedMedia(item.id, this.mediaUser); this.items = this.items.filter(entry => entry.id !== item.id); }
      catch (error) { this.$toast.error(error.response?.data?.message || 'Could not remove title'); }
    },
  },
};
</script>
