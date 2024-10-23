import axios from 'axios';

export default {
    props: ['config'],
    data() {
        return {
            loading: false,
            loadingLibraries: false,
            servers: [],
            selectedServer: null,
            selectedServerConnection: null, 
            libraries: [],
            selectedLibraries: [],
            manualConfiguration: false,
            manualServerAddress: '',
            isLoggedIn: false
        };
    },
    methods: {
        toggleLibrarySelection(library) {
            const index = this.selectedLibraries.findIndex(l => l.uuid === library.uuid);
            index > -1 ? this.selectedLibraries.splice(index, 1) : this.selectedLibraries.push(library);
            this.updateSelectedLibraries();
        },
        isSelected(libraryId) {
            return this.selectedLibraries.some(library => library.uuid === libraryId);
        },
        updateSelectedLibraries() {
            const libraryIds = this.selectedLibraries.map(library => library.uuid);
            this.$emit('updateConfig', 'PLEX_LIBRARIES', libraryIds);
        },
        loadSelectedLibraries() {
            if (this.config.PLEX_LIBRARIES) {
                this.selectedLibraries = this.libraries.filter(library =>
                    this.config.PLEX_LIBRARIES.includes(library.uuid)
                );
            }
        },

        // Funzione separata per eseguire le chiamate API
        async apiRequest(url, method = 'get', data = null) {
            try {
                const response = await axios({ url, method, data, headers: this.config.headers });
                return response;
            } catch (error) {
                console.error(`API Request error: ${error.message}`);
                throw error;
            }
        },

        async loginWithPlex() {
            try {
                this.loading = true;
                const response = await this.apiRequest('/api/plex/auth', 'post');
                const { pin_id, auth_url } = response.data;

                window.open(auth_url, '_blank', 'width=800,height=600');
                this.startPolling(pin_id);
            } catch (error) {
                this.$toast.error('Error during Plex login.');
            }
        },

        async startPolling(pin_id) {
            const interval = setInterval(async () => {
                try {
                    const response = await this.apiRequest(`/api/plex/check-auth/${pin_id}`);
                    const { auth_token } = response.data;

                    if (auth_token) {
                        clearInterval(interval);
                        this.$emit('update-config', 'PLEX_TOKEN', auth_token);
                        await this.fetchPlexServers(auth_token);
                        this.isLoggedIn = true;
                    }
                } catch (error) {
                    console.error('Error checking Plex auth status:', error);
                } finally {
                    this.loading = false;
                }
            }, 3000);
        },

        async fetchPlexServers(auth_token) {
            try {
                const response = await this.apiRequest('/api/plex/servers', 'post', { auth_token });
                if (response.status === 200 && response.data.servers) {
                    this.servers = response.data.servers;
                    if (this.servers.length > 0) {
                        this.selectedServer = this.servers[0];
                    }
                } else {
                    this.$toast.error('Failed to fetch servers.');
                }
            } catch (error) {
                this.$toast.error('Error fetching Plex servers.');
            }
        },

        updateSelectedServer() {
            this.libraries = [];  // Reset libraries if a new server is selected
            if (this.selectedServerConnection === 'manual') {
                this.manualConfiguration = true;
            } else {
                this.manualConfiguration = false;
                const { address, port, protocol } = this.selectedServerConnection;
                this.$emit('update-config', 'PLEX_API_URL', `${protocol}://${address}:${port}`);
            }
        },

        getServerConnections() {
            return this.servers.reduce((connections, server) => {
                server.connections.forEach(connection => {
                    connections.push({
                        serverName: server.name,
                        address: connection.address,
                        port: connection.port,
                        protocol: connection.protocol,
                        secure: connection.protocol === 'https'
                    });
                });
                return connections;
            }, []);
        },

        async fetchLibraries() {
            this.loadingLibraries = true;
            try {
                let tost_loading_libs = this.$toast.info('Fetching Plex libraries...');
                const response = await this.apiRequest('/api/plex/libraries', 'post', {
                    PLEX_API_URL: this.config.PLEX_API_URL,
                    PLEX_TOKEN: this.config.PLEX_TOKEN
                });

                if (response.status === 200 && response.data.items) {
                    this.libraries = response.data.items;
                } else {
                    this.$toast.error('Failed to fetch libraries.');
                }

                tost_loading_libs.dismiss();
            } catch (error) {
                this.$toast.error('Error fetching libraries.');
            } finally {
                this.loadingLibraries = false;
            }
        },
    },
    mounted() {
        const authToken = this.config.PLEX_TOKEN;
        if (authToken) {
            this.isLoggedIn = true;
            this.fetchPlexServers(authToken);
        }
    }
};
