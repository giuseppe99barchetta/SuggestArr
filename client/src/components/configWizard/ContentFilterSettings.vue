<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">Advanced Filter Configuration</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">
            Set up advanced filters based on ratings and other criteria. None of the fields below are mandatory, so you
            can use only the filters you need.
        </p>

        <!-- TMDB Rating and Votes Filters -->
        <div class="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4">
            <div class="w-full sm:w-1/2">
                <label for="FILTER_TMDB_THRESHOLD" class="block text-xs sm:text-sm font-semibold text-gray-300">
                    TMDB Rating Threshold:
                </label>
                <p class="text-xs text-gray-400 mb-2">Minimum rating (out of 100) on TMDB for content to be included.
                </p>
                <input type="number" :value="config.FILTER_TMDB_THRESHOLD"
                    @input="validateThreshold($event.target.value)"
                    class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                    id="FILTER_TMDB_THRESHOLD" placeholder="60">
                <span v-if="errors.FILTER_TMDB_THRESHOLD" class="text-red-500 text-xs">{{ errors.FILTER_TMDB_THRESHOLD
                    }}</span>
            </div>
            <div class="w-full sm:w-1/2">
                <label for="FILTER_TMDB_MIN_VOTES" class="block text-xs sm:text-sm font-semibold text-gray-300">
                    TMDB Minimum Votes:
                </label>
                <p class="text-xs text-gray-400 mb-2">Minimum number of votes on TMDB for content to qualify.</p>
                <input type="number" :value="config.FILTER_TMDB_MIN_VOTES"
                    @input="validateMinVotes($event.target.value)"
                    class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                    id="FILTER_TMDB_MIN_VOTES" placeholder="20">
                <span v-if="errors.FILTER_TMDB_MIN_VOTES" class="text-red-500 text-xs">{{ errors.FILTER_TMDB_MIN_VOTES
                    }}</span>
            </div>
        </div>

        <!-- Checkbox for Missing Ratings -->
        <div class="flex items-center mt-4">
            <label for="FILTER_INCLUDE_NO_RATING" class="flex items-center cursor-pointer">
                <span class="text-xs sm:text-sm font-semibold text-gray-300 mr-3">
                    Include content with missing rating or votes:
                </span>
                <div class="relative inline-flex items-center">
                    <input type="checkbox" :checked="config.FILTER_INCLUDE_NO_RATING"
                        @change="handleUpdate('FILTER_INCLUDE_NO_RATING', $event.target.checked)"
                        id="FILTER_INCLUDE_NO_RATING" class="sr-only">
                    <div class="w-10 h-5 bg-gray-600 rounded-full shadow-inner"></div>
                    <div
                        class="dot absolute left-0 top-0 w-5 h-5 bg-red-600 rounded-full transition-transform transform translate-x-0">
                    </div>
                </div>
            </label>
        </div>

        <!-- Genre Exclusion Filter with Vue Multiselect -->
        <label for="FILTER_GENRES_EXCLUDE" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">
            Exclude Genres:
        </label>
        <p class="text-xs text-gray-400 mb-2">Select genres to exclude from recommendations.</p>
        <vue-multiselect v-model="selectedGenres" :options="genres" track-by="id" label="name" multiple
            placeholder="No excluded genre" @update:modelValue="updateGenres"
            class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md multiselect-genres"
            id="FILTER_GENRES_EXCLUDE">
        </vue-multiselect>

        <!-- Country and Release Year Filters -->
        <div class="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4 mt-4">
            <div class="w-full sm:w-1/2">
                <label for="FILTER_LANGUAGE" class="block text-xs sm:text-sm font-semibold text-gray-300">
                    Original language of content:
                </label>
                <p class="text-xs text-gray-400 mb-2">Select the preferred original language(s) of the content</p>
                <vue-multiselect v-model="selectedLanguages" :options="languages" track-by="iso_639_1"
                    label="english_name" multiple placeholder="No preferred language"
                    @update:modelValue="updateLanguages"
                    class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md multiselect-languages"
                    id="FILTER_LANGUAGE">
                </vue-multiselect>
            </div>
            <div class="w-full sm:w-1/2">
                <label for="FILTER_RELEASE_YEAR" class="block text-xs sm:text-sm font-semibold text-gray-300">
                    Release Year:
                </label>
                <p class="text-xs text-gray-400 mb-2">Specify a starting year for search (e.g., "2020" includes 2020 and
                    later).</p>
                <input type="number" :value="config.FILTER_RELEASE_YEAR"
                    @focusout="validateReleaseYear($event.target.value)"
                    class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                    id="FILTER_RELEASE_YEAR" placeholder="2000">
                <span v-if="errors.FILTER_RELEASE_YEAR" class="text-red-500 text-xs">{{ errors.FILTER_RELEASE_YEAR
                    }}</span>
            </div>
        </div>

        <div class="flex flex-col sm:flex-row justify-between mt-8 space-y-4 sm:space-y-0 sm:space-x-4">
            <button @click="$emit('previous-step')"
                class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">Back</button>
            <button @click="submit" :disabled="hasErrors"
                class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full">Next</button>
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
            errors: {
                FILTER_TMDB_THRESHOLD: '',
                FILTER_TMDB_MIN_VOTES: '',
                FILTER_RELEASE_YEAR: ''
            }
        };
    },
    computed: {
            hasErrors() {
                // Checks if there are any error messages in the errors object
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
        submit() {
            // Check if there are no validation errors before proceeding
            if (!this.hasErrors) {
                this.$emit('next-step');
            }
        }
    },
    mounted() {
        this.fetchGenres();
        this.fetchLanguages();
    }
};
</script>
