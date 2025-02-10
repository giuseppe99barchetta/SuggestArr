<template>
    <div>
        <h3 class="text-sm sm:text-lg font-semibold text-gray-300">Database Configuration</h3>
        <p class="text-xs sm:text-sm text-gray-400 mb-4">Configure the database settings below to connect to your preferred database (PostgreSQL, MySQL/MariaDB, or SQLite). By default, SQLite is used for the standard configuration.</p>

        <!-- DB Type Selection -->
        <label for="DB_TYPE" class="block text-xs sm:text-sm font-semibold text-gray-300">Database Type:</label>
        <p class="text-xs sm:text-sm text-gray-400 mb-2">Select the database to store request made from SuggestArr.</p>
        <select v-model="config.DB_TYPE" @change="handleUpdate('DB_TYPE', config.DB_TYPE)"
                class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2">
            <option value="sqlite">SQLite (Default)</option>
            <option value="postgres">PostgreSQL</option>
            <option value="mysql">MySQL/MariaDB</option>
        </select>

        <div v-if="config.DB_TYPE !== 'sqlite'">
            <!-- Host -->
            <label for="DB_HOST" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Database Host:</label>
            <p class="text-xs sm:text-sm text-gray-400 mb-2">Enter the database host address</p>
            <input type="text" :value="config.DB_HOST"
                   @input="handleUpdate('DB_HOST', $event.target.value)"
                   class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                   id="DB_HOST" placeholder="localhost">

            <!-- Port -->
            <label for="DB_PORT" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Database Port:</label>
            <p class="text-xs sm:text-sm text-gray-400 mb-2">Enter the port number for the database. Default for PostgreSQL is 5432, MySQL/MariaDB is 3306.</p>
            <input type="number" :value="config.DB_PORT"
                   @input="handleUpdate('DB_PORT', $event.target.value)"
                   class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                   id="DB_PORT" placeholder="5432">

            <!-- User -->
            <label for="DB_USER" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Database User:</label>
            <p class="text-xs sm:text-sm text-gray-400 mb-2">Enter the username used to connect to your database.</p>
            <input type="text" :value="config.DB_USER"
                   @input="handleUpdate('DB_USER', $event.target.value)"
                   class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                   id="DB_USER" placeholder="root">

            <!-- Password -->
            <label for="DB_PASSWORD" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Database Password:</label>
            <p class="text-xs sm:text-sm text-gray-400 mb-2">Enter the password for your database user.</p>
            <input type="password" :value="config.DB_PASSWORD"
                   @input="handleUpdate('DB_PASSWORD', $event.target.value)"
                   class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                   id="DB_PASSWORD" placeholder="password">

            <!-- Database Name -->
            <label for="DB_NAME" class="block text-xs sm:text-sm font-semibold text-gray-300 mt-4">Database Name:</label>
            <p class="text-xs sm:text-sm text-gray-400 mb-2">Enter the name of the database you wish to connect to.</p>
            <p class="text-xs sm:text-sm font-bold text-yellow-400 mb-2">
                <strong>Important:</strong> The database must be created before connecting.
            </p>
            <input type="text" :value="config.DB_NAME"
                   @input="handleUpdate('DB_NAME', $event.target.value)"
                   class="w-full bg-gray-700 border border-gray-600 rounded-lg shadow-md px-4 py-2"
                   id="DB_NAME" placeholder="suggestarr">

            <!-- Error Message -->
            <p class="text-xs sm:text-sm text-red-500 mt-2" v-if="dbError">{{ dbError }}</p>
            <p class="text-xs sm:text-sm text-green-500 mt-2" v-if="dbSuccess">{{ dbSuccess }}</p>

            <!-- Test Connection Button -->
            <div class="flex justify-between mt-4">
                <button @click="testConnection" 
                        class="bg-green-600 hover:bg-green-500 text-white font-bold py-4 px-8 rounded-lg w-full">
                        {{ buttonText }}
                </button>
            </div>

        </div>

        <div class="flex justify-between mt-8 space-x-4">
            <button @click="$emit('previous-step')" class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-4 px-8 rounded-lg w-full">Back</button>
            <button @click="$emit('next-step')" 
                    :disabled="!isTestSuccessful"
                    class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full">Next</button>
        </div>
    </div>
</template>

<script>
import axios from 'axios';

export default {
    props: ['config'],
    data() {
        return {
            dbError: '',
            buttonText: 'Test Connection',
            isTestSuccessful: true,
        };
    },
    created() {
        if (!this.config.DB_TYPE) {
            this.config.DB_TYPE = 'sqlite';
            this.isTestSuccessful = true;
        }
    },
    watch: {
        isTested(newValue) {
            this.isNextDisabled = !newValue && this.config.DB_TYPE !== 'sqlite';
        }
    },
    methods: {
        handleUpdate(key, value) {
            this.$emit('update-config', key, value);
            console.log(key, value);
            console.log(key == 'DB_TYPE' && value == 'sqlite')
            if (key == 'DB_TYPE' && value == 'sqlite') {
                this.isTestSuccessful = true;
            } else {
                this.isTestSuccessful = false;
            }
        },
        async testConnection() {
            this.dbError = '';
            this.buttonText = 'Testing...';

            // Per PostgreSQL, MySQL/MariaDB, possiamo tentare una connessione tramite API o direttamente
            try {
                const response = await axios.post('/api/config/test-db-connection', this.config);
                if (response.data.status == 'success') {
                    this.buttonText = 'Connection Successful!';
                    this.isTestSuccessful = true;
                } else {
                    this.dbError = 'Failed to connect to the database.';
                    this.buttonText = 'Test Connection';
                    this.isTestSuccessful = false;
                }
            } catch (error) {
                this.dbError = 'Error connecting to the database: ' + error.message;
                this.buttonText = 'Test Connection'; 
                this.isTestSuccessful = false;
            }
            
        }
    }
};
</script>
