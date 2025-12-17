<template>
  <transition name="fade" mode="out-in">
    <div class="request-container" :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">
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
              <div class="filter-group">
                <label class="filter-label">
                  <i class="fas fa-sort"></i>
                  Sort By
                </label>
                <select v-model="sortBy" class="filter-select">
                  <option value="date-desc">Date (Newest)</option>
                  <option value="date-asc">Date (Oldest)</option>
                  <option value="title-asc">Title (A-Z)</option>
                  <option value="title-desc">Title (Z-A)</option>
                  <option value="rating-desc">Rating (High-Low)</option>
                  <option value="rating-asc">Rating (Low-High)</option>
                </select>
              </div>
            
              <!-- Media Type Filter -->
              <div class="filter-group">
                <label class="filter-label">
                  <i class="fas fa-filter"></i>
                  Type
                </label>
                <select v-model="mediaTypeFilter" class="filter-select">
                  <option value="all">All Types</option>
                  <option value="movie">Movies</option>
                  <option value="tv">TV Shows</option>
                </select>
              </div>
            
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
                      v-if="source.backdrop_path" 
                      :src="source.backdrop_path" 
                      :alt="source.title"
                      class="backdrop-image" />
                    
                    <!-- Logo overlay -->
                    <div class="backdrop-overlay">
                      <img 
                        v-if="source.logo_path" 
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
                    <span class="badge badge-media">
                      <i :class="source.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i>
                      {{ source.media_type.toUpperCase() }}
                    </span>
                    <span class="badge badge-rating">
                      <i class="fas fa-star"></i>
                      {{ source.rating || 'N/A' }}
                    </span>
                    <span class="badge badge-date">
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

          <!-- View: All Requests -->
          <div v-else key="all-requests">
            <transition-group 
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
                      {{ request.rating || 'N/A' }}
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
                </div>
              </div>
            </transition-group>


          </div>
        </transition>
        <div 
          v-if="hasMoreData" 
          :ref="viewMode === 'by-content' ? 'loadMoreTrigger' : 'loadMoreTriggerRequests'"
          class="load-more-trigger">
          <div class="spinner-small"></div>
          <p>Loading more requests...</p>
        </div>
        <!-- No Results -->
        <div v-if="(viewMode === 'by-content' ? filteredAndSortedSources : filteredAndSortedRequests).length === 0 && !loading" class="no-results">
          <i class="fas fa-inbox text-6xl mb-4"></i>
          <h3>No {{ viewMode === 'by-content' ? 'content' : 'requests' }} found</h3>
          <p v-if="searchQuery || mediaTypeFilter !== 'all'">Try adjusting your filters</p>
          <p v-else>Start watching content to see suggestions here</p>
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
                  v-if="selectedSource.poster_path" 
                  :src="selectedSource.poster_path" 
                  :alt="selectedSource.title"
                  class="modal-poster" />
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
                    {{ selectedSource.rating || 'N/A' }}
                  </span>
                  <span class="badge badge-date">
                    <i class="fas fa-calendar"></i>
                    {{ selectedSource.release_date }}
                  </span>
                  <span v-if="selectedSource.requested_at" class="badge badge-requested">
                    <i class="fas fa-clock"></i>
                    Requested {{ formatDate(selectedSource.requested_at) }}
                  </span>
                </div>

                <!-- Source Link (for requests view) -->
                <div v-if="selectedSource.source_title" class="source-link-modal">
                  <i class="fas fa-link"></i>
                  <span>Requested from: <strong>{{ selectedSource.source_title }}</strong></span>
                </div>

                <div class="modal-separator"></div>

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
  </transition>
</template>

<script>
import '@/assets/styles/requestsPage.css';
import axios from "axios";
import backgroundManager from '@/api/backgroundManager';
import Footer from './AppFooter.vue';
import { fetchRandomMovieImage } from '@/api/tmdbApi';

