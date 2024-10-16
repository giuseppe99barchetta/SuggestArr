new Vue({
    el: '#app',
    data: {
        config: {
            TMDB_API_KEY: '',
            JELLYFIN_API_URL: '',
            JELLYFIN_TOKEN: '',
            JELLYSEER_API_URL: '',
            JELLYSEER_TOKEN: '',
            MAX_SIMILAR_MOVIE: '5',
            MAX_SIMILAR_TV: '2',
            CRON_TIMES: '0 0 * * *',
            JELLYSEER_USER: ''
        },
        activeTab: 'config',
        users: [],
        isConfigSaved: false,
        isLoading: false
    },
    mounted() {
        this.fetchConfig();
        // Check if the fields have values, and if so, consider the config as saved
        if (this.config.TMDB_API_KEY && this.config.JELLYFIN_API_URL && this.config.JELLYFIN_TOKEN && this.config.JELLYSEER_API_URL && this.config.JELLYSEER_TOKEN) {
            this.isConfigSaved = true;
        }

        // Listener for real-time cron to time conversion
        const cronInput = document.getElementById('CRON_TIMES');
        const cronDescriptionElement = document.getElementById('cron-description');

        cronInput.addEventListener('input', function () {
            const cronValue = cronInput.value;
            try {
                const humanReadable = cronstrue.toString(cronValue);
                cronDescriptionElement.textContent = humanReadable;
            } catch (err) {
                cronDescriptionElement.textContent = 'Invalid cron expression';
            }
        });
    },
    methods: {
        fetchConfig() {
            axios.get('/api/config')
                .then(response => {
                    this.config = response.data;
                    this.fetchUsers();
                    this.isConfigSaved = true;
                })
                .catch(error => {
                    console.error('Error fetching configuration:', error);
                    this.showToast('Error fetching configuration:' + error, 'error');
                });
        },
        fetchUsers() {
            if (this.config.JELLYSEER_TOKEN && this.config.JELLYSEER_API_URL) {
                axios.post('/api/get_users', this.config, {
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => {
                    if (response.data.type === 'success') {
                        this.users = response.data.users;
                    } else {
                        this.users = []
                        this.config.JELLYSEER_USER = 'default'
                        this.showToast(response.data.message, 'error');
                    }
                })
                .catch(error => {
                    this.users = []
                    this.config.JELLYSEER_USER = 'default'
                    this.showToast('Failed to fetch users. Please check the API key.', 'error');
                });
            } else {
                // If API key or URL is not provided, clear the users list
                this.config.JELLYSEER_USER = 'default'
                this.users = [];
            }
        },
        saveConfig() {
            axios.post('/api/save', this.config, {
                headers: {
                    'Content-Type': 'application/json'
                }
                })
                .then(response => {
                    this.showToast(response.data.message, 'success');
                })
                .catch(error => {
                    if (error.response && error.response.data && error.response.data.message) {
                        this.showToast(error.response.data.message, 'error');
                    } else {
                        this.showToast('An unexpected error occurred.', 'error');
                    }
                });
        },
        forceRun() {
            this.isLoading = true;
            axios.post('/run_now')
            .then(response => {
                this.showToast(response.data.message, 'success');
            })
            .catch(error => {
                console.error(error.response);
                this.showToast('Error starting the process.', 'error');
            })
            .finally(() => {
                this.isLoading = false;
            });
        },
        showToast(message, status) {
            const toast = document.getElementById('toast');
            const toastMessage = document.getElementById('toast-message');
            toastMessage.innerText = message;

            if (status === 'success') {
                toast.classList.remove('bg-red-500');
                toast.classList.add('bg-green-500');
            } else if (status === 'error') {
                toast.classList.remove('bg-green-500');
                toast.classList.add('bg-red-500');
            }

            // Show toast
            toast.classList.remove('opacity-0');
            toast.classList.add('opacity-100');

            // Hide toast after 3 seconds
            setTimeout(() => {
                toast.classList.remove('opacity-100');
                toast.classList.add('opacity-0');
            }, 3000);
        },
    }
});