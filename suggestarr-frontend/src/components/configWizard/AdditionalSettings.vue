<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">Step 4: Additional Settings</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">Configure additional settings for similar media, content checks, and schedule times.</p>

        <!-- Max Similar Movies -->
        <label for="MAX_SIMILAR_MOVIE" class="block text-xs sm:text-sm font-semibold text-gray-300">Max Similar Movies:</label>
        <p class="text-xs sm:text-sm text-gray-400 mb-2">Specify the maximum number of similar movies to fetch for each movie seen.</p>
        <input type="number" :value="config.MAX_SIMILAR_MOVIE" @input="$emit('update-max-similar-movies', $event.target.value)"
               class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
               id="MAX_SIMILAR_MOVIE" placeholder="5">

        <!-- Max Similar TV Shows -->
        <label for="MAX_SIMILAR_TV" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Max Similar TV Shows:</label>
        <p class="text-xs sm:text-sm text-gray-400 mb-2">Specify the maximum number of similar TV shows to fetch for each TV show seen.</p>
        <input type="number" :value="config.MAX_SIMILAR_TV" @input="$emit('update-max-similar-tv', $event.target.value)"
               class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
               id="MAX_SIMILAR_TV" placeholder="2">

        <!-- Max Content Checks -->
        <label for="MAX_CONTENT_CHECKS" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Max Content Checks:</label>
        <p class="text-xs sm:text-sm text-gray-400 mb-2">Set the maximum number of recently viewed content items to search for similar content.</p>
        <input type="number" :value="config.MAX_CONTENT_CHECKS" @input="$emit('update-max-content-checks', $event.target.value)"
               class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
               id="MAX_CONTENT_CHECKS" placeholder="10">

        <!-- Cron Times -->
        <label for="CRON_TIMES" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Cron Times:</label>
        <p class="text-xs sm:text-sm text-gray-400 mb-2">Set the schedule in cron format for content checks. (e.g., "0 0 * * *" for daily checks at midnight)</p>
        <input type="text" :value="config.CRON_TIMES" @input="handleCronInput($event.target.value)"
               class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
               id="CRON_TIMES" placeholder="0 0 * * *">

        <p class="text-xs sm:text-sm text-green-400 mt-2" v-if="cronDescription">{{ cronDescription }}</p>
        <p class="text-xs sm:text-sm text-red-500 mt-2" v-if="cronError">{{ cronError }}</p>

        <div class="flex justify-between mt-8 space-x-4">
            <button @click="$emit('previous-step')" class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">Back</button>
            <button @click="$emit('next-step')" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full">Save</button>
        </div>
    </div>
</template>

<script>
import cronParser from 'cron-parser';

export default {
    props: ['config'],
    data() {
        return {
            cronDescription: '',
            cronError: ''
        };
    },
    methods: {
        handleCronInput(value) {
            this.$emit('update-cron-times', value);

            try {
                const interval = cronParser.parseExpression(value);
                const nextRun = interval.next().toString();
                this.cronDescription = `Next run: ${nextRun}`;
                this.cronError = '';
            } catch (err) {
                this.cronDescription = '';
                this.cronError = 'Invalid cron expression';
            }
        }
    }
};
</script>
