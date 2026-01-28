<template>
    <div class="config-section">
        <h3 class="section-title">Advanced Filter Configuration</h3>
        <p class="section-description">
            Set up advanced filters to customize your content recommendations. Each field below allows you to narrow down suggestions based on specific criteria. All fields are optional.
        </p>

        <!-- Rating & Votes Card -->
        <div class="settings-card">
            <h4 class="card-title">Rating & Popularity Filters</h4>

            <div class="form-row">
                <div class="form-group flex-1">
                    <label for="FILTER_TMDB_THRESHOLD" class="form-label">Minimum Rating</label>
                    <input type="number" :value="config.FILTER_TMDB_THRESHOLD"
                        @input="validateThreshold($event.target.value)"
                        class="form-input"
                        id="FILTER_TMDB_THRESHOLD" placeholder="60" min="0" max="100">
                    <span v-if="errors.FILTER_TMDB_THRESHOLD" class="form-error">{{ errors.FILTER_TMDB_THRESHOLD }}</span>
                </div>

                <div class="form-group flex-1">
                    <label for="FILTER_TMDB_MIN_VOTES" class="form-label">Minimum Votes</label>
                    <input type="number" :value="config.FILTER_TMDB_MIN_VOTES"
                        @input="validateMinVotes($event.target.value)"
                        class="form-input"
                        id="FILTER_TMDB_MIN_VOTES" placeholder="20" min="0">
                    <span v-if="errors.FILTER_TMDB_MIN_VOTES" class="form-error">{{ errors.FILTER_TMDB_MIN_VOTES }}</span>
                </div>
            </div>
            <p class="form-help">
                <i class="fas fa-info-circle"></i>
                Filter by TMDB rating (0-100) and minimum number of votes required
            </p>
        </div>

        <!-- Content Exclusion Card -->
        <div class="settings-card">
            <h4 class="card-title">Content Exclusion Options</h4>

            <div class="space-y-3">
                <div class="toggle-item">
                    <div class="toggle-info">
                        <h4 class="toggle-title">Include content with missing ratings</h4>
                        <p class="toggle-description">Show recommendations even without rating information</p>
                    </div>
                    <label class="switch">
                        <input type="checkbox"
                            :checked="config.FILTER_INCLUDE_NO_RATING"
                            @change="handleUpdate('FILTER_INCLUDE_NO_RATING', $event.target.checked)">
                        <span class="slider round"></span>
                    </label>
                </div>

                <div class="toggle-item">
                    <div class="toggle-info">
                        <h4 class="toggle-title">Exclude downloaded content</h4>
                        <p class="toggle-description">Skip suggesting items already in your library</p>
                    </div>
                    <label class="switch">
                        <input type="checkbox"
                            :checked="config.EXCLUDE_DOWNLOADED"
                            @change="handleUpdate('EXCLUDE_DOWNLOADED', $event.target.checked)">
                        <span class="slider round"></span>
                    </label>
                </div>

                <div class="toggle-item">
                    <div class="toggle-info">
                        <h4 class="toggle-title">Exclude requested content</h4>
                        <p class="toggle-description">Avoid recommending shows or movies you've already requested</p>
                    </div>
                    <label class="switch">
                        <input type="checkbox"
                            :checked="config.EXCLUDE_REQUESTED"
                            @change="handleUpdate('EXCLUDE_REQUESTED', $event.target.checked)">
                        <span class="slider round"></span>
                    </label>
                </div>
            </div>
        </div>

        <!-- Genre & Content Type Card -->
        <div class="settings-card">
            <h4 class="card-title">Genre & Content Filters</h4>

            <div class="form-group">
                <label for="FILTER_GENRES_EXCLUDE" class="form-label">Exclude Genres</label>
                <vue-multiselect v-model="selectedGenres" :options="genres" track-by="id" label="name" multiple
                    placeholder="No excluded genre" @update:modelValue="updateGenres"
                    class="multiselect-genres"
                    id="FILTER_GENRES_EXCLUDE">
                </vue-multiselect>
                <p class="form-help">
                    <i class="fas fa-info-circle"></i>
                    Select genres to exclude from recommendations (e.g., Horror, Documentary)
                </p>
            </div>

            <div class="form-group">
                <label for="FILTER_NUM_SEASONS" class="form-label">Maximum Number of Seasons</label>
                <input type="number" :value="config.FILTER_NUM_SEASONS"
                    @input="validateNumSeasons($event.target.value)"
                    class="form-input"
                    id="FILTER_NUM_SEASONS" placeholder="0 (unlimited)" min="0">
                <p class="form-help">
                    <i class="fas fa-info-circle"></i>
                    Limit TV series by number of seasons (0 = no limit)
                </p>
                <span v-if="errors.FILTER_NUM_SEASONS" class="form-error">{{ errors.FILTER_NUM_SEASONS }}</span>
            </div>
        </div>

        <!-- Streaming & Region Card -->
        <div class="settings-card">
            <h4 class="card-title">Streaming & Regional Filters</h4>

            <div class="form-row">
                <div class="form-group flex-1">
                    <label for="FILTER_REGION_PROVIDER" class="form-label">Region</label>
                    <vue-multiselect v-model="selectedRegion" :options="regions" track-by="iso_3166_1" label="english_name"
                        placeholder="Select a region" @update:modelValue="updateRegion"
                        class="multiselect-region"
                        id="FILTER_REGION_PROVIDER">
                    </vue-multiselect>
                </div>

                <div class="form-group flex-1">
                    <label for="FILTER_STREAMING_SERVICES" class="form-label">Exclude Streaming Services</label>
                    <vue-multiselect v-model="selectedStreamingServices" :options="streamingServices" track-by="provider_id"
                        label="provider_name" multiple placeholder="No excluded service"
                        @update:modelValue="updateStreamingServices"
                        class="multiselect-services"
                        id="FILTER_STREAMING_SERVICES">
                    </vue-multiselect>
                </div>
            </div>
            <p class="form-help">
                <i class="fas fa-info-circle"></i>
                Filter by region and exclude specific streaming services
            </p>
        </div>

        <!-- Language & Year Card -->
        <div class="settings-card">
            <h4 class="card-title">Language & Release Date</h4>

            <div class="form-row">
                <div class="form-group flex-1">
                    <label for="FILTER_LANGUAGE" class="form-label">Original Language</label>
                    <vue-multiselect v-model="selectedLanguages" :options="languages" track-by="iso_639_1"
                        label="english_name" multiple placeholder="No preferred language"
                        @update:modelValue="updateLanguages"
                        class="multiselect-languages"
                        id="FILTER_LANGUAGE">
                    </vue-multiselect>
                </div>

                <div class="form-group flex-1">
                    <label for="FILTER_RELEASE_YEAR" class="form-label">Earliest Release Year</label>
                    <input type="number" :value="config.FILTER_RELEASE_YEAR"
                        @focusout="validateReleaseYear($event.target.value)"
                        class="form-input"
                        id="FILTER_RELEASE_YEAR" placeholder="2000" min="1900">
                    <span v-if="errors.FILTER_RELEASE_YEAR" class="form-error">{{ errors.FILTER_RELEASE_YEAR }}</span>
                </div>
            </div>
            <p class="form-help">
                <i class="fas fa-info-circle"></i>
                Filter by original language and minimum release year
            </p>
        </div>

        <!-- Navigation Buttons -->
        <div class="flex justify-between mt-8 gap-4">
            <button @click="$emit('previous-step')"
                class="btn-secondary w-full flex items-center justify-center gap-2 py-4 px-8">
                <i class="fas fa-arrow-left"></i>
                Back
            </button>
            <button @click="submit" :disabled="hasErrors"
                class="btn-primary w-full flex items-center justify-center gap-2 py-4 px-8"
                :class="{ 'opacity-50 cursor-not-allowed': hasErrors }">
                Next Step
                <i class="fas fa-arrow-right"></i>
            </button>
        </div>
    </div>
