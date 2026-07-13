<template>
    <div class="request-container" :class="{ 'static-bg-active': config.ENABLE_STATIC_BACKGROUND }">
      <div class="background-container">
        <template v-if="!config.ENABLE_STATIC_BACKGROUND">
          <div
            class="background-layer"
            :class="activeBg === 'bg1' ? 'bg-visible' : 'bg-hidden'"
            :style="{ backgroundImage: 'url(' + bg1Url + ')' }"
          ></div>
          <div
            class="background-layer"
            :class="activeBg === 'bg2' ? 'bg-visible' : 'bg-hidden'"
            :style="{ backgroundImage: 'url(' + bg2Url + ')' }"
          ></div>
        </template>
        <div
          v-if="config.ENABLE_STATIC_BACKGROUND"
          class="background-layer static-bg"
          :style="{ backgroundColor: config.STATIC_BACKGROUND_COLOR }"
        ></div>
      </div>
      <div class="background-overlay"></div>
      <div class="request-content">
        <!-- Header -->
        <div class="request-header">
          <!-- Back Button -->
          <div class="header-top">
            <button type="button" class="back-button" @click="goHome">
              <i class="fas fa-arrow-left"></i>
              <span>Back to Home</span>
            </button>
            <div class="header-spacer"></div>
          </div>

          <div class="header-content">
            <h1 class="page-title">Requests</h1>
            <p class="page-subtitle">Review approvals and track requests sent to Seer</p>
          </div>
        </div>

        <!-- View Toggle -->
        <div class="view-toggle-section">
          <div class="view-toggle">
            <button
              @click="viewMode = 'by-content'" 
              :class="{ active: viewMode === 'by-content' }"
              class="view-toggle-btn">
              <i class="fas fa-film"></i>
              <span>By Watched Content</span>
              <span class="view-count">{{ totalSources }}</span>
            </button>
            <button
              @click="viewMode = 'all-requests'"
              :class="{ active: viewMode === 'all-requests' }"
              class="view-toggle-btn">
              <i class="fas fa-list"></i>
              <span>All Requests</span>
              <span class="view-count">{{ totalRequests }}</span>
            </button>
            <button
              @click="switchToAiRequests"
              :class="{ active: viewMode === 'ai-requests' }"
              class="view-toggle-btn">
              <i class="fas fa-magic"></i>
              <span>AI Requests</span>
              <span class="view-count">{{ aiRequestsTotal }}</span>
            </button>
          </div>
        </div>

        <!-- Filters & Search Bar -->
        <div class="filters-section">
          <!-- Container per affiancare filtri e search -->
          <div class="filters-search-container">
            <!-- Search Bar (affiancata ai filtri) -->
            <div class="search-wrapper">
              <i class="fas fa-search search-icon"></i>
              <input 
                v-model="searchQuery" 
                type="text" 
                :placeholder="viewMode === 'by-content' ? 'Search content...' : 'Search requests...'" 
                class="search-input" />
              <span v-if="searchQuery" @click="searchQuery = ''" class="clear-search">
                <i class="fas fa-times"></i>
              </span>
            </div>
            <button type="button" class="mobile-filters-toggle" :class="{ active: showMobileFilters }" :aria-expanded="showMobileFilters.toString()" aria-controls="request-filters" @click="showMobileFilters = !showMobileFilters"><span><i class="fas fa-sliders-h"></i> Filters</span><span v-if="activeFilterCount" class="mobile-filter-count">{{ activeFilterCount }}</span><i class="fas fa-chevron-down mobile-filter-chevron"></i></button>
            <!-- Filter Buttons -->
            <div id="request-filters" class="filter-bar" :class="{ 'mobile-open': showMobileFilters }">
              <!-- Sort By -->
              <BaseDropdown
                v-model="sortBy"
                :options="sortOptions"
                placeholder="Select sort order"
                :disabled="loading"
                id="sortBy"
              />
            
              <!-- Media Type Filter -->
              <BaseDropdown
                v-model="mediaTypeFilter"
                :options="mediaTypeOptions"
                placeholder="Select media type"
                :disabled="loading"
                id="mediaType"
              />

              <BaseDropdown
                v-if="requestUserOptions.length > 1"
                v-model="requestUserFilter"
                :options="requestUserOptions"
                placeholder="Requested for"
                :disabled="loading"
                id="requestUser"
              />

              <BaseDropdown
                v-if="viewMode === 'all-requests' && approvalEnabled"
                v-model="requestStatusFilter"
                :options="requestStatusOptions"
                placeholder="Request status"
                :disabled="loading"
                id="requestStatus"
              />
              <button v-if="viewMode === 'all-requests'" type="button" class="btn btn-outline workflow-bulk-toggle" :class="{ active: workflowBulkMode }" :disabled="!approvalEnabled || requestStatusFilter === 'sent' || workflowTotal < 1" :title="bulkModeDisabledReason" @click="workflowBulkMode = !workflowBulkMode"><i class="fas fa-check-double"></i><span>{{ workflowBulkMode ? 'Exit bulk mode' : 'Bulk mode' }}</span></button>
            
              <!-- Clear Filters -->
              <button 
                v-if="sortBy !== 'date-desc' || mediaTypeFilter !== 'all' || requestUserFilter !== 'all'"
                @click="clearFilters" 
                class="clear-filters-btn"
                aria-label="Reset filters"
                title="Reset filters">
                <i class="fas fa-undo"></i>
              </button>
            </div>
          </div>
        
          <!-- Search Results Count -->
          <div class="search-results-count" v-if="searchQuery || mediaTypeFilter !== 'all' || requestUserFilter !== 'all'">
            Found {{ viewMode === 'by-content' ? filteredAndSortedSources.length : filteredAndSortedRequests.length }} result(s)
          </div>
        </div>

        <!-- View: By Content Watched -->
        <transition name="fade-slide" mode="out-in">
          <div v-if="viewMode === 'by-content'" key="by-content">
            <transition-group 
              name="fade-slide" 
              tag="div"
              class="content-grid">
              <div 
                v-for="source in filteredAndSortedSources" 
                :key="source.id" 
                class="content-card">
                
                <!-- Card Header with Backdrop -->
                <div class="card-header" @click="openModal(source)">
                  <div class="backdrop-container">
                    <img
                      v-if="source.backdrop_path && !source.visual"
                      :src="source.backdrop_path"
                      :alt="source.title"
                      class="backdrop-image" />
                    <div
                      v-else-if="source.visual"
                      class="source-visual-backdrop"
                      :class="source.visual.key"
                      :style="{ background: source.visual.gradient }">
                      <i :class="source.visual.icon" class="source-visual-icon"></i>
                    </div>

                    <!-- Logo overlay -->
                    <div class="backdrop-overlay">
                      <img
                        v-if="source.logo_path && !source.visual"
                        :src="source.logo_path"
                        alt="Logo"
                        class="content-logo" />
                      <h3 v-else class="content-title-overlay">{{ source.title }}</h3>
                    </div>
                  </div>
                </div>

                <!-- Card Body -->
                <div class="card-body">
                  <!-- Badges -->
                  <div class="badge-container">
                    <span v-if="shouldShowSourceMediaBadge(source)" class="badge badge-media">
                      <i :class="source.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
                      {{ source.media_type.toUpperCase() }}
                    </span>
                    <span v-if="!source.visual" class="badge badge-rating">
                      <i class="fas fa-star"></i>
                      {{ formatRating(source.rating) }}
                    </span>
                    <span v-if="!source.visual && source.release_date" class="badge badge-date">
                      <i class="fas fa-calendar"></i>
                      {{ source.release_date }}
                    </span>
                  </div>

                  <!-- Toggle Requests -->
                  <button 
                    @click="source.showRequests = !source.showRequests"
                    class="toggle-requests-btn">
                    <i :class="source.showRequests ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
                    <span>{{ source.showRequests ? 'Hide' : 'View' }} Requested Media ({{ source.requests.length }})</span>
                  </button>

                  <!-- Requests List -->
                  <transition name="expand">
                    <div v-show="source.showRequests" class="requests-list">
                      <div 
                        v-for="request in source.requests" 
                        :key="request.request_id"
                        class="request-item"
                        @click="openModal(request)">
                        <img 
                          v-if="request.poster_path" 
                          :src="request.poster_path" 
                          :alt="request.title"
                          class="request-poster" />
                        <div class="request-info">
                          <h4 class="request-title">{{ request.title }}</h4>
                          <p class="request-date">
                            <i class="fas fa-clock"></i>
                            Requested {{ formatDate(request.requested_at) }}
                          </p>
                          <p v-if="request.user_name || request.user_id" class="request-date">
                            <i class="fas fa-user"></i>
                            For {{ request.user_name || request.user_id }}
                          </p>
                        </div>
                        <i class="fas fa-chevron-right request-arrow"></i>
                      </div>
                    </div>
                  </transition>
                </div>
              </div>
            </transition-group>
          </div>

          <!-- View: AI Requests -->
          <div v-else-if="viewMode === 'ai-requests'" key="ai-requests">
            <transition-group
              name="fade-slide"
              tag="div"
              class="requests-grid">
              <div
                v-for="item in aiRequests"
                :key="item.request_id"
                class="request-card"
                @click="openModal(item, true)">

                <div class="request-card-poster">
                  <img
                    v-if="item.poster_path"
                    :src="item.poster_path"
                    :alt="item.title"
                    class="poster-image" />
                  <div v-else class="poster-placeholder">
                    <i class="fas fa-magic"></i>
                  </div>
                </div>

                <div class="request-card-body">
                  <h3 class="request-card-title">{{ item.title }}</h3>

                  <div class="badge-container">
                    <span class="badge badge-media">
                      <i :class="item.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
                      {{ item.media_type.toUpperCase() }}
                    </span>
                    <span v-if="item.rating" class="badge badge-rating">
                      <i class="fas fa-star"></i>
                      {{ formatRating(item.rating) }}
                    </span>
                    <span class="badge badge-requested">
                      <i class="fas fa-clock"></i>
                      {{ formatDate(item.requested_at) }}
                    </span>
                  </div>

                  <div v-if="item.rationale" class="source-link">
                    <i class="fas fa-search"></i>
                    <span>Search: <em>"{{ item.rationale }}"</em></span>
                  </div>
                  <div v-else class="source-link">
                    <i class="fas fa-magic"></i>
                    <span>From: <strong>AI Search</strong></span>
                  </div>
                </div>
              </div>
            </transition-group>
            <div v-if="aiRequestsHasMore" ref="loadMoreTriggerAi" class="load-more-trigger">
              <div class="spinner-small"></div>
              <p>Loading more...</p>
            </div>
          </div>

          <!-- View: All Requests -->
          <div v-else key="all-requests">
            <div v-if="approvalEnabled && requestStatusFilter === 'all' && workflowTotal > 0" class="requests-section-heading">
              <span class="requests-section-icon"><i class="fas fa-hourglass-half"></i></span>
              <div><h2>Requests in progress</h2><p>Suggestions waiting for approval or still being processed.</p></div>
            </div>
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
              @update:total="workflowTotal = $event"
            />
            <div v-if="approvalEnabled && requestStatusFilter === 'all' && workflowTotal > 0" class="requests-section-heading requests-section-heading--sent">
              <span class="requests-section-icon"><i class="fas fa-check"></i></span>
              <div><h2>Requested media</h2><p>Items already submitted to your media request service.</p></div>
            </div>
            <transition-group 
              v-if="!approvalEnabled || requestStatusFilter === 'all' || requestStatusFilter === 'sent'"
              name="fade-slide" 
              tag="div"
              class="requests-grid">
              <div 
                v-for="request in filteredAndSortedRequests" 
                :key="request.request_id"
                class="request-card"
                @click="openModal(request)">
                
                <div class="request-card-poster">
                  <img 
                    v-if="request.poster_path" 
                    :src="request.poster_path" 
                    :alt="request.title"
                    class="poster-image" />
                  <div v-else class="poster-placeholder">
                    <i class="fas fa-image"></i>
                  </div>
                </div>

                <div class="request-card-body">
                  <h3 class="request-card-title">{{ request.title }}</h3>
                  
                  <!-- Request Badges -->
                  <div class="badge-container">
                    <span class="badge badge-media">
                      <i :class="request.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
                      {{ request.media_type.toUpperCase() }}
                    </span>
                    <span class="badge badge-rating">
                      <i class="fas fa-star"></i>
                      {{ formatRating(request.rating) }}
                    </span>
                    <span class="badge badge-requested">
                      <i class="fas fa-clock"></i>
                      {{ formatDate(request.requested_at) }}
                    </span>
                  </div>

                  <!-- Source Info -->
                  <div class="source-link">
                    <i class="fas fa-arrow-left"></i>
                    <span>From: <strong>{{ request.source_title }}</strong></span>
                  </div>
                  <div v-if="request.user_name || request.user_id" class="source-link">
                    <i class="fas fa-user"></i>
                    <span>For: <strong>{{ request.user_name || request.user_id }}</strong></span>
                  </div>
                </div>
              </div>
            </transition-group>
          </div>
        </transition>
        <div
          v-if="hasMoreData && viewMode !== 'ai-requests' && (viewMode !== 'all-requests' || requestStatusFilter === 'all' || requestStatusFilter === 'sent')"
          :ref="viewMode === 'by-content' ? 'loadMoreTrigger' : 'loadMoreTriggerRequests'"
          class="load-more-trigger">
          <div class="spinner-small"></div>
          <p>Loading more requests...</p>
        </div>
        <!-- No Results -->
        <div v-if="viewMode !== 'ai-requests' && (viewMode !== 'all-requests' || requestStatusFilter === 'all' || requestStatusFilter === 'sent') && (viewMode === 'by-content' ? filteredAndSortedSources : filteredAndSortedRequests).length === 0 && !loading" class="no-results">
          <i class="fas fa-inbox text-6xl mb-4"></i>
          <h3>No {{ viewMode === 'by-content' ? 'content' : 'requests' }} found</h3>
          <p v-if="searchQuery || mediaTypeFilter !== 'all'">Try adjusting your filters</p>
          <p v-else>Start watching content to see suggestions here</p>
        </div>
        <div v-if="viewMode === 'ai-requests' && aiRequests.length === 0 && !loading" class="no-results">
          <i class="fas fa-magic text-6xl mb-4"></i>
          <h3>No AI Search requests yet</h3>
          <p>Use the <strong>AI Search</strong> tab to discover and request content.</p>
        </div>

        <!-- Initial Loading -->
        <div v-if="loading && sources.length === 0" class="loading-initial">
          <div class="spinner"></div>
          <p>Loading your requests...</p>
        </div>

        <Footer />
      </div>

      <!-- Modal -->
      <transition name="fade">
        <div 
          v-if="showModal" 
          class="modal-overlay" 
          @click.self="closeModal">
          <div class="modal-content">
            <!-- Close Button -->
            <button @click="closeModal" class="modal-close">
              <i class="fas fa-times"></i>
            </button>

            <div class="modal-layout">
              <!-- Left: Poster -->
              <div class="modal-poster-section">
                <img
                  v-if="selectedSource.poster_path && !getSourceVisual(selectedSource)"
                  :src="selectedSource.poster_path"
                  :alt="selectedSource.title"
                  class="modal-poster" />
                <div
                  v-else-if="getSourceVisual(selectedSource)"
                  class="modal-poster-placeholder source-visual-modal"
                  :class="getSourceVisual(selectedSource).key"
                  :style="{ background: getSourceVisual(selectedSource).gradient }">
                  <i :class="getSourceVisual(selectedSource).icon" class="source-visual-icon"></i>
                </div>
                <div v-else class="modal-poster-placeholder">
                  <i class="fas fa-image text-6xl"></i>
                </div>
              </div>

              <!-- Right: Details -->
              <div class="modal-details-section">
                <h2 class="modal-title">{{ selectedSource.title }}</h2>

                <!-- Badges -->
                <div class="badge-container mb-4">
                  <span class="badge badge-media">
                    <i :class="selectedSource.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
                    {{ selectedSource.media_type?.toUpperCase() }}
                  </span>
                  <span class="badge badge-rating">
                    <i class="fas fa-star"></i>
                    {{ formatRating(selectedSource.rating) }}
                  </span>
                  <span class="badge badge-date">
                    <i class="fas fa-calendar"></i>
                    {{ selectedSource.release_date }}
                  </span>
                  <span v-if="selectedSource.requested_at" class="badge badge-requested">
                    <i class="fas fa-clock"></i>
                    Requested {{ formatDate(selectedSource.requested_at) }}
                  </span>
                  <span v-if="selectedSource.source_origin === 'trakt_history'" class="badge badge-date">
                    <i class="fas fa-history"></i>
                    Trakt History
                  </span>
                </div>

                <!-- Source Link (for requests view) -->
                <div v-if="selectedSource.source_title" class="source-link-modal">
                  <i class="fas fa-link"></i>
                  <span>Requested from: <strong>{{ selectedSource.source_title }}</strong></span>
                </div>

                <!-- Requested For (user) -->
                <div v-if="selectedSource.user_name || selectedSource.user_id" class="source-link-modal">
                  <i class="fas fa-user"></i>
                  <span>Requested for: <strong>{{ selectedSource.user_name || selectedSource.user_id }}</strong></span>
                </div>

                <div class="modal-separator"></div>

                <!-- LLM Rationale / Search Query -->
                <div v-if="selectedSource.rationale" class="modal-section">
                  <h3 class="modal-section-title" :style="selectedSource._isAiRequest ? 'color: var(--color-info)' : 'color: #a855f7'">
                    <i :class="selectedSource._isAiRequest ? 'fas fa-search' : 'fas fa-robot'"></i>
                    {{ selectedSource._isAiRequest ? 'Search Query' : 'AI Reasoning' }}
                  </h3>
                  <p class="modal-overview" :style="selectedSource._isAiRequest ? 'border-left: 3px solid var(--color-info); padding-left: 1rem; margin-top: 0.5rem;' : 'font-style: italic; border-left: 3px solid #a855f7; padding-left: 1rem; margin-top: 0.5rem; white-space: pre-wrap;'">
                    {{ selectedSource.rationale }}
                  </p>
                </div>

                <!-- Overview -->
                <div class="modal-section">
                  <h3 class="modal-section-title">
                    <i class="fas fa-align-left"></i>
                    Overview
                  </h3>
                  <p class="modal-overview">{{ selectedSource.overview || 'No overview available.' }}</p>
                </div>

                <!-- Related Requests -->
                <div v-if="selectedSource.requests && selectedSource.requests.length > 0" class="modal-section">
                  <h3 class="modal-section-title">
                    <i class="fas fa-list"></i>
                    Requested Media ({{ selectedSource.requests.length }})
                  </h3>
                  <div class="modal-requests-list">
                    <div
                      v-for="request in selectedSource.requests"
                      :key="request.request_id"
                      class="modal-request-item"
                      @click="openModal(request)">
                      <div class="flex-1">
                        <h4 class="modal-request-title">{{ request.title }}</h4>
                        <p class="modal-request-date">
                          <i class="fas fa-clock"></i>
                          Requested on {{ formatDate(request.requested_at) }}
                        </p>
                        <p v-if="request.user_name || request.user_id" class="modal-request-date">
                          <i class="fas fa-user"></i>
                          {{ request.user_name || request.user_id }}
                        </p>
                      </div>
                      <button class="modal-request-btn">
                        <i class="fas fa-external-link-alt"></i>
                        Details
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </transition>
    </div>
