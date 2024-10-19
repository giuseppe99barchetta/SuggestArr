<template>
    <div>
        <div v-if="currentStep <= 5" class="flex items-center justify-center min-h-screen bg-gradient-to-br from-gray-900 to-gray-800">
            <div class="p-10 space-y-8 max-w-4xl mx-auto bg-gray-800 rounded-lg shadow-lg">
                <h2 class="text-2xl font-bold text-gray-200 mb-4 text-center">Configuration Wizard</h2>

                <div class="relative">
                    <div class="w-full bg-gray-700 rounded-full h-2 mb-4">
                        <div class="bg-indigo-600 h-full rounded-full transition-all duration-500 ease-in-out" :style="{ width: progressBarWidth }"></div>
                    </div>
                    <p class="text-sm text-gray-400 text-center">{{ currentStep }} / 5 Steps Complete</p>
                </div>

                <transition name="fade" @after-leave="showNewStep">
                    <div v-if="showStep" class="step">
                        <!-- Step 1 -->
                        <template v-if="currentStep === 1">
                            <h3 class="text-lg font-semibold text-gray-300">Step 1: TMDB API Key</h3>
                            <p class="text-gray-400 mb-4">You can get your TMDB API Key by signing up at <a href="https://www.themoviedb.org/" class="text-indigo-400">The Movie Database</a>.</p>
                            <label for="TMDB_API_KEY" class="block text-sm font-semibold text-gray-300">TMDB API Key:</label>
                            <div class="flex items-center">
                                <input type="text" v-model="config.TMDB_API_KEY" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" 
                                       id="TMDB_API_KEY" 
                                       placeholder="Enter your TMDB API Key">
                                <button
                                    type="button"
                                    @click="testTmdbApi"
                                    :disabled="isTesting"
                                    :class="{
                                        'bg-green-500 hover:bg-green-600': tmdbTestStatus === 'success',
                                        'bg-red-500 hover:bg-red-600': tmdbTestStatus === 'fail',
                                        'bg-blue-500 hover:bg-blue-600': !tmdbTestStatus
                                    }"
                                    class="text-white px-4 py-2 rounded-lg shadow-md ml-2"
                                >
                                    <i v-if="isTesting" class="fas fa-spinner fa-spin"></i>
                                    <i v-else-if="tmdbTestStatus === 'success'" class="fas fa-check"></i>
                                    <i v-else-if="tmdbTestStatus === 'fail'" class="fas fa-times"></i>
                                    <i v-else class="fas fa-play"></i>
                                </button>
                            </div>
                            <div v-if="tmdbTestFailed" class="bg-gray-800 border border-red-500 text-red-500 px-4 py-3 rounded-lg mt-4" role="alert">
                                <span class="block sm:inline">Failed to validate TMDB API Key.</span>
                            </div>
                            <div class="flex justify-between mt-8 space-x-4">
                                <button @click="nextStep" :disabled="!tmdbTestResult" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full" :class="{ 'opacity-50 cursor-not-allowed': !tmdbTestResult }">
                                    Next Step
                                </button>
                            </div>
                        </template>

                        <!-- Step 2 -->
                        <template v-else-if="currentStep === 2">
                            <h3 class="text-lg font-semibold text-gray-300">Step 2: Jellyfin API Details</h3>
                            <p class="text-gray-400 mb-4">To get your Jellyfin API URL and Key, refer to your Jellyfin server settings.</p>
                            <label for="JELLYFIN_API_URL" class="block text-sm font-semibold text-gray-300">Jellyfin URL:</label>
                            <input type="text" v-model="config.JELLYFIN_API_URL" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" 
                                   id="JELLYFIN_API_URL" 
                                   placeholder="http://your-jellyfin-url">
                            <label for="JELLYFIN_TOKEN" class="block text-sm font-semibold text-gray-300 mt-4">Jellyfin API Key:</label>
                            <div class="flex items-center">
                                <input type="text" v-model="config.JELLYFIN_TOKEN" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" 
                                       id="JELLYFIN_TOKEN" 
                                       placeholder="Your Jellyfin API Key">
                                <button
                                    type="button"
                                    @click="testJellyfinApi"
                                    :disabled="isTesting"
                                    :class="{
                                        'bg-green-500 hover:bg-green-600': jellyfinTestStatus === 'success',
                                        'bg-red-500 hover:bg-red-600': jellyfinTestStatus === 'fail',
                                        'bg-blue-500 hover:bg-blue-600': !jellyfinTestStatus
                                    }"
                                    class="text-white px-4 py-2 rounded-lg shadow-md ml-2"
                                >
                                    <i v-if="isTesting" class="fas fa-spinner fa-spin"></i>
                                    <i v-else-if="jellyfinTestStatus === 'success'" class="fas fa-check"></i>
                                    <i v-else-if="jellyfinTestStatus === 'fail'" class="fas fa-times"></i>
                                    <i v-else class="fas fa-play"></i>
                                </button>
                            </div>
                            <div v-if="jellyfinTestFailed" class="bg-gray-800 border border-red-500 text-red-500 px-4 py-3 rounded-lg mt-4" role="alert">
                                <span class="block sm:inline">Failed to validate Jellyfin Key.</span>
                            </div>
                            <div class="flex justify-between mt-8 space-x-4">
                                <button @click="previousStep" class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">
                                    Back
                                </button>
                                <button @click="nextStep" :disabled="!jellyfinTestResult" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full" :class="{ 'opacity-50 cursor-not-allowed': !jellyfinTestResult }">
                                    Next Step
                                </button>
                            </div>
                        </template>

                        <!-- Step 3 -->
                        <template v-if="currentStep === 3">
                            <div>
                                <h3 class="text-lg font-semibold text-gray-300">Step 3: Jellyseer API Details</h3>
                                <p class="text-gray-400 mb-4">To get your Jellyseer API URL and Key, refer to your Jellyseer settings.</p>

                                <label for="JELLYSEER_API_URL" class="block text-sm font-semibold text-gray-300">Jellyseer URL:</label>
                                <input type="text" v-model="config.JELLYSEER_API_URL" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" 
                                       id="JELLYSEER_API_URL" placeholder="http://your-jellyseer-url">

                                <label for="JELLYSEER_TOKEN" class="block text-sm font-semibold text-gray-300 mt-4">Jellyseer API Key:</label>
                                <div class="flex items-center">
                                    <input type="text" v-model="config.JELLYSEER_TOKEN" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" 
                                           id="JELLYSEER_TOKEN" placeholder="Enter your Jellyseer API Key">
                                    <button
                                        type="button"
                                        @click="testJellyseerApi"
                                        :class="{
                                            'bg-green-500 hover:bg-green-600': jellyseerTestStatus === 'success',
                                            'bg-red-500 hover:bg-red-600': jellyseerTestStatus === 'fail',
                                            'bg-blue-500 hover:bg-blue-600': !jellyseerTestStatus
                                        }"
                                        class="text-white px-4 py-2 rounded-lg shadow-md ml-2"
                                    >
                                        <i v-if="isTesting" class="fas fa-spinner fa-spin"></i>
                                        <i v-else-if="jellyseerTestStatus === 'success'" class="fas fa-check"></i>
                                        <i v-else-if="jellyseerTestStatus === 'fail'" class="fas fa-times"></i>
                                        <i v-else class="fas fa-play"></i>
                                    </button>
                                </div>
                            
                                <!-- Box di errore -->
                                <div v-if="jellyseerTestFailed" class="bg-gray-800 border border-red-500 text-red-500 px-4 py-3 rounded-lg mt-4" role="alert">
                                    <span class="block sm:inline">Failed to validate Jellyseer Key.</span>
                                </div>
                            
                                <!-- Dropdown con utenti e campo password -->
                                <div v-if="jellyseerTestStatus === 'success'" class="mt-4">
                                    <label for="JELLYSEER_USER" class="block text-sm font-semibold text-gray-300">Select User:</label>
                                    <select v-model="selectedUser" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2">
                                        <option v-for="user in jellyseerUsers" :key="user.id" :value="user">{{ user.name }}</option>
                                    </select>
                                
                                    <label for="JELLYSEER_PASSWORD" class="block text-sm font-semibold text-gray-300 mt-4">Password:</label>
                                    <input type="password" v-model="userPassword" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" id="JELLYSEER_PASSWORD" placeholder="Enter your password">
                                
                                    <button
                                        @click="authenticateUser"
                                        :disabled="isAuthenticating || authenticated"
                                        :class="{
                                            'bg-green-500 hover:bg-green-600': authenticated,
                                            'bg-indigo-600 hover:bg-indigo-500': !authenticated,
                                            'opacity-50 cursor-not-allowed': isAuthenticating
                                        }"
                                        class="text-white font-bold py-4 px-8 rounded-lg w-full mt-4"
                                    >
                                        <i v-if="isAuthenticating" class="fas fa-spinner fa-spin"></i>
                                        <span v-else-if="authenticated">Logged In</span>
                                        <span v-else>Authenticate</span>
                                    </button>
                                </div>
                                
                                <!-- Messaggio aggiuntivo per account manuale -->
                                <div class="mt-4 text-gray-400">
                                    <p>If you don't have an account, you can create one in Jellyseer without auto-approval permissions. This will allow SuggestArr to request approval for actions that require your authorization.</p>
                                </div>
                            
                                <div class="flex justify-between mt-8 space-x-4">
                                    <button @click="previousStep" class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">
                                        Back
                                    </button>
                                    <!-- Next Step button is always enabled -->
                                    <button @click="nextStep" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full">
                                        Next Step
                                    </button>
                                </div>
                            </div>
                        </template>

                        <template v-if="currentStep === 4">
                            <h3 class="text-lg font-semibold text-gray-300">Step 5: Additional Settings</h3>
                            <p class="text-gray-400 mb-4">Configure additional settings for similar media and schedule times.</p>

                            <label for="MAX_SIMILAR_MOVIE" class="block text-sm font-semibold text-gray-300">Max Similar Movies:</label>
                            <input type="number" v-model="config.MAX_SIMILAR_MOVIE" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" 
                                   id="MAX_SIMILAR_MOVIE" placeholder="5">

                            <label for="MAX_SIMILAR_TV" class="block text-sm font-semibold text-gray-300 mt-4">Max Similar TV Shows:</label>
                            <input type="number" v-model="config.MAX_SIMILAR_TV" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" 
                                   id="MAX_SIMILAR_TV" placeholder="2">

                            <label for="CRON_TIMES" class="block text-sm font-semibold text-gray-300 mt-4">Cron Times:</label>
                            <input type="text" v-model="config.CRON_TIMES" class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2" 
                                   id="CRON_TIMES" placeholder="0 0 * * *">

                            <div class="flex justify-between mt-8 space-x-4">
                                <button @click="previousStep" class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">
                                    Back
                                </button>
                                <button @click="saveConfig" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full">
                                    Save and Finish
                                </button>
                            </div>
                        </template>

                        
                        <!-- Step 4 -->
                        <template v-else-if="currentStep === 5">
                            <h3 class="text-lg font-semibold text-gray-300">Final Step: Save Configuration</h3>
                            <p class="text-gray-400 mb-4">Please review your configuration settings before saving.</p>
                            <div class="flex justify-between mt-8 space-x-4">
                                <button @click="previousStep" class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">
                                    Back
                                </button>
                                <button @click="saveConfig" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full">
                                    Save
                                </button>
                            </div>
                        </template>
                    </div>
                </transition>
            </div>
        </div>

        <div v-if="currentStep === 6">
            <ConfigSummary :config="config" @edit-config="editConfig" />
        </div>
    </div>
