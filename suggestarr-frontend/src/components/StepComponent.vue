<template>
    <div>
        <h3 class="text-lg font-semibold text-gray-300">{{ title }}</h3>
        <p class="text-gray-400 mb-4">{{ description }}</p>
        <label :for="inputId" class="block text-sm font-semibold text-gray-300">{{ label }}</label>
        <div class="flex items-center">
            <!-- Usare una variabile locale per evitare di mutare direttamente la prop -->
            <input type="text" v-model="localApiKey" :id="inputId" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" :placeholder="placeholder" @input="updateApiKey">
            <button
                type="button"
                @click="testFunction"
                :disabled="isTesting"
                :class="{
                    'bg-green-500 hover:bg-green-600': testStatus === 'success',
                    'bg-red-500 hover:bg-red-600': testStatus === 'fail',
                    'bg-blue-500 hover:bg-blue-600': !testStatus
                }"
                class="text-white px-4 py-2 rounded-lg shadow-md ml-2"
            >
                <i v-if="isTesting" class="fas fa-spinner fa-spin"></i>
                <i v-else-if="testStatus === 'success'" class="fas fa-check"></i>
                <i v-else-if="testStatus === 'fail'" class="fas fa-times"></i>
                <i v-else class="fas fa-play"></i>
            </button>
        </div>
        <!-- Box di errore -->
        <div v-if="testFailed" class="bg-gray-800 border border-red-500 text-red-500 px-4 py-3 rounded-lg mt-4" role="alert">
            <span class="block sm:inline">{{ errorMessage }}</span>
        </div>
        <div class="flex justify-between mt-8 space-x-4">
            <button v-if="hasBack" @click="previousStep" class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">
                Back
            </button>
            <button @click="nextStep" :disabled="!testResult" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full" :class="{ 'opacity-50 cursor-not-allowed': !testResult }">
                Next Step
            </button>
        </div>
    </div>
</template>

<script>
export default {
    props: {
        title: String,
        description: String,
        label: String,
        placeholder: String,
        inputId: String,
        apiKey: String,
        testFunction: Function,
        testResult: Boolean,
        testFailed: Boolean,
        testStatus: String,
        isTesting: Boolean,
        errorMessage: String,
        hasBack: Boolean,
        previousStep: Function,
        nextStep: Function
    },
    data() {
        return {
            localApiKey: this.apiKey // Variabile locale per il v-model
        };
    },
    watch: {
        apiKey(newVal) {
            this.localApiKey = newVal; // Mantieni la sincronizzazione con il genitore
        }
    },
    methods: {
        updateApiKey() {
            this.$emit('update-api-key', this.localApiKey); // Emetti l'evento verso il genitore
        }
    }
};
</script>