</template>


<script>
import axios from 'axios';
import Multiselect from 'vue-multiselect';
import 'vue-multiselect/dist/vue-multiselect.min.css';
import '@/assets/styles/advancedFilterConfig.css';

export default {
    components: {
        'vue-multiselect': Multiselect
    },
    props: ['config'],
    data() {
        return {
            genres: [],
            selectedGenres: this.config.FILTER_GENRES_EXCLUDE || [],
            languages: [],
            selectedLanguages: this.config.FILTER_LANGUAGE || [],
            regions: [],
            selectedRegion: this.config.FILTER_REGION_PROVIDER || null,
            streamingServices: [],
            selectedStreamingServices: this.config.FILTER_STREAMING_SERVICES || [],
            errors: {
                FILTER_TMDB_THRESHOLD: '',
                FILTER_TMDB_MIN_VOTES: '',
                FILTER_RELEASE_YEAR: '',
                FILTER_NUM_SEASONS: ''
            }
        };
    },
    computed: {
            hasErrors() {
                return Object.values(this.errors).some(error => error !== '');
            }
    },
    methods: {
        handleUpdate(key, value) {
            this.$emit('update-config', key, value);
        },
        async fetchGenres() {
            try {
                const response = await axios.get(`https://api.themoviedb.org/3/genre/movie/list?api_key=${this.config.TMDB_API_KEY}`);
                this.genres = response.data.genres;
            } catch (error) {
                console.error("Error fetching genres:", error);
            }
        },
        async fetchLanguages() {
            try {
                const response = await axios.get(`https://api.themoviedb.org/3/configuration/languages?api_key=${this.config.TMDB_API_KEY}`);
                this.languages = response.data;
            } catch (error) {
                console.error("Error fetching languages:", error);
            }
        },
        async fetchRegions() {
            try {
                const response = await axios.get(`https://api.themoviedb.org/3/watch/providers/regions?api_key=${this.config.TMDB_API_KEY}`);
                this.regions = response.data.results;
            } catch (error) {
                console.error("Error fetching regions:", error);
            }
        },
        async fetchStreamingServices() {
            if (!this.selectedRegion) return;

            const region_code = this.selectedRegion?.iso_3166_1;

            try {
                const response = await axios.get(`https://api.themoviedb.org/3/watch/providers/movie?api_key=${this.config.TMDB_API_KEY}&watch_region=${region_code}`);
                this.streamingServices = response.data.results;
            } catch (error) {
                console.error("Error fetching streaming services:", error);
            }
        },
        updateLanguages(selected) {
            this.handleUpdate(
                'FILTER_LANGUAGE',
                selected
                    .filter(lang => lang.iso_639_1 && lang.english_name)
                    .map(lang => ({ id: lang.iso_639_1, english_name: lang.english_name }))
            );
        },
        updateGenres(selected) {
            this.handleUpdate('FILTER_GENRES_EXCLUDE', selected.map(genre => ({ id: genre.id, name: genre.name })));
        },
        updateRegion(selected) {
            this.handleUpdate('FILTER_REGION_PROVIDER', selected ? selected.iso_3166_1 : null);
        },
        updateStreamingServices(selected) {
            this.handleUpdate('FILTER_STREAMING_SERVICES', selected.map(service => ({ provider_id: service.provider_id, provider_name: service.provider_name })));
        },
        validateThreshold(value) {
            if (value < 0 || value > 100) {
                this.errors.FILTER_TMDB_THRESHOLD = "Rating must be between 0 and 100.";
            } else {
                this.errors.FILTER_TMDB_THRESHOLD = "";
                this.handleUpdate('FILTER_TMDB_THRESHOLD', value);
            }
        },
        validateMinVotes(value) {
            if (value < 0) {
                this.errors.FILTER_TMDB_MIN_VOTES = "Minimum votes cannot be negative.";
            } else {
                this.errors.FILTER_TMDB_MIN_VOTES = "";
                this.handleUpdate('FILTER_TMDB_MIN_VOTES', value);
            }
        },
        validateReleaseYear(value) {
            const year = parseInt(value, 10);
            const currentYear = new Date().getFullYear();
            if (isNaN(year) || year < 1900 || year > currentYear) {
                this.errors.FILTER_RELEASE_YEAR = `Year must be between 1900 and ${currentYear}.`;
            } else {
                this.errors.FILTER_RELEASE_YEAR = "";
                this.handleUpdate('FILTER_RELEASE_YEAR', value);
            }
        },
        validateNumSeasons(value) {
            if (value < 0) {
                this.errors.FILTER_NUM_SEASONS = "Seasons count must be at least 0 to select all seasons.";
            } else {
                this.errors.FILTER_NUM_SEASONS = "";
                this.handleUpdate('FILTER_NUM_SEASONS', value);
            }
        },
        submit() {
            if (!this.hasErrors) {
                this.$emit('next-step');
            }
        }
    },
    watch: {
        regions(newRegions) {
            const matchedRegion = newRegions.find(region => region.iso_3166_1 === this.config.FILTER_REGION_PROVIDER);
            if (matchedRegion) {
                this.selectedRegion = matchedRegion;
            } else {
                this.selectedRegion = null;
            }
        },
        selectedRegion() {
            this.fetchStreamingServices();
        }
    },
    mounted() {
        this.fetchGenres();
        this.fetchLanguages();
        this.fetchRegions();
    }
};
</script>