</template>


<script>
import ConfigSummary from './ConfigSummary.vue';
import axios from 'axios';

export default {
    components: {
        ConfigSummary
    },
    data() {
        return {
            currentStep: 1,
            config: {
                TMDB_API_KEY: '',
                JELLYFIN_API_URL: '',
                JELLYFIN_TOKEN: '',
                JELLYSEER_API_URL: '',
                JELLYSEER_TOKEN: '',
                MAX_SIMILAR_MOVIE: 5,  // Default value
                MAX_SIMILAR_TV: 2,      // Default value
                CRON_TIMES: '0 0 * * *' // Default value
            },
            jellyseerUsers: [],
            selectedUser: '',
            userPassword: '',
            tmdbTestResult: false,
            tmdbTestFailed: false,
            jellyfinTestResult: false,
            jellyfinTestFailed: false,
            jellyseerTestResult: false,
            jellyseerTestFailed: false,
            showStep: true,
            isTesting: false,
            isAuthenticating: false,
        };
    },
    computed: {
        progressBarWidth() {
            return `${(this.currentStep / 5) * 100}%`;
        }
    },
    mounted() {
    this.fetchConfig();  // Ottieni la configurazione quando il componente viene montato
    },
    methods: {
        fetchConfig() {
            axios.get('http://localhost:5000/api/config')
            .then(response => {
              this.config = response.data;  // Salva la configurazione nella variabile
            })
            .catch(error => {
                this.errorMessage = `Error: ${error.response.data.message}`;
            });
        },
        nextStep() {
            this.showStep = false; // Nascondi il passo corrente
            setTimeout(() => {
                if (this.currentStep < 6) {
                    this.currentStep++;
                } else if (this.currentStep === 6) {
                    this.saveConfig();
                }
                this.showStep = true; // Mostra il nuovo passo
            }, 300); // Aspetta il tempo dell'animazione
        },
        previousStep() {
        this.showStep = false;
        setTimeout(() => {
            if (this.currentStep > 1) {
                this.currentStep--;
            }
            this.showStep = true;
        }, 300);
        },
        editConfig() {
            this.currentStep = 1;
        },
        saveConfig() {
            axios.post('http://localhost:5000/api/save', this.config)
            .then(response => {
                console.log(response)
                this.currentStep = 6;
            })
            .catch(error => {
                this.errorMessage = `Error: ${error.response.data.message}`;
            });
        },
        testTmdbApi() {
            this.isTesting = true; // Inizia il caricamento
            setTimeout(() => { // Simula un test
                const isSuccess = Math.random() > 0.5;
                if (isSuccess) {
                    this.tmdbTestResult = true;
                    this.tmdbTestFailed = false;
                    this.tmdbTestStatus = 'success';
                } else {
                    this.tmdbTestResult = false;
                    this.tmdbTestFailed = true;
                    this.tmdbTestStatus = 'fail';
                }
                this.isTesting = false; // Fine del caricamento
            }, 500); // Simula un test che dura 2 secondi
        },
        testJellyfinApi() {
            const isSuccess = Math.random() > 0.5; // Simula un successo o fallimento casuale
            this.isTesting = true;
            if (isSuccess) {
                this.jellyfinTestResult = true;
                this.jellyfinTestFailed = false;
                this.jellyfinTestStatus = 'success'; // Imposta lo stato del test su successo
            } else {
                this.jellyfinTestResult = false;
                this.jellyfinTestFailed = true;
                this.jellyfinTestStatus = 'fail'; // Imposta lo stato del test su fallimento
            }
            this.isTesting = false; 
        },
        testJellyseerApi() {
            this.isTesting = true;
            const isSuccess = true; // Simula un successo o fallimento casuale
            if (isSuccess) {
                this.jellyseerTestResult = true;
                this.jellyseerTestFailed = false;
                this.jellyseerTestStatus = 'success'; // Imposta lo stato del test su successo
                this.fetchJellyseerUsers();
            } else {
                this.jellyseerTestResult = false;
                this.jellyseerTestFailed = true;
                this.jellyseerTestStatus = 'fail'; // Imposta lo stato del test su fallimento
            }
            this.isTesting = false;
        },
        fetchJellyseerUsers() {
            axios.post('http://localhost:5000/api/jellyseer/get_users', {
                JELLYSEER_API_URL: this.config.JELLYSEER_API_URL,
                JELLYSEER_TOKEN: this.config.JELLYSEER_TOKEN
            })
            .then(response => {
              if (response.data.type === 'success') {
                this.jellyseerUsers = response.data.users;  // Ottiene e imposta gli utenti
                this.successMessage = response.data.message;
                this.errorMessage = '';  // Resetta il messaggio di errore
              } else {
                this.errorMessage = response.data.message;
                this.successMessage = '';  // Resetta il messaggio di successo
              }
            })
            .catch(error => {
              this.errorMessage = `Error: ${error.response.data.message}`;
              this.successMessage = '';  // Resetta il messaggio di successo
            });
        },
        authenticateUser() {
            this.isAuthenticating = true;
            axios.post('http://localhost:5000/api/jellyseer/login', {
                JELLYSEER_API_URL: this.config.JELLYSEER_API_URL,
                JELLYSEER_TOKEN: this.config.JELLYSEER_TOKEN,
                JELLYSEER_USER_NAME: this.selectedUser.name,  // Assumendo che l'utente abbia una proprietà 'name'
                JELLYSEER_PASSWORD: this.userPassword
            })
            .then(response => {
                if (response.data.type === 'success') {
                    this.authenticated = true;  // Login avvenuto con successo
                    this.successMessage = response.data.message;  // Mostra messaggio di successo
                    this.errorMessage = '';  // Pulisci eventuali errori precedenti
                } else {
                    this.authenticated = false;  // Login fallito
                    this.errorMessage = response.data.message;  // Mostra il messaggio di errore
                    this.successMessage = '';  // Pulisci eventuali messaggi di successo
                }
            })
            .catch(error => {
                this.authenticated = false;  // Gestisci gli errori imprevisti
                this.errorMessage = `Login failed: ${error.response?.data?.message || error.message}`;
                this.successMessage = '';  // Pulisci eventuali messaggi di successo
            })
            .finally(() => {
                this.isAuthenticating = false;  // Fine del caricamento
            });
        }
    }
};
</script>

<style scoped>
.step {
    transition: opacity 0.3s ease-in-out;
}

/* Animazione fade */
.fade-enter-active, .fade-leave-active {
    transition: opacity 0.3s ease;
}
.fade-enter, .fade-leave-to /* .fade-leave-active in <2.1.8 */ {
    opacity: 0;
}
</style>
