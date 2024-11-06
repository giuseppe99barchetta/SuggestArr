<template>
  <transition name="fade" mode="out-in">
    <div class="request-container bg-fixed bg-center min-h-screen flex flex-col items-center py-4 px-2 sm:px-4 lg:px-8"
      :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }">
      <div
        class="request-content p-4 sm:p-6 bg-gray-800 bg-opacity-90 rounded-lg shadow-lg w-full max-w-3xl lg:max-w-4xl">
        <!-- Back Button -->
        <button @click="goHome"
          class="p-0 bg-transparent border-none text-gray-300 hover:text-gray-400 focus:outline-none mb-4 sm:mb-6 flex items-center">
          <i class="fas fa-arrow-left mr-2 text-xl"></i>
          <span class="text-sm">Back to Home</span>
        </button>

        <!-- Logo -->
        <div class="flex items-center justify-center mb-4">
          <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank">
            <img src="@/assets/logo.png" alt="SuggestArr Logo" class="w-20 h-auto">
          </a>
        </div>

        <!-- Search Bar -->
        <div class="mb-6 text-center">
          <input v-model="searchQuery" type="text" placeholder="Search requests..." class="search-input w-full" />
        </div>

        <!-- Section Title -->
        <h2 class="text-2xl font-semibold text-white text-center mb-5">Recently Watched Content</h2>

        <!-- Content Grid -->
        <transition-group name="fade-slide" tag="div"
          class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-6">
          <div v-for="source in filteredSources" :key="source.id" class="source-box p-4 rounded-lg shadow-md">
            <div class="flex flex-col space-y-3">
              <div class="relative">
                <div class="relative w-full h-24 overflow-hidden rounded-md">
                  <img v-if="source.backdrop_path" :src="source.backdrop_path" :alt="source.title"
                    class="w-full h-full object-cover" @click="openModal(source)" />

                  <!-- Logo overlay -->
                  <div v-if="source.logo_path" @click="openModal(source)"
                    class="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50">
                    <img :src="source.logo_path" alt="Logo"
                      class="content-logo h-16 max-w-[50%] object-contain" />
                  </div>

                  <!-- Title fallback if logo is missing -->
                  <div v-else class="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50">
                    <h2 class="text-lg font-semibold text-white text-center px-2">{{ source.title }}</h2>
                  </div>
                </div>

                <!-- Badges -->
                <div class="flex flex-wrap gap-1 mt-3">
                  <span class="text-xs bg-blue-600 text-white px-2 py-1 rounded-lg">{{ source.media_type.toUpperCase()
                    }}</span>
                  <span class="text-xs bg-green-600 text-white px-2 py-1 rounded-lg">Rating: {{ source.rating || 'N/A'
                    }}</span>
                  <span class="text-xs bg-yellow-600 text-white px-2 py-1 rounded-lg">Released: {{ source.release_date }}</span>
                </div>

                <!-- Toggle Requests -->
                <div @click="source.showRequests = !source.showRequests"
                  class="text-xs font-semibold text-blue-400 mt-3 cursor-pointer flex items-center space-x-2">
                  <i :class="source.showRequests ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
                  <span>{{ source.showRequests ? 'Hide Requested Media' : 'View Requested Media' }}</span>
                </div>

                <div v-show="source.showRequests" class="mt-3 space-y-2">
                  <div v-for="request in source.requests" :key="request.request_id"
                    class="request-box p-3 rounded-md flex items-center space-x-4 bg-gray-700">
                    <img v-if="request.poster_path" :src="request.poster_path" :alt="request.title"
                      class="w-16 h-16 object-cover rounded-md" @click="openModal(request)" />
                    <div class="flex-grow">
                      <h4 class="font-semibold text-white">{{ request.title }}</h4>
                      <p class="text-xs text-gray-500">Requested at: {{ request.requested_at }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </transition-group>

        <!-- Modal for source details -->
        <transition name="fade">
          <div v-if="showModal"
            class="modal-overlay fixed inset-0 flex items-center justify-center z-50 bg-black bg-opacity-70">
            <div
              class="modal-content relative p-6 sm:p-8 bg-gray-900 rounded-lg shadow-lg w-full max-w-md sm:max-w-3xl flex flex-col sm:flex-row items-center sm:items-start">
              <!-- Close Button -->
              <button @click="closeModal" class="text-gray-400 hover:text-gray-200 absolute top-4 right-4 text-xl">
                <i class="fas fa-times"></i>
              </button>

              <!-- Left Section: Cover Image -->
              <div class="w-full sm:w-1/3 mb-4 sm:mb-0">
                <img v-if="selectedSource.poster_path" :src="selectedSource.poster_path" :alt="selectedSource.title"
                  class="w-full h-auto object-cover rounded-md shadow-md" />
              </div>

              <!-- Right Section: Details -->
              <div class="w-full sm:w-2/3 sm:pl-6 text-gray-300">
                <h2 class="text-3xl font-bold text-white mb-4">{{ selectedSource.title }}</h2>

                <div class="modal-separator"></div>

                <div class="mb-4 space-y-2">
                  <div class="flex flex-wrap gap-1 mt-3">
                  <span class="text-xs bg-blue-600 text-white px-2 py-1 rounded-lg">{{ selectedSource.media_type.toUpperCase()
                    }}</span>
                  <span class="text-xs bg-green-600 text-white px-2 py-1 rounded-lg">Rating: {{ selectedSource.rating || 'N/A'
                    }}</span>
                  <span class="text-xs bg-yellow-600 text-white px-2 py-1 rounded-lg">Released: {{ selectedSource.release_date }}</span>
                  <span v-if="selectedSource.requested_at" class="text-xs bg-purple-600 text-white px-2 py-1 rounded-lg">Requested: {{ selectedSource.requested_at }}</span>
                </div>
                  <p><strong>Overview:</strong> <span class="text-gray-400">{{ selectedSource.overview }}</span></p>
                </div>

                <div v-if="selectedSource.requests">
                  <h3 class="text-lg font-semibold text-gray-400 mb-2">Requested Media:</h3>
                  <ul class="space-y-2">
                    <li v-for="request in selectedSource.requests" :key="request.request_id"
                      class="text-sm bg-gray-800 p-3 rounded-md flex justify-between items-center shadow">
                      <div>
                        <strong>{{ request.title }}</strong>
                        <p class="text-xs text-gray-500">Requested on: {{ request.requested_at }}</p>
                      </div>
                      <button class="hover:underline" @click="openModal(request)">Details</button>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </transition>

        <!-- Load More Trigger -->
        <div v-if="currentPage < totalPages" ref="loadMoreTrigger"
          class="load-more text-center text-gray-400 mt-6 mx-auto">
          <i class="fas fa-spinner fa-spin text-xl sm:text-2xl"></i>
        </div>

        <!-- No Requests Found -->
        <div v-if="filteredSources.length === 0" class="text-center text-gray-500 mt-6">
          <p>No requests found.</p>
        </div>

        <Footer />
      </div>
    </div>
  </transition>
</template>

<script>
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
      searchQuery: "",
      showModal: false,
      selectedSource: null,
      loading: false,
      currentPage: 1,
      totalPages: 1, // Placeholder for pagination
    };
  },
  computed: {
    filteredSources() {
      const query = this.searchQuery.toLowerCase();
      return this.sources.filter((source) => {
        const sourceMatch = source.title && source.title.toLowerCase().includes(query);
        const requestMatch = source.requests.some((request) =>
          request.title && request.title.toLowerCase().includes(query)
        );
        return sourceMatch || requestMatch;
      });
    },
  },
  watch: {
    totalPages() {
      this.initObserver();
    },
    currentPage() {
      this.initObserver();
    },
  },
  methods: {
    async observeIntersection(entries) {
      if (entries[0].isIntersecting && !this.loading) {
        await this.fetchRequests(this.currentPage + 1);
      }
    },
    initObserver() {
      if (this.observer) {
        this.observer.disconnect();
      }
      this.$nextTick(() => {
        const loadMoreTrigger = this.$refs.loadMoreTrigger;
        if (loadMoreTrigger) {
          this.observer = new IntersectionObserver(this.observeIntersection, {
            root: null,
            threshold: 1.0,
          });
          this.observer.observe(loadMoreTrigger);
        }
      });
    },
    async fetchRequests(page = 1) {
      if (page > this.totalPages) return; // Evita richieste oltre il numero di pagine
      this.loading = true;
      try {
        const response = await axios.get(`/api/automation/requests?page=${page}`);
        const { data, total_pages } = response.data;
        this.sources = [...this.sources, ...data.map((sourceData) => ({
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
        }))];
        this.totalPages = total_pages;
        this.currentPage = page;
      } catch (error) {
        console.error("Failed to fetch requests:", error);
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
    },
    closeModal() {
      this.showModal = false;
      this.selectedSource = null;
    },
  },
  created() {
    this.fetchRequests();
    console.log('TMDB_API_KEY:', this.apiKey);
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
  },
};

