<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">Additional Configuration</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">Suggestarr scans your recent viewing history and finds similar content based on the settings below. Adjust these options to control the number and type of suggestions generated.</p>

        <div class="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4 mt-4">
            <!-- Max Similar Movies -->
            <div class="w-full sm:w-1/2">
                <label for="MAX_SIMILAR_MOVIE" class="block text-xs sm:text-sm font-semibold text-gray-300">Max Similar Movies:</label>
                <p class="text-xs sm:text-sm text-gray-400 mb-2">Define how many similar movies Suggestarr should find for each movie viewed. For example, if set to 1, Suggestarr will suggest one similar movie for every movie in the recent viewing history.</p>
                <input type="number" :value="config.MAX_SIMILAR_MOVIE" 
                       @input="handleUpdate('MAX_SIMILAR_MOVIE', $event.target.value)"
                       class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                       id="MAX_SIMILAR_MOVIE" placeholder="5">
            </div>

            <!-- Max Similar TV Shows -->
            <div class="w-full sm:w-1/2">
                <label for="MAX_SIMILAR_TV" class="block text-xs sm:text-sm font-semibold text-gray-300">Max Similar TV Shows:</label>
                <p class="text-xs sm:text-sm text-gray-400 mb-2">Define how many similar TV shows Suggestarr should find for each show in the viewing history. For example, if set to 2, it will suggest up to two similar shows for every recently viewed show.</p>
                <input type="number" :value="config.MAX_SIMILAR_TV" 
                       @input="handleUpdate('MAX_SIMILAR_TV', $event.target.value)"
                       class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                       id="MAX_SIMILAR_TV" placeholder="2">
            </div>
        </div>

        <!-- Max Content Checks -->
        <label for="MAX_CONTENT_CHECKS" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Max Content Checks:</label>
        <p class="text-xs sm:text-sm text-gray-400 mb-2">Set the maximum number of items from your recent viewing history Suggestarr should analyze. For instance, if set to 3, it will look for similar items based on the last three movies or shows viewed.</p>
        <input type="number" :value="config.MAX_CONTENT_CHECKS" 
               @input="handleUpdate('MAX_CONTENT_CHECKS', $event.target.value)"
               class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
               id="MAX_CONTENT_CHECKS" placeholder="10">

        <!-- Search Size -->
        <label for="SEARCH_SIZE" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Search Size:</label>
        <p class="text-xs sm:text-sm text-gray-400 mb-2">Specify how many suggestions Suggestarr should generate for each item it analyzes. For example, if set to 5, Suggestarr will find up to 5 possible suggestions for each movie or show it checks.</p>
        <input type="number" :value="config.SEARCH_SIZE" 
               @input="handleUpdate('SEARCH_SIZE', $event.target.value)"
               class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
               id="SEARCH_SIZE" placeholder="20">

        <!-- Cron Times -->
        <label for="CRON_TIMES" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Cron Times:</label>
        <p class="text-xs sm:text-sm text-gray-400 mb-2">Define when Suggestarr should run searches using a cron schedule. For example, "0 0 * * *" means checks will occur every day at midnight. Incorrect cron formats will show an error.</p>
        <input type="text" :value="config.CRON_TIMES" 
               @input="handleCronInput($event.target.value)"
               class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
               id="CRON_TIMES" placeholder="0 0 * * *">

        <p class="text-xs sm:text-sm text-green-400 mt-2" v-if="cronDescription">{{ cronDescription }}</p>
        <p class="text-xs sm:text-sm text-red-500 mt-2" v-if="cronError">{{ cronError }}</p>

        <!-- SUBPATH -->
        <label for="SUBPATH" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Base URL Subpath:</label>
        <p class="text-xs sm:text-sm text-gray-400 mb-2">Specify the subpath where Suggestarr will be accessed. For example, "/suggestarr" would make Suggestarr accessible at "yourdomain.com/suggestarr". If left empty, it defaults to the root path.</p>
        <input type="text" :value="config.SUBPATH" 
               @input="handleUpdate('SUBPATH', $event.target.value)"
               class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
               id="SUBPATH" placeholder="/suggestarr">

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
        handleUpdate(key, value) {
            this.$emit('update-config', key, value); 
        },
        handleCronInput(value) {
            this.handleUpdate('CRON_TIMES', value);

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