export default {
  name: "RequestsPage",
  components: {
    Footer,
  },
  mixins: [backgroundManager],
  data() {
    return {
      tmdbApiKey: this.$route.query.tmdbApiKey,
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
      totalSourcesCount: 0,
      totalRequestsCount: 0,
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

      // Filter by media type
      if (this.mediaTypeFilter !== 'all') {
        filtered = filtered.filter(source => source.media_type === this.mediaTypeFilter);
      }

      // Filter by search query
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
  },
  watch: {
    viewMode() {
      this.$nextTick(() => {
        setTimeout(() => {
          this.initObserver();
        }, 400);
      });
    },
    
    sortBy() {
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
    resetAndReload() {
      console.log('🔄 Sorting changed, reloading data...');
      
      if (this.observer) {
        this.observer.disconnect();
        this.observer = null;
      }
      
      this.sources = [];
      this.currentPage = 0;
      this.totalPages = 1;
      this.retryCount = 0;
      
      this.fetchRequests(1);
    },

    clearFilters() {
      this.sortBy = 'date-desc';
      this.mediaTypeFilter = 'all';
      this.searchQuery = '';
    },

    formatDate(dateString) {
      if (!dateString) return 'N/A';
      const date = new Date(dateString);
      const now = new Date();
      const diffTime = Math.abs(now - date);
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      
      if (diffDays === 0) return 'today';
      if (diffDays === 1) return 'yesterday';
      if (diffDays < 7) return `${diffDays} days ago`;
      if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
      return date.toLocaleDateString();
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

    async observeIntersection(entries) {
      if (entries[0].isIntersecting && !this.loading) {
        console.log('🔄 Lazy loading triggered for:', this.viewMode);
        await this.fetchRequests(this.currentPage + 1);
      }
    },

    initObserver() {
      if (this.observer) {
        this.observer.disconnect();
        this.observer = null;
      }

      if (!this.hasMoreData) {
        console.log('❌ No more data to load');
        return;
      }

      this.$nextTick(() => {
        const triggerRef = this.viewMode === 'by-content' 
          ? this.$refs.loadMoreTrigger 
          : this.$refs.loadMoreTriggerRequests;

        console.log('🎯 Init observer for:', this.viewMode, 'Ref exists:', !!triggerRef);

        if (triggerRef) {
          this.observer = new IntersectionObserver(this.observeIntersection, {
            root: null,
            rootMargin: '300px', 
            threshold: 0,
          });
          this.observer.observe(triggerRef);
          console.log('✅ Observer initialized');
        } else {
          console.warn('⚠️ Trigger ref not found, retrying...');
          setTimeout(() => {
            this.initObserver();
          }, 200);
        }
      });
    },

    async fetchRequests(page = 1) {
      if (page > this.totalPages || this.loading) {
        console.log('⛔ Fetch blocked - page:', page, 'loading:', this.loading);
        return;
      }
      
      console.log('📡 Fetching page:', page, 'with sort:', this.sortBy);
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
          })),
        }));

        this.sources = [...this.sources, ...newSources];
        this.totalPages = total_pages;
        this.currentPage = page;

        console.log('✅ Loaded page:', page, 'Total sources:', this.sources.length);

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

    openModal(source) {
      this.selectedSource = source;
      this.showModal = true;
      document.body.style.overflow = 'hidden';
    },

    closeModal() {
      this.showModal = false;
      this.selectedSource = null;
      document.body.style.overflow = 'auto';
    },
  },

  created() {
    this.fetchRequests();
  },

  mounted() {
    this.$nextTick(() => {
      setTimeout(() => {
        this.initObserver();
      }, 500);
    });
    
    if (!this.tmdbApiKey) {
      this.startDefaultImageRotation();
    } else {
      this.startBackgroundImageRotation(fetchRandomMovieImage, this.tmdbApiKey);
    }
  },

  beforeUnmount() {
    this.stopBackgroundImageRotation();
    if (this.observer) {
      this.observer.disconnect();
    }
    document.body.style.overflow = 'auto';
  },
};
</script>
