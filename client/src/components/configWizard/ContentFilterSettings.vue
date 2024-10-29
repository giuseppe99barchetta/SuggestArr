<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">Advanced Filter Configuration</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">
            Set up advanced filters based on ratings and other criteria. None of the fields below are mandatory, so you can use only the filters you need.
        </p>

        <!-- TMDB Rating and Votes Filters -->
        <div class="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4">
            <div class="w-full sm:w-1/2">
                <label for="FILTER_TMDB_THRESHOLD" class="block text-xs sm:text-sm font-semibold text-gray-300">
                    TMDB Rating Threshold:
                </label>
                <p class="text-xs text-gray-400 mb-2">Minimum rating (out of 100) on TMDB for content to be included.</p>
                <input type="number" :value="config.FILTER_TMDB_THRESHOLD" 
                       @input="handleUpdate('FILTER_TMDB_THRESHOLD', $event.target.value)"
                       class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                       id="FILTER_TMDB_THRESHOLD" placeholder="75">
            </div>
            <div class="w-full sm:w-1/2">
                <label for="FILTER_TMDB_MIN_VOTES" class="block text-xs sm:text-sm font-semibold text-gray-300">
                    TMDB Minimum Votes:
                </label>
                <p class="text-xs text-gray-400 mb-2">Minimum number of votes on TMDB for content to qualify.</p>
                <input type="number" :value="config.FILTER_TMDB_MIN_VOTES" 
                       @input="handleUpdate('FILTER_TMDB_MIN_VOTES', $event.target.value)"
                       class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                       id="FILTER_TMDB_MIN_VOTES" placeholder="50">
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
                           id="FILTER_INCLUDE_NO_RATING"
                           class="sr-only">
                    <div class="w-10 h-5 bg-gray-600 rounded-full shadow-inner"></div>
                    <div class="dot absolute left-0 top-0 w-5 h-5 bg-red-600 rounded-full transition-transform transform translate-x-0"></div>
                </div>
            </label>
        </div>

        <!-- Genre Exclusion Filter with Vue Multiselect -->
        <label for="FILTER_GENRES_EXCLUDE" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">
            Exclude Genres:
        </label>
        <p class="text-xs text-gray-400 mb-2">Select genres to exclude from recommendations.</p>
        <vue-multiselect
            v-model="selectedGenres"
            :options="genres"
            track-by="id"
            label="name"
            multiple
            placeholder="Select genres to exclude"
            @update:modelValue="updateGenres"
        >
        </vue-multiselect>

        <!-- Country and Release Year Filters -->
        <div class="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4 mt-4">
            <div class="w-full sm:w-1/2">
                <label for="FILTER_COUNTRY" class="block text-xs sm:text-sm font-semibold text-gray-300">
                    Original language of content:
                </label>
                <p class="text-xs text-gray-400 mb-2">Specify the language code (e.g., "US" for United States, "IT" for Italy).</p>
                <input type="text" :value="config.FILTER_COUNTRY" 
                       @input="handleUpdate('FILTER_COUNTRY', $event.target.value)"
                       class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                       id="FILTER_COUNTRY" placeholder="US">
            </div>
            <div class="w-full sm:w-1/2">
                <label for="FILTER_RELEASE_YEAR" class="block text-xs sm:text-sm font-semibold text-gray-300">
                    Release Year:
                </label>
                <p class="text-xs text-gray-400 mb-2">Specify a starting year for search (e.g., "2020" includes 2020 and later).</p>
                <input type="text" :value="config.FILTER_RELEASE_YEAR" 
                       @input="handleUpdate('FILTER_RELEASE_YEAR', $event.target.value)"
                       class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                       id="FILTER_RELEASE_YEAR" placeholder="2000">
            </div>
        </div>

        <div class="flex flex-col sm:flex-row justify-between mt-8 space-y-4 sm:space-y-0 sm:space-x-4">
            <button @click="$emit('previous-step')" class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">Back</button>
            <button @click="$emit('next-step')" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full">Next</button>
        </div>
    </div>
</template>


<script>
import axios from 'axios';
import Multiselect from 'vue-multiselect';
import 'vue-multiselect/dist/vue-multiselect.min.css';

export default {
    components: {
    'vue-multiselect': Multiselect
    },
    props: ['config'],
    data() {
        return {
            genres: [],
            selectedGenres: this.config.FILTER_GENRES_EXCLUDE || []
        };
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
        updateGenres(selected) {
            // Instead of only sending the IDs, send the full list of selected genres with id and name
            this.handleUpdate('FILTER_GENRES_EXCLUDE', selected.map(genre => ({ id: genre.id, name: genre.name })));
        }
    },
    mounted() {
        this.fetchGenres();
    }
};
</script>

<style>

.relative input:checked ~ .dot {
    transform: translateX(100%);
    background-color: #34d399; /* Green color when checked */
}


/* Styling for vue-multiselect */
.multiselect {
    border: 1px solid #4a5568; /* Match border-gray-600 */
    border-radius: 0.5rem; /* Match rounded-lg */
    padding: 0.0rem;
    color: #e5e7eb;
    width: 100%;
}

.multiselect__tag {
    background-color: #b84141; /* Red for excluded tags */
    color: #caced8 !important;
    margin: 2px;
    font-size: 0.875rem;
    border-radius: 0.5rem;
}

.multiselect__input {
    background-color: transparent !important;
    color: #ffffff !important; /* Force light text color */
}

/* Target selected single items */
.multiselect__single {
    color: #e5e7eb !important;
    background-color: transparent !important;
}

.multiselect__placeholder {
    color: #9ca3af;
}

.multiselect__content-wrapper {
    background-color: #1f2937;
    border: 0px solid #4b5563;
    border-radius: 0.5rem;
}

.multiselect__option--highlight {
    color: #e5e7eb;
}

.multiselect__option--selected {
    background-color: #b84141;
    color: #ffffff;
}

.multiselect__select, .multiselect__clear {
    color: #9ca3af;
}

.multiselect__tags {
    min-height: 40px;
    display: block;
    padding: 8px 40px 0 8px;
    border-radius: 5px;
    --tw-bg-opacity: 1;
    background-color: rgba(55, 65, 81, var(--tw-bg-opacity));
    font-size: 14px;
    border:0;
}

.multiselect__content-wrapper::-webkit-scrollbar {
    width: 8px; /* Width of the scrollbar */
}

.multiselect__content-wrapper::-webkit-scrollbar-track {
    background: #1f2937; /* Background of the scrollbar track */
    border-radius: 8px;
}

.multiselect__content-wrapper::-webkit-scrollbar-thumb {
    background-color: #4b5563; /* Color of the scrollbar thumb */
    border-radius: 8px;
    border: 2px solid #1f2937; /* Adds padding around the thumb */
}

.multiselect__content-wrapper::-webkit-scrollbar-thumb:hover {
    background-color: #6b7280; /* Color on hover */
}

/* Firefox scrollbar styling */
.multiselect__content-wrapper {
    scrollbar-width: thin;
    scrollbar-color: #4b5563 #1f2937; /* Thumb color and track color */
}
</style>