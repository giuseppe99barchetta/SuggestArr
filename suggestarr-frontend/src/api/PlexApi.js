import axios from 'axios';

export default {
    props: ['config'],
    data() {
        return {
            plexTestState: {
                status: null,
                isTesting: false
            },
            servers: [],
            selectedServer: null,
            selectedServerConnection: null, // Connessione selezionata
            libraries: [],
            selectedLibraries: [],
            manualConfiguration: false, // Modalità di configurazione manuale
            manualServerAddress: '', // Indirizzo del server per configurazione manuale
            manualServerPort: '', // Porta del server per configurazione manuale
            isLoggedIn: false // Stato del login
        };
    },
    methods: {
        toggleLibrarySelection(library) {
            const index = this.selectedLibraries.findIndex(l => l.uuid === library.uuid);
            if (index > -1) {
                this.selectedLibraries.splice(index, 1);
            } else {
                this.selectedLibraries.push(library);
            }

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
                console.log(this.config.PLEX_LIBRARIES)
                this.selectedLibraries = this.libraries.filter(library =>
                    this.config.PLEX_LIBRARIES.includes(library.uuid)
                );
            }
        },
        async loginWithPlex() {
            try {
                // Chiedi al backend il pin e l'URL di login
                const response = await axios.post('/api/plex/auth');
                const { pin_id, auth_url } = response.data;

                // Reindirizza l'utente alla pagina di login di Plex
                window.open(auth_url, '_blank', 'width=800,height=600');

                this.startPolling(pin_id);
            } catch (error) {
                console.error('Error during Plex login:', error);
            }
        },
        async startPolling(pin_id) {
            console.log("Starting polling for Pin ID:", pin_id);
            const interval = setInterval(async () => {
                try {
                    // Controlla se il login è completato e il token è disponibile
                    const response = await axios.get(`/api/plex/check-auth/${pin_id}`);
                    const { auth_token } = response.data;

                    if (auth_token) {
                        // Se ottieni il token, interrompi il polling e salva il token
                        clearInterval(interval);
                        // Puoi salvare il token o inviare il token a una funzione di autenticazione
                        this.$emit('update-config', 'PLEX_TOKEN', auth_token);
                        this.fetchPlexServers(auth_token)
                        this.isLoggedIn = true
                    }
                } catch (error) {
                    console.error('Error checking Plex auth status:', error);
                }
            }, 3000); // Polling ogni 3 secondi
        },
        async fetchPlexServers(auth_token) {
            try {
                const response = await axios.post('/api/plex/servers', {
                    'auth_token': auth_token
                });

                if (response.status === 200 && response.data.servers) {
                    this.servers = response.data.servers;
                    console.log('Plex Servers:', this.servers);

                    if (this.servers.length > 0) {
                        this.selectedServer = this.servers[0];
                    }
                } else {
                    console.error('Failed to fetch servers:', response.data.message);
                }
            } catch (error) {
                console.error('Error fetching Plex servers:', error);
            }
        },
        updateSelectedServer() {
            this.libraries = [] // reset previously loaded library if new Plex server was selected

            if (this.selectedServerConnection === 'manual') {
                this.manualConfiguration = true;
            } else {
                this.manualConfiguration = false;
                // Usa la connessione selezionata per aggiornare la configurazione
                const { address, port, protocol } = this.selectedServerConnection;
                this.$emit('update-config', 'PLEX_API_URL', protocol + '://' + address + ':' + port);
            }
        },
        getServerConnections() {
            // Funzione che raccoglie tutte le connessioni dai server e le prepara per il dropdown
            const connections = [];
            this.servers.forEach(server => {
                server.connections.forEach(connection => {
                    connections.push({
                        serverName: server.name,
                        address: connection.address,
                        port: connection.port,
                        protocol: connection.protocol,
                        secure: connection.protocol === 'https'
                    });
                });
            });
            return connections;
        },
        async fetchLibraries() {
            try {
                let tost_loading_libs = this.$toast.info('Fetching Plex libraries..');
                const response = await axios.post('/api/plex/libraries', {
                    PLEX_API_URL: this.config.PLEX_API_URL,
                    PLEX_TOKEN: this.config.PLEX_TOKEN
                });

                if (response.status === 200 && response.data.items) {
                    this.libraries = response.data.items;
                } else {
                    this.$toast.error('Failed to fetch libraries:', response.data.message);
                }

                tost_loading_libs.dismiss()

            } catch (error) {
                this.$toast.error('Failed to fetch libraries:', error);
            }
        },
    },
    mounted() {
        // Controlla se c'è già un auth_token salvato
        const authToken = this.config.PLEX_TOKEN;
        if (authToken) {
            this.isLoggedIn = true;
            this.fetchPlexServers(authToken);
        }
    },
};