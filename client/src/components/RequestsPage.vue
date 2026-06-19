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
            <button @click="goHome" class="back-button">
              <i class="fas fa-arrow-left"></i>
              <span>Back to Home</span>
            </button>
            <div class="header-spacer"></div>
          </div>

          <div class="header-content">
            <h1 class="page-title">Request History</h1>
            <p class="page-subtitle">Track your content requests and viewing patterns</p>
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
            <!-- Filter Buttons -->
            <div class="filter-bar">
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
            
              <!-- Clear Filters -->
              <button 
                v-if="sortBy !== 'date-desc' || mediaTypeFilter !== 'all'" 
                @click="clearFilters" 
                class="clear-filters-btn">
                <i class="fas fa-undo"></i>
                <span>Reset</span>
              </button>
            </div>
          </div>
        
          <!-- Search Results Count -->
          <div class="search-results-count" v-if="searchQuery || mediaTypeFilter !== 'all'">
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
                      {{ source.rating || 'N/A' }}
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
              <RequestPosterCard
                v-for="item in aiRequests"
                :key="item.request_id"
                :item="item"
                source-mode="ai"
                placeholder-icon="fas fa-magic"
                :show-missing-rating="false"
                @select="openModal($event, true)" />
            </transition-group>
            <div v-if="aiRequestsHasMore" ref="loadMoreTriggerAi" class="load-more-trigger">
              <div class="spinner-small"></div>
              <p>Loading more...</p>
            </div>
          </div>

          <!-- View: All Requests -->
          <div v-else key="all-requests">
            <transition-group 
              name="fade-slide" 
              tag="div"
              class="requests-grid">
              <RequestPosterCard
                v-for="request in filteredAndSortedRequests" 
                :key="request.request_id"
                :item="request"
                @select="openModal" />
            </transition-group>


          </div>
        </transition>
        <div
          v-if="hasMoreData && viewMode !== 'ai-requests'"
          :ref="viewMode === 'by-content' ? 'loadMoreTrigger' : 'loadMoreTriggerRequests'"
          class="load-more-trigger">
          <div class="spinner-small"></div>
          <p>Loading more requests...</p>
        </div>
        <!-- No Results -->
        <div v-if="viewMode !== 'ai-requests' && (viewMode === 'by-content' ? filteredAndSortedSources : filteredAndSortedRequests).length === 0 && !loading" class="no-results">
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

      <RequestDetailsModal
        :show="showModal"
        :selected-source="selectedSource"
        @close="closeModal"
        @select-related="openModal" />
    </div>
</template>

<script>
import '@/assets/styles/requestsPage.css';
import axios from "axios";
import { useBackgroundImage } from '@/composables/useBackgroundImage';
import Footer from './AppFooter.vue';
import BaseDropdown from '@/components/common/BaseDropdown.vue';
import RequestPosterCard from '@/components/common/RequestPosterCard.vue';
import RequestDetailsModal from '@/components/common/RequestDetailsModal.vue';
import { formatDate } from '@/utils/dateUtils.js';
import { getRequestSourceVisual } from '@/utils/jobTypeVisuals.js';
import { getAiSearchRequests } from '@/api/api.js';

export default {
  name: "RequestsPage",
  components: {
    Footer,
    BaseDropdown,
    RequestPosterCard,
    RequestDetailsModal,
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
      ]
    };
  },
  computed: {
    totalRequests() {
      return this.totalRequestsCount || this.sources.reduce((sum, source) => sum + source.requests.length, 0);
    },

    totalSources() {
      return this.totalSourcesCount || this.sources.length;
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
    viewMode(newMode) {
      if (newMode === 'ai-requests') return; // handled by switchToAiRequests
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
    
    searchQuery() {
      this.$nextTick(() => {
        this.initObserver();
      });
    },
  },
  methods: {
    formatDate,

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

        const response = await axios.get('/api/automation/requests', { params });
        const { data, total_pages, total_sources, total_requests } = response.data;
        
        if (page === 1) {
          this.totalSourcesCount = total_sources;
          this.totalRequestsCount = total_requests;
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

    closeModal() {
      this.showModal = false;
      this.selectedSource = null;
      document.body.style.overflow = 'auto';
    },
  },
  mounted() {
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