</script>

<style scoped>

.content-logo {
  max-width: 70%;
  height: 80%;
  object-fit: contain;
}

.request-container {
  background-color: #1a202c;
  position: relative;
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}

.request-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: -1;
}

.request-content {
  padding: 30px;
  background-color: #2d3748e7;
  border-radius: 15px;
  max-width: 850px;
  width: 100%;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
  min-width: 80%;
}

.search-input {
  color: #ffffff;
  background-color: #2d3748;
  border: 1px solid #4a5568;
  padding: 10px;
  border-radius: 5px;
  font-size: 1rem;
}

.source-box {
  background-color: #1a202c;
  color: #e2e8f0;
  transition: transform 0.3s ease;
}

.source-box img {
  transition: transform 0.3s ease;
}

.source-box:hover img {
  transform: scale(1.05);
}

.source-box .absolute {
  transition: opacity 0.3s ease;
}

.source-box:hover .absolute {
  opacity: 1;
}

.request-box {
  background-color: #2d3748;
  color: #cbd5e0;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.5s ease, transform 0.5s ease;
}

.fade-slide-enter {
  opacity: 0;
  transform: translateY(20px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}

.cursor-pointer {
  cursor: pointer;
}

.modal-overlay {
  background: rgba(0, 0, 0, 0.75);
}

.modal-content {
  max-height: 90vh;
  overflow-y: auto;
  transition: all 0.3s ease-in-out;
  background-color: #2d3748e7;
}

ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.load-more {
  height: 50px;
  background: transparent;
}

.line-clamp {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.modal-separator {
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  margin: 16px 0;
}

@media (min-width: 640px) {
  .request-content {
    max-width: 100%;
  }
}

@media (min-width: 1024px) {
  .request-content {
    max-width: 850px;
  }
}
</style>