<style scoped>
/* Config Section */
.config-section {
  display: flex;
  flex-direction: column;
}

.section-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 0.5rem;
}

.section-description {
  color: var(--color-text-muted);
  font-size: 0.9rem;
  line-height: 1.5;
  margin-bottom: 1.5rem;
}

/* Form Row */
.form-row {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.form-row .form-group {
  margin-bottom: 0;
}

.form-row + .form-help {
  margin-top: 0.5rem;
}

.flex-1 {
  flex: 1;
}

/* Form Error */
.form-error {
  display: block;
  color: var(--color-error);
  font-size: 0.8125rem;
  margin-top: 0.25rem;
  font-weight: 500;
}

/* Toggle Items */
.space-y-3 > * + * {
  margin-top: 0.75rem;
}

.toggle-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--color-border-light);
  padding: 1rem;
  border-radius: var(--border-radius-sm);
  transition: var(--transition-base);
}

.toggle-item:hover {
  border-color: var(--color-primary);
  background: rgba(255, 255, 255, 0.04);
}

.toggle-info {
  flex-grow: 1;
  padding-right: 1rem;
}

.toggle-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 0.25rem 0;
}

.toggle-description {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
  margin: 0;
}

/* Responsive */
@media (max-width: 768px) {
  .form-row {
    flex-direction: column;
    gap: 0;
  }

  .form-row .form-group {
    margin-bottom: 1rem;
  }

}
</style>
