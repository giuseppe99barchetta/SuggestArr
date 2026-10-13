<template>
  <div class="flex flex-col gap-6">
    <header class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="m-0 text-3xl font-extrabold tracking-tight text-ink">Requests</h1>
        <p class="m-0 mt-1.5 text-[15px] text-ink-3">Approve suggestions and follow what has been sent to Seer.</p>
      </div>
      <button
        v-if="viewMode === 'all-requests' && approvalEnabled"
        type="button"
        class="inline-flex h-10 cursor-pointer items-center gap-2 rounded-ctl border px-4 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
        :class="workflowBulkMode ? 'border-brand-ink bg-brand-soft text-brand-ink' : 'border-edge-strong bg-panel-2 text-ink'"
        :disabled="requestStatusFilter === 'sent' || workflowTotal < 1"
        :title="bulkModeDisabledReason"
        @click="workflowBulkMode = !workflowBulkMode"
      >
        <i aria-hidden="true" class="fas fa-check-double"></i>{{ workflowBulkMode ? 'Exit bulk mode' : 'Select several' }}
      </button>
    </header>

    <div role="tablist" aria-label="Request views" class="-mb-2 flex gap-1 overflow-x-auto border-b border-edge">
      <button
        v-for="tab in viewTabs"
        :key="tab.id"
        type="button"
        role="tab"
        :aria-selected="tab.active ? 'true' : 'false'"
        class="-mb-px inline-flex h-12 shrink-0 cursor-pointer items-center gap-2 border-0 border-b-2 bg-transparent px-3.5 text-sm font-semibold"
        :class="tab.active ? 'border-brand-ink text-white' : 'border-transparent text-ink-3 hover:text-ink'"
        @click="selectTab(tab.id)"
      >
        {{ tab.label }}
        <span v-if="tab.count !== null" class="rounded-full px-2 py-0.5 text-xs" :class="tab.active ? 'bg-brand text-white' : 'bg-raised text-ink-3'">{{ tab.count }}</span>
      </button>
    </div>

    <form role="search" class="flex flex-wrap items-center gap-2.5" @submit.prevent>
      <label class="flex h-[42px] min-w-0 flex-[1_1_260px] items-center gap-2.5 rounded-ctl border border-edge-strong bg-panel px-3.5 text-ink-4 focus-within:border-brand-ink">
        <i aria-hidden="true" class="fas fa-search text-sm"></i>
        <span class="sr-only">Search</span>
        <input v-model="searchQuery" type="search" :placeholder="viewMode === 'by-content' ? 'Search watched titles…' : 'Search by title…'" class="min-w-0 flex-1 border-0 bg-transparent text-sm text-ink outline-none placeholder:text-ink-4" />
      </label>
      <label v-for="control in filterControls" :key="control.key" class="contents">
        <span class="sr-only">{{ control.label }}</span>
        <select
          :value="control.value"
          :disabled="loading"
          class="h-[42px] cursor-pointer rounded-ctl border border-edge-strong bg-panel px-3 text-sm text-ink"
          @change="setFilter(control.key, $event.target.value)"
        >
          <option v-for="option in control.options" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>
      <button
        v-if="sortBy !== 'date-desc' || mediaTypeFilter !== 'all' || requestUserFilter !== 'all' || searchQuery"
        type="button"
        class="h-[42px] cursor-pointer rounded-ctl border-0 bg-transparent px-3 text-sm font-semibold text-ink-3 hover:text-ink"
        @click="clearFilters"
      >
        Reset
      </button>
    </form>

    <!-- By watched title -->
    <div v-if="viewMode === 'by-content'" class="flex flex-col gap-4">
      <section
        v-for="source in filteredAndSortedSources"
        :key="source.id"
        class="flex flex-wrap gap-5 rounded-card border border-edge bg-panel p-4 sm:p-5"
      >
        <button type="button" class="relative aspect-[2/3] w-24 shrink-0 cursor-pointer overflow-hidden rounded-ctl border-0 p-0 sm:w-28" :style="source.visual ? { background: source.visual.gradient } : null" :aria-label="`Details for ${source.title}`" @click="openModal(source)">
          <img v-if="source.poster_path && !source.visual" :src="source.poster_path" alt="" class="absolute inset-0 h-full w-full object-cover" />
          <img v-else-if="source.backdrop_path && !source.visual" :src="source.backdrop_path" alt="" class="absolute inset-0 h-full w-full object-cover" />
          <i aria-hidden="true" v-else-if="source.visual" :class="source.visual.icon" class="text-2xl text-white/90"></i>
        </button>
        <div class="flex min-w-0 flex-[1_1_380px] flex-col gap-3">
          <div class="flex flex-col gap-1">
            <span class="text-xs font-semibold uppercase tracking-wider text-ink-4">{{ source.visual ? 'Suggested by' : 'Because you watched' }}</span>
            <h2 class="m-0 text-xl font-extrabold text-ink">{{ source.title }}</h2>
            <span class="text-[13px] text-ink-4">
              {{ source.requests.length }} {{ source.requests.length === 1 ? 'suggestion' : 'suggestions' }}
              <template v-if="!source.visual && source.rating"> · <i aria-hidden="true" class="fas fa-star text-caution"></i> {{ formatRating(source.rating) }}</template>
              <template v-if="!source.visual && source.release_date"> · {{ source.release_date }}</template>
            </span>
          </div>
          <div class="flex gap-3 overflow-x-auto pb-1">
            <button
              v-for="request in source.requests"
              :key="request.request_id"
              type="button"
              class="flex w-[104px] shrink-0 cursor-pointer flex-col gap-1.5 border-0 bg-transparent p-0 text-left"
              @click="openModal(request)"
            >
              <span class="relative block aspect-[2/3] w-full overflow-hidden rounded-[8px] bg-raised">
                <img v-if="request.poster_path" :src="request.poster_path" alt="" loading="lazy" class="absolute inset-0 h-full w-full object-cover" />
              </span>
              <span class="line-clamp-2 text-xs font-semibold leading-snug text-ink">{{ request.title }}</span>
              <span v-if="request.user_name || request.user_id" class="text-[11px] text-ink-4">For {{ request.user_name || request.user_id }}</span>
            </button>
          </div>
        </div>
      </section>
    </div>

    <!-- AI Search requests -->
    <div v-else-if="viewMode === 'ai-requests'">
      <div class="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-4">
        <MediaCard
          v-for="item in aiRequests"
          :key="item.request_id"
          :title="item.title"
          :poster="item.poster_path || ''"
          :badge="item.media_type === 'movie' ? 'Movie' : 'TV'"
          placeholder-icon="fas fa-magic"
          @open="openModal(item, true)"
        >
          <span v-if="item.rationale" class="line-clamp-2 text-xs italic leading-snug text-ink-3">“{{ item.rationale }}”</span>
          <span class="text-xs text-ink-4">{{ formatDate(item.requested_at) }}</span>
        </MediaCard>
      </div>
      <div v-if="aiRequestsHasMore" ref="loadMoreTriggerAi" class="py-8 text-center text-sm text-ink-4">Loading more…</div>
    </div>

    <!-- Needs approval / All requests -->
    <div v-else class="flex flex-col gap-4">
      <h2 v-if="approvalEnabled && requestStatusFilter === 'all' && workflowTotal > 0" class="m-0 text-lg font-bold text-ink">In progress</h2>
      <RequestWorkflowPanel
        v-if="approvalEnabled && requestStatusFilter !== 'sent'"
        :status-filter="requestStatusFilter"
        :search-query="searchQuery"
        :media-type="mediaTypeFilter"
        :requested-for="requestUserFilter"
        :show-header="false"
        :show-empty="false"
        :bulk-mode="workflowBulkMode"
        @open="openWorkflowModal"
        @update:total="onWorkflowTotal"
      />
      <div v-if="isApprovalTab && workflowTotal === 0" class="flex flex-col items-center gap-2 rounded-card border border-dashed border-edge-strong px-6 py-14 text-center">
        <i aria-hidden="true" class="fas fa-check-circle text-4xl text-good"></i>
        <h2 class="m-0 text-lg font-bold text-ink">You're all caught up</h2>
        <p class="m-0 text-sm text-ink-3">New suggestions that need your approval will show up here.</p>
      </div>
      <h2 v-if="approvalEnabled && requestStatusFilter === 'all' && workflowTotal > 0" class="m-0 mt-4 text-lg font-bold text-ink">Sent to Seer</h2>
      <div v-if="!approvalEnabled || requestStatusFilter === 'all' || requestStatusFilter === 'sent'" class="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-4">
        <MediaCard
          v-for="request in filteredAndSortedRequests"
          :key="request.request_id"
          :title="request.title"
          :poster="request.poster_path || ''"
          badge="Requested"
          tone="notice"
          @open="openModal(request)"
        >
          <span class="text-xs font-semibold text-ink-2">{{ request.media_type === 'movie' ? 'Movie' : 'TV' }}<template v-if="request.rating"> · <i aria-hidden="true" class="fas fa-star text-caution"></i> {{ formatRating(request.rating) }}</template></span>
          <span class="line-clamp-2 text-xs leading-snug text-ink-3">From {{ request.source_title }}</span>
          <span class="text-xs text-ink-4"><template v-if="request.user_name || request.user_id">For {{ request.user_name || request.user_id }} · </template>{{ formatDate(request.requested_at) }}</span>
        </MediaCard>
      </div>
    </div>

    <div
      v-if="hasMoreData && viewMode !== 'ai-requests' && (viewMode !== 'all-requests' || requestStatusFilter === 'all' || requestStatusFilter === 'sent')"
      :ref="viewMode === 'by-content' ? 'loadMoreTrigger' : 'loadMoreTriggerRequests'"
      class="py-8 text-center text-sm text-ink-4"
    >
      Loading more requests…
    </div>

    <div
      v-if="viewMode !== 'ai-requests' && (viewMode !== 'all-requests' || requestStatusFilter === 'all' || requestStatusFilter === 'sent') && (viewMode === 'by-content' ? filteredAndSortedSources : filteredAndSortedRequests).length === 0 && !loading"
      class="flex flex-col items-center gap-2 rounded-card border border-dashed border-edge-strong px-6 py-14 text-center"
    >
      <i aria-hidden="true" class="fas fa-inbox text-4xl text-ink-4"></i>
      <h2 class="m-0 text-lg font-bold text-ink">No {{ viewMode === 'by-content' ? 'titles' : 'requests' }} found</h2>
      <p class="m-0 text-sm text-ink-3">{{ searchQuery || mediaTypeFilter !== 'all' ? 'Try changing the filters.' : 'Requests appear here once a job has run.' }}</p>
    </div>
    <div v-if="viewMode === 'ai-requests' && aiRequests.length === 0 && !loading" class="flex flex-col items-center gap-2 rounded-card border border-dashed border-edge-strong px-6 py-14 text-center">
      <i aria-hidden="true" class="fas fa-magic text-4xl text-ink-4"></i>
      <h2 class="m-0 text-lg font-bold text-ink">No AI Search requests yet</h2>
      <p class="m-0 text-sm text-ink-3">Describe what you feel like watching in <router-link :to="{ name: 'DashboardTab', params: { tab: 'ai_search' } }">AI Search</router-link>.</p>
    </div>

    <div v-if="loading && sources.length === 0" class="py-14 text-center text-sm text-ink-3">
      <i aria-hidden="true" class="fas fa-spinner fa-spin mr-2"></i>Loading your requests…
    </div>

    <MediaDetailsModal
      v-if="showModal"
      :item="selectedSource"
      :trailer-url="trailerUrl"
      :placeholder-icon="getSourceVisual(selectedSource)?.icon || 'fas fa-image'"
      :placeholder-background="getSourceVisual(selectedSource)?.gradient || 'var(--color-raised)'"
      :rationale-title="selectedSource._isAiRequest ? 'Search query' : 'Why it was suggested'"
      @close="closeModal"
    >
      <template #badges>
        <span v-if="selectedSource.requested_at" class="rounded-md bg-raised px-2 py-1 text-ink-2" :title="new Date(selectedSource.requested_at).toLocaleString()"><i aria-hidden="true" class="fas fa-clock"></i> Requested {{ formatDate(selectedSource.requested_at) }}</span>
        <span v-if="selectedSource.source_origin === 'trakt_history'" class="rounded-md bg-raised px-2 py-1 text-ink-2"><i aria-hidden="true" class="fas fa-history"></i> Trakt history</span>
        <span v-if="selectedSource.source_origin === 'simkl_history'" class="rounded-md bg-raised px-2 py-1 text-ink-2"><i aria-hidden="true" class="icon-simkl"></i> Simkl history</span>
      </template>

      <section v-if="canFeedbackSelected" aria-labelledby="media-feedback-title" class="flex flex-col gap-3">
        <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h3 id="media-feedback-title" class="m-0 text-sm font-semibold text-ink-3">Good pick?</h3>
          <div role="group" aria-labelledby="media-feedback-title" class="flex flex-wrap gap-1.5">
            <button
              v-for="option in visibleFeedbackOptions"
              :key="option.value"
              type="button"
              class="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-full border px-3 text-[13px] font-semibold disabled:opacity-50"
              :class="selectedSource.feedback?.feedback === option.value ? 'border-brand-ink bg-brand-soft text-brand-ink' : 'border-edge-strong bg-transparent text-ink-2 hover:border-ink-4'"
              :aria-pressed="(selectedSource.feedback?.feedback === option.value).toString()"
              :disabled="isFeedbackSaving(selectedSource)"
              @click="toggleSelectedFeedback(option.value)"
            >
              <span aria-hidden="true">{{ option.emoji }}</span>{{ option.label }}
            </button>
            <button
              v-if="!feedbackExpanded"
              type="button"
              class="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-full border-0 bg-transparent px-2 text-[13px] font-semibold text-ink-4 hover:text-ink"
              @click="feedbackExpanded = true"
            >
              More <i aria-hidden="true" class="fas fa-chevron-down text-[10px]"></i>
            </button>
          </div>
        </div>
        <div v-if="selectedSource.feedback?.feedback" class="flex flex-wrap items-center gap-x-3 gap-y-2">
          <p id="media-feedback-reason" class="m-0 text-xs font-semibold text-ink-4">Mostly because of <span class="font-normal">(optional)</span></p>
          <div role="group" aria-labelledby="media-feedback-reason" class="flex flex-wrap gap-1.5">
            <button
              v-for="reason in feedbackReasons"
              :key="reason.value"
              type="button"
              class="h-7 cursor-pointer rounded-full border px-2.5 text-xs font-semibold disabled:opacity-50"
              :class="selectedSource.feedback?.reason_type === reason.value ? 'border-brand-ink bg-brand-soft text-brand-ink' : 'border-edge bg-transparent text-ink-3 hover:border-ink-4'"
              :aria-pressed="(selectedSource.feedback?.reason_type === reason.value).toString()"
              :disabled="isFeedbackSaving(selectedSource)"
              @click="setSelectedFeedback(selectedSource.feedback.feedback, selectedSource.feedback.reason_type === reason.value ? null : reason.value)"
            >
              {{ reason.label }}
            </button>
          </div>
        </div>
        <p v-if="isFeedbackSaving(selectedSource)" role="status" class="m-0 text-xs text-ink-4">Saving…</p>
      </section>

      <section v-if="selectedSource.requests && selectedSource.requests.length > 0">
        <h3 class="m-0 mb-2 text-xs font-bold uppercase tracking-wider text-ink-4">Suggestions from this title ({{ selectedSource.requests.length }})</h3>
        <ul class="m-0 flex list-none flex-col gap-1.5 p-0">
          <li v-for="request in selectedSource.requests" :key="request.request_id">
            <button type="button" class="flex w-full cursor-pointer items-center gap-3 rounded-ctl border border-edge bg-panel-2 px-3 py-2.5 text-left hover:border-edge-strong" @click="openModal(request)">
              <span class="flex min-w-0 flex-1 flex-col gap-0.5">
                <span class="truncate text-sm font-semibold text-ink">{{ request.title }}</span>
                <span class="text-xs text-ink-4">{{ formatDate(request.requested_at) }}<template v-if="request.user_name || request.user_id"> · for {{ request.user_name || request.user_id }}</template></span>
              </span>
              <i aria-hidden="true" class="fas fa-chevron-right text-xs text-ink-4"></i>
            </button>
          </li>
        </ul>
      </section>
    </MediaDetailsModal>
  </div>
