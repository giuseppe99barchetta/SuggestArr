<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">Final Step: Save Configuration</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">Please review your configuration settings before saving.</p>

        <div class="flex justify-between mt-8 space-x-4">
            <button @click="$emit('previous-step')" class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">Back</button>
            <button @click="saveConfig" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full">Save</button>
        </div>
    </div>
</template>

<script>
export default {
    props: ['config'],
    methods: {
        saveConfig() {
            // Esegui la chiamata API per salvare la configurazione
            this.$emit('next-step');
        }
    }
};
</script>