</template>

<script>
import '@/assets/styles/requestsPage.css';
import axios from "axios";
import { useBackgroundImage } from '@/composables/useBackgroundImage';
import Footer from './AppFooter.vue';
import BaseDropdown from '@/components/common/BaseDropdown.vue';
import { formatDate } from '@/utils/dateUtils.js';
import { getRequestSourceVisual } from '@/utils/jobTypeVisuals.js';
import { getAiSearchRequests } from '@/api/api.js';
import RequestWorkflowPanel from './RequestWorkflowPanel.vue';

export default {
  name: "RequestsPage",
  components: {
    Footer,
    BaseDropdown,
    RequestWorkflowPanel,
  },
  setup() {
    const { bg1Url, bg2Url, activeBg, isTransitioning, startDefaultImageRotation, startBackgroundImageRotation, stopBackgroundImageRotation } = useBackgroundImage();
    return {
      bg1Url,
      bg2Url,
      activeBg,
      isTransitioning,
      startDefaultImageRotation,
      startBackgroundImageRotation,
      stopBackgroundImageRotation,
    };
  },
  data() {
    return {
      defaultImages: ["/images/default1.jpg", "/images/default2.jpg", "/images/default3.jpg"],
      currentDefaultImageIndex: 0,
      config: {},
      sources: [],
      viewMode: 'all-requests',
      searchQuery: "",
      sortBy: 'date-desc',
      mediaTypeFilter: 'all',
      requestUserFilter: 'all',
      requestUsers: [],
      showModal: false,
      selectedSource: null,
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
      showMobileFilters: false,
      workflowBulkMode: false,
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
    activeFilterCount() {
      return Number(this.sortBy !== 'date-desc') + Number(this.mediaTypeFilter !== 'all') + Number(this.requestUserFilter !== 'all') + Number(this.requestStatusFilter !== 'all') + Number(this.workflowBulkMode);
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
        const workflow = await axios.get('/api/automation/requests/workflow', { params: { status: this.requestStatusFilter, page: 1, per_page: 1 } });
        this.workflowTotal = workflow.data.total || 0;
      } catch (error) {
        console.error('Error loading approval jobs:', error);
      }
    },

    formatDate,
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

    goHome() {
      this.$router.push({ name: "Home" });
    },

    openModal(source, isAiRequest = false) {
      this.selectedSource = { ...source, _isAiRequest: isAiRequest };
      this.showModal = true;
      document.body.style.overflow = 'hidden';
    },
    openWorkflowModal(item) {
      this.openModal({
        ...item,
        poster_path: item.poster_path ? `https://image.tmdb.org/t/p/w500${item.poster_path}` : null,
        requested_at: item.created_at,
        source_title: item.name
      });
    },

    closeModal() {
      this.showModal = false;
      this.selectedSource = null;
      document.body.style.overflow = 'auto';
    },
  },
  mounted() {
    this.loadApprovalState();
    if (this.$route.query.status) {
      this.viewMode = 'all-requests';
      this.requestStatusFilter = this.$route.query.status;
    }
    const savedConfig = localStorage.getItem('suggestarr_config');
    if (savedConfig) {
      try {
        const config = JSON.parse(savedConfig);
        this.config = config || {};
      } catch (e) {
        console.error('❌ Failed to parse saved config:', e);
      }
    }

    this.$nextTick(() => {
      if (this.config.ENABLE_STATIC_BACKGROUND) {
        // do not start rotation
      } else {
        this.startBackgroundImageRotation();
      }
    });

    setTimeout(() => {
      this.fetchRequests();

      this.$nextTick(() => {
        this.initObserver();
      });
    }, 300);
  },

  beforeUnmount() {
    this.stopBackgroundImageRotation();
    this.cleanupObserver();
    document.body.style.overflow = 'auto';
  },
};
</script>