</template>

<script>
import axios from "axios";
import MediaCard from '@/components/ui/MediaCard.vue';
import MediaDetailsModal from './MediaDetailsModal.vue';
import { formatDate } from '@/utils/dateUtils.js';
import { getRequestSourceVisual } from '@/utils/jobTypeVisuals.js';
import { getAiSearchRequests } from '@/api/api.js';
import RequestWorkflowPanel from './RequestWorkflowPanel.vue';
import { loadTrailerUrl } from '@/utils/trailer.js';

// Shown up front in the details modal; the other answers sit behind "More".
const PRIMARY_FEEDBACK = ['interested', 'not_interested', 'already_seen'];

export default {
  name: "RequestsPage",
  components: {
    MediaCard,
    MediaDetailsModal,
    RequestWorkflowPanel,
  },
  // The dashboard shell passes settings props to every tab; this page does not use them.
  inheritAttrs: false,
  data() {
    return {
      sources: [],
      viewMode: 'all-requests',
      searchQuery: "",
      sortBy: 'date-desc',
      mediaTypeFilter: 'all',
      requestUserFilter: 'all',
      requestUsers: [],
      showModal: false,
      selectedSource: null,
      trailerUrl: null,
      loading: false,
      currentPage: 1,
      totalPages: 1,
      observer: null,
      retryTimeout: null,
      totalSourcesCount: 0,
      totalRequestsCount: 0,
      // AI Requests state
      aiRequests: [],
      aiRequestsTotal: 0,
      aiRequestsPage: 1,
      aiRequestsTotalPages: 1,
      aiObserver: null,
      sortOptions: [
        { value: 'date-desc', label: 'Date (Newest)' },
        { value: 'date-asc', label: 'Date (Oldest)' },
        { value: 'title-asc', label: 'Title (A-Z)' },
        { value: 'title-desc', label: 'Title (Z-A)' },
        { value: 'rating-desc', label: 'Rating (High-Low)' },
        { value: 'rating-asc', label: 'Rating (Low-High)' }
      ],
      mediaTypeOptions: [
        { value: 'all', label: 'All Types' },
        { value: 'movie', label: 'Movies' },
        { value: 'tv', label: 'TV Shows' }
      ],
      requestStatusFilter: 'all',
      approvalEnabled: false,
      workflowTotal: null,
      pendingTotal: null,
      workflowBulkMode: false,
      feedbackSaving: {},
      feedbackExpanded: false,
      feedbackOptions: [
        { value: 'seen_liked', emoji: '👍', label: 'Seen it, liked it' },
        { value: 'seen_disliked', emoji: '👎', label: 'Seen it, did not like it' },
        { value: 'interested', emoji: '😍', label: 'Interested' },
        { value: 'not_interested', emoji: '🙅', label: 'Not interested' },
        { value: 'already_seen', emoji: '👀', label: 'Already seen' },
        { value: 'too_similar', emoji: '🫠', label: 'Too similar' },
        { value: 'save_for_later', emoji: '🔖', label: 'Save for later' },
      ],
      feedbackReasons: [
        { value: 'genre', label: 'Genre' },
        { value: 'provider', label: 'Provider' },
        { value: 'content', label: 'Content' },
        { value: 'title', label: 'Title' },
        { value: 'other', label: 'Other' },
      ],
      requestStatusOptions: [
        { value: 'all', label: 'All statuses' },
        { value: 'awaiting_approval', label: 'Waiting approval' },
        { value: 'queued', label: 'Queued' },
        { value: 'sent', label: 'Sent' },
        { value: 'rejected', label: 'Rejected' },
        { value: 'failed', label: 'Failed' },
        { value: 'blacklisted', label: 'Blacklisted' }
      ]
    };
  },
  computed: {
    /** The three common answers, plus the current one when it is among the rest. */
    visibleFeedbackOptions() {
      if (this.feedbackExpanded) return this.feedbackOptions;
      const current = this.selectedSource?.feedback?.feedback;
      return this.feedbackOptions.filter((option) => PRIMARY_FEEDBACK.includes(option.value) || option.value === current);
    },
    canFeedbackSelected() {
      return Boolean(
        this.selectedSource
        && !this.selectedSource._isAiRequest
        && (this.selectedSource.request_id || this.selectedSource._workflowSuggestionId)
      );
    },
    isApprovalTab() {
      return this.viewMode === 'all-requests' && this.requestStatusFilter === 'awaiting_approval';
    },
    viewTabs() {
      const tabs = [
        { id: 'approval', label: 'Needs approval', count: this.pendingTotal, active: this.isApprovalTab },
        { id: 'all', label: 'All requests', count: this.totalRequests, active: this.viewMode === 'all-requests' && !this.isApprovalTab },
        { id: 'by-content', label: 'By watched title', count: this.totalSources, active: this.viewMode === 'by-content' },
        { id: 'ai', label: 'AI Search', count: this.viewMode === 'ai-requests' || this.aiRequestsTotal ? this.aiRequestsTotal : null, active: this.viewMode === 'ai-requests' },
      ];
      return this.approvalEnabled ? tabs : tabs.slice(1);
    },
    filterControls() {
      const controls = [
        { key: 'sortBy', label: 'Sort', value: this.sortBy, options: this.sortOptions },
        { key: 'mediaTypeFilter', label: 'Media type', value: this.mediaTypeFilter, options: this.mediaTypeOptions },
      ];
      if (this.requestUserOptions.length > 1) {
        controls.push({ key: 'requestUserFilter', label: 'Requested for', value: this.requestUserFilter, options: this.requestUserOptions });
      }
      if (this.viewMode === 'all-requests' && this.approvalEnabled && !this.isApprovalTab) {
        controls.push({ key: 'requestStatusFilter', label: 'Status', value: this.requestStatusFilter, options: this.requestStatusOptions });
      }
      return controls;
    },
    bulkModeDisabledReason() {
      if (!this.approvalEnabled) return 'Bulk mode requires a job with manual approval enabled';
      if (this.requestStatusFilter === 'sent') return 'Sent requests cannot be edited in bulk';
      if (this.workflowTotal === null) return 'Loading requests';
      if (this.workflowTotal === 0) return 'No requests available for bulk actions';
      return '';
    },
    totalRequests() {
      return this.totalRequestsCount || this.sources.reduce((sum, source) => sum + source.requests.length, 0);
    },

    totalSources() {
      return this.totalSourcesCount || this.sources.length;
    },

    requestUserOptions() {
      return [{ value: 'all', label: 'All accounts' }, ...this.requestUsers.map(user => ({ value: String(user.id), label: user.name }))];
    },

    allRequestsFlat() {
      return this.sources.flatMap(source => 
        source.requests.map(req => ({
          ...req,
          source_title: source.title,
          source_id: source.id,
          source_poster: source.poster_path,
          source_backdrop: source.backdrop_path,
          source_logo: source.logo_path,
        }))
      );
    },

    filteredSources() {
      const query = this.searchQuery.toLowerCase();
      let filtered = this.sources;

      if (this.mediaTypeFilter !== 'all') {
        filtered = filtered
          .map((source) => {
            const matchingRequests = source.requests.filter(
              (request) => request.media_type === this.mediaTypeFilter
            );
            if (matchingRequests.length === 0) {
              return null;
            }
            return { ...source, requests: matchingRequests };
          })
          .filter(Boolean);
      }

      if (query) {
        filtered = filtered.filter((source) => {
          const sourceMatch = source.title && source.title.toLowerCase().includes(query);
          const requestMatch = source.requests.some((request) =>
            request.title && request.title.toLowerCase().includes(query)
          );
          return sourceMatch || requestMatch;
        });
      }

      return filtered;
    },

    filteredAllRequests() {
      const query = this.searchQuery.toLowerCase();
      let filtered = [...this.allRequestsFlat];

      // Filter by media type (client-side)
      if (this.mediaTypeFilter !== 'all') {
        filtered = filtered.filter(request => request.media_type === this.mediaTypeFilter);
      }

      // Filter by search query (client-side)
      if (query) {
        filtered = filtered.filter(request =>
          (request.title && request.title.toLowerCase().includes(query)) ||
          (request.source_title && request.source_title.toLowerCase().includes(query))
        );
      }

      return filtered;
    },

    filteredAndSortedSources() {
      return this.filteredSources;
    },

    filteredAndSortedRequests() {
      return this.filteredAllRequests;
    },

    hasMoreData() {
      return this.currentPage < this.totalPages;
    },

    aiRequestsHasMore() {
      return this.aiRequestsPage < this.aiRequestsTotalPages;
    },
  },
  watch: {
    workflowTotal(value) {
      if (value === 0) this.workflowBulkMode = false;
    },
    requestStatusFilter() {
      this.workflowBulkMode = false;
      this.workflowTotal = null;
    },
    viewMode(newMode) {
      if (newMode === 'ai-requests') return;
      this.$nextTick(() => {
        setTimeout(() => {
          this.initObserver();
        }, 400);
      });
    },

    sortBy() {
      if (this.viewMode === 'ai-requests') {
        this.aiRequests = [];
        this.aiRequestsPage = 1;
        this.fetchAiRequests(1);
        return;
      }
      this.resetAndReload();
    },
    
    mediaTypeFilter() {
      this.$nextTick(() => {
        this.initObserver();
      });
    },

    requestUserFilter() {
      this.resetAndReload();
    },
    
    searchQuery() {
      this.$nextTick(() => {
        this.initObserver();
      });
    },
  },
  methods: {
    async loadApprovalState() {
      try {
        const { data } = await axios.get('/api/jobs');
        this.approvalEnabled = (data.jobs || []).some(job => job.delivery_mode === 'manual');
        if (!this.approvalEnabled) {
          this.requestStatusFilter = 'sent';
          this.workflowTotal = 0;
          return;
        }
        const pending = await axios.get('/api/automation/requests/workflow', { params: { status: 'awaiting_approval', page: 1, per_page: 1 } });
        this.pendingTotal = pending.data.total || 0;
        // Open on the approval queue when something is waiting, unless a link asked for a status.
        if (this.pendingTotal > 0 && !this.$route.query.status && this.viewMode === 'all-requests') {
          this.requestStatusFilter = 'awaiting_approval';
        }
        const workflow = await axios.get('/api/automation/requests/workflow', { params: { status: this.requestStatusFilter, page: 1, per_page: 1 } });
        this.workflowTotal = workflow.data.total || 0;
      } catch (error) {
        console.error('Error loading approval jobs:', error);
      }
    },

    formatDate,
    feedbackKey(request) {
      return request._workflowSuggestionId
        ? `workflow:${request._workflowSuggestionId}`
        : `${request.media_type}:${request.request_id}:${request.user_id || ''}`;
    },
    isFeedbackSaving(request) {
      return Boolean(this.feedbackSaving[this.feedbackKey(request)]);
    },
    syncSentFeedback(request, feedback) {
      for (const source of this.sources) {
        for (const item of source.requests) {
          if (this.feedbackKey(item) === this.feedbackKey(request)) item.feedback = feedback;
        }
      }
      if (this.selectedSource && this.feedbackKey(this.selectedSource) === this.feedbackKey(request)) {
        this.selectedSource.feedback = feedback;
      }
    },
    async setSentFeedback(requestItem, feedback, reasonType) {
      const key = this.feedbackKey(requestItem);
      this.feedbackSaving = { ...this.feedbackSaving, [key]: true };
      try {
        const url = `/api/automation/requests/media/${requestItem.media_type}/${encodeURIComponent(requestItem.request_id)}/feedback`;
        if (feedback) {
          const payload = { feedback, media_user_id: requestItem.user_id || null };
          if (reasonType !== undefined) payload.reason_type = reasonType || null;
          const response = await axios.put(url, payload);
          this.syncSentFeedback(requestItem, response.data.feedback);
        } else {
          await axios.delete(url, { data: { media_user_id: requestItem.user_id || null } });
          this.syncSentFeedback(requestItem, null);
        }
        this.$toast.open({ message: feedback ? 'Feedback saved' : 'Feedback cleared', type: 'success' });
      } catch (error) {
        this.$toast.open({ message: error.response?.data?.message || 'Unable to save feedback', type: 'error' });
      } finally {
        const saving = { ...this.feedbackSaving };
        delete saving[key];
        this.feedbackSaving = saving;
      }
    },
    async setSelectedFeedback(feedback, reasonType) {
      if (!this.selectedSource) return;
      if (!this.selectedSource._workflowSuggestionId) {
        await this.setSentFeedback(this.selectedSource, feedback, reasonType);
        return;
      }

      const key = this.feedbackKey(this.selectedSource);
      this.feedbackSaving = { ...this.feedbackSaving, [key]: true };
      try {
        const url = `/api/automation/requests/workflow/${this.selectedSource._workflowSuggestionId}/feedback`;
        if (feedback) {
          const payload = { feedback };
          if (reasonType !== undefined) payload.reason_type = reasonType;
          const response = await axios.put(url, payload);
          this.selectedSource.feedback = response.data.feedback;
        } else {
          await axios.delete(url);
          this.selectedSource.feedback = null;
        }
        this.$toast.open({ message: feedback ? 'Feedback saved' : 'Feedback cleared', type: 'success' });
      } catch (error) {
        this.$toast.open({ message: error.response?.data?.message || 'Unable to save feedback', type: 'error' });
      } finally {
        const saving = { ...this.feedbackSaving };
        delete saving[key];
        this.feedbackSaving = saving;
      }
    },
    toggleSelectedFeedback(feedback) {
      const current = this.selectedSource?.feedback?.feedback;
      return this.setSelectedFeedback(current === feedback ? '' : feedback);
    },
    formatRating(value) {
      if (value === null || value === undefined || value === '') return 'N/A';
      const rating = Number(value);
      return Number.isFinite(rating) ? rating.toFixed(1) : 'N/A';
    },

    getSourceVisual(source) {
      return source?.visual ?? getRequestSourceVisual(source);
    },

    shouldShowSourceMediaBadge(source) {
      if (!source?.media_type) {
        return false;
      }
      if (source.visual && this.sourceHasMixedMediaTypes(source)) {
        return false;
      }
      return true;
    },

    sourceHasMixedMediaTypes(source) {
      const types = new Set((source?.requests || []).map((request) => request.media_type));
      return types.size > 1;
    },

    resetAndReload() {
      console.log('🔄 Sorting changed, reloading data...');

      this.cleanupObserver();

      this.sources = [];
      this.currentPage = 0;
      this.totalPages = 1;
      this.retryCount = 0;

      this.fetchRequests(1);
    },

    selectTab(id) {
      if (id === 'ai') {
        this.switchToAiRequests();
        return;
      }
      if (id === 'by-content') {
        this.viewMode = 'by-content';
        return;
      }
      this.viewMode = 'all-requests';
      this.requestStatusFilter = id === 'approval' ? 'awaiting_approval' : 'all';
    },

    setFilter(key, value) {
      this[key] = value;
    },

    onWorkflowTotal(total) {
      this.workflowTotal = total;
      if (this.isApprovalTab) this.pendingTotal = total;
    },

    switchToAiRequests() {
      this.viewMode = 'ai-requests';
      if (this.aiRequests.length === 0) {
        this.fetchAiRequests(1);
      }
    },

    async fetchAiRequests(page = 1) {
      if (this.loading) return;
      this.loading = true;
      try {
        const response = await getAiSearchRequests(page, 12, this.sortBy);
        const { data, total, total_pages } = response.data;
        if (page === 1) {
          this.aiRequests = data;
          this.aiRequestsTotal = total;
        } else {
          this.aiRequests = [...this.aiRequests, ...data];
        }
        this.aiRequestsPage = page;
        this.aiRequestsTotalPages = total_pages;
        this.$nextTick(() => {
          setTimeout(() => this.initAiObserver(), 150);
        });
      } catch (error) {
        console.error('❌ Failed to fetch AI search requests:', error);
      } finally {
        this.loading = false;
      }
    },

    initAiObserver() {
      if (this.aiObserver) {
        this.aiObserver.disconnect();
        this.aiObserver = null;
      }
      if (!this.aiRequestsHasMore) return;
      this.$nextTick(() => {
        const trigger = this.$refs.loadMoreTriggerAi;
        if (trigger) {
          this.aiObserver = new IntersectionObserver(async (entries) => {
            if (entries[0].isIntersecting && !this.loading) {
              await this.fetchAiRequests(this.aiRequestsPage + 1);
            }
          }, { rootMargin: '300px', threshold: 0 });
          this.aiObserver.observe(trigger);
        }
      });
    },

    clearFilters() {
      this.sortBy = 'date-desc';
      this.mediaTypeFilter = 'all';
      this.requestUserFilter = 'all';
      this.searchQuery = '';
    },



    async observeIntersection(entries) {
      if (entries[0].isIntersecting && !this.loading) {
        console.log('🔄 Lazy loading triggered for:', this.viewMode);
        await this.fetchRequests(this.currentPage + 1);
      }
    },

    reinitObserverAfterFilter() {
      this.$nextTick(() => {
        setTimeout(() => {
          this.initObserver();
        }, 100);
      });
    },

    initObserver() {
      // Cleanup existing observer
      this.cleanupObserver();

      if (!this.hasMoreData) {
        console.log('❌ No more data to load');
        return;
      }

      this.$nextTick(() => {
        const triggerRef = this.viewMode === 'by-content' 
          ? this.$refs.loadMoreTrigger 
          : this.$refs.loadMoreTriggerRequests;

        if (triggerRef) {
          this.observer = new IntersectionObserver(this.observeIntersection, {
            root: null,
            rootMargin: '300px', 
            threshold: 0,
          });
          this.observer.observe(triggerRef);
        } else {
          console.warn('⚠️ Trigger ref not found, retrying...');
          this.retryTimeout = setTimeout(() => {
            this.initObserver();
          }, 200);
        }
      });
    },

    cleanupObserver() {
      if (this.observer) {
        this.observer.disconnect();
        this.observer = null;
      }
      if (this.retryTimeout) {
        clearTimeout(this.retryTimeout);
        this.retryTimeout = null;
      }
    },

    async fetchRequests(page = 1) {
      if (page > this.totalPages || this.loading) {
        console.log('⛔ Fetch blocked - page:', page, 'loading:', this.loading);
        return;
      }
      
      this.loading = true;
      
      try {
        const params = {
          page: page,
          sort_by: this.sortBy,
        };
        if (this.requestUserFilter !== 'all') params.user_id = this.requestUserFilter;

        const response = await axios.get('/api/automation/requests', { params });
        const { data, total_pages, total_sources, total_requests, request_users } = response.data;
        
        if (page === 1) {
          this.totalSourcesCount = total_sources;
          this.totalRequestsCount = total_requests;
          if (this.requestUserFilter === 'all') this.requestUsers = request_users || [];
        }
        
        const newSources = data.map((sourceData) => ({
          id: sourceData.source_id,
          title: sourceData.source_title,
          release_date: sourceData.source_release_date,
          overview: sourceData.source_overview,
          poster_path: sourceData.source_poster_path,
          rating: sourceData.rating,
          media_type: sourceData.media_type,
          showRequests: false,
          logo_path: sourceData.logo_path,
          backdrop_path: sourceData.backdrop_path,
          visual: getRequestSourceVisual({
            id: sourceData.source_id,
            title: sourceData.source_title,
          }),
          requests: sourceData.requests.map((request) => ({
            request_id: request.request_id,
            title: request.title,
            media_type: request.media_type,
            requested_at: request.requested_at,
            overview: request.overview,
            poster_path: request.poster_path,
            release_date: request.release_date,
            rating: request.rating,
            logo_path: request.logo_path,
            backdrop_path: request.backdrop_path,
            rationale: request.rationale,
            user_id: request.user_id,
            user_name: request.user_name,
            source_origin: request.source_origin,
            feedback: request.feedback || null,
          })),
        }));

        this.sources = [...this.sources, ...newSources];
        this.totalPages = total_pages;
        this.currentPage = page;

        this.$nextTick(() => {
          setTimeout(() => {
            this.initObserver();
          }, 150);
        });

      } catch (error) {
        console.error("❌ Failed to fetch requests:", error);
        this.$toast.open({
          message: '❌ Failed to load requests',
          type: 'error',
          duration: 5000,
          position: 'top-right'
        });
      } finally {
        this.loading = false;
      }
    },

    openModal(source, isAiRequest = false) {
      this.selectedSource = { ...source, _isAiRequest: isAiRequest };
      this.feedbackExpanded = false;
      this.showModal = true;
      document.body.style.overflow = 'hidden';
      this.loadTrailer();
    },
    async loadTrailer() {
      this.trailerUrl = null;
      const shown = this.selectedSource;
      const url = await loadTrailerUrl(axios, shown);
      // The modal may show another title by the time the answer arrives.
      if (this.selectedSource === shown) this.trailerUrl = url;
    },
    openWorkflowModal(item) {
      this.openModal({
        ...item,
        _workflowSuggestionId: item.id,
        user_id: item.media_user_id,
        poster_path: item.poster_path ? `https://image.tmdb.org/t/p/w500${item.poster_path}` : null,
        requested_at: item.created_at,
        source_title: item.name
      });
    },

    closeModal() {
      this.showModal = false;
      this.selectedSource = null;
      this.trailerUrl = null;
      document.body.style.overflow = 'auto';
    },
  },
  mounted() {
    this.loadApprovalState();
    if (this.$route.query.status) {
      this.viewMode = 'all-requests';
      this.requestStatusFilter = this.$route.query.status;
    }
    setTimeout(() => {
      this.fetchRequests();

      this.$nextTick(() => {
        this.initObserver();
      });
    }, 300);
  },

  beforeUnmount() {
    this.cleanupObserver();
    document.body.style.overflow = 'auto';
  },
};
</script>
