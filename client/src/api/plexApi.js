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
      isLoggedIn: false,
      users: [],                  // Contains the retrieved users
      selectedUsers: [],          // Stores the selected users
    };
  },
  methods: {
    // Toggle and update selected libraries
    toggleLibrarySelection(library) {
      const index = this.selectedLibraries.findIndex(l => l.key === library.key);
      index > -1 ? this.selectedLibraries.splice(index, 1) : this.selectedLibraries.push(library);
      this.updateSelectedLibraries();
    },
    isSelected(libraryId) {
      return this.selectedLibraries.some(library => library.key === libraryId);
    },
    updateSelectedLibraries() {
      const libraryIds = this.selectedLibraries.map(library => library.key);
      this.$emit('update-config', 'PLEX_LIBRARIES', libraryIds);
    },
    loadSelectedLibraries() {
      if (this.config.PLEX_LIBRARIES) {
        this.selectedLibraries = this.libraries.filter(library =>
          this.config.PLEX_LIBRARIES.includes(library.key)
        );
      }
    },

    // Toggle and update selected users
    toggleUserSelection(user) {
      const index = this.selectedUsers.findIndex(u => u.id === user.id);
      index > -1 ? this.selectedUsers.splice(index, 1) : this.selectedUsers.push(user);
      this.updateSelectedUsers();
    },
    isUserSelected(userId) {
      return this.selectedUsers.some(user => user.id === userId);
    },
    updateSelectedUsers() {
      // Save full user objects (id + name) for consistency with Jellyfin
      const users = this.selectedUsers.map(user => ({
        id: user.id,
        name: user.name
      }));
      this.$emit('update-config', 'SELECTED_USERS', users);
    },
    loadSelectedUsers() {
      if (this.config.SELECTED_USERS) {
        // Handle both formats: array of objects or array of IDs (legacy)
        if (this.config.SELECTED_USERS.length > 0) {
          const firstItem = this.config.SELECTED_USERS[0];
          if (typeof firstItem === 'string') {
            // Legacy format: array of IDs
            this.selectedUsers = this.users.filter(user =>
              this.config.SELECTED_USERS.includes(user.id)
            );
          } else if (typeof firstItem === 'object' && firstItem.id) {
            // New format: array of objects
            const selectedIds = this.config.SELECTED_USERS.map(u => u.id);
            this.selectedUsers = this.users.filter(user =>
              selectedIds.includes(user.id)
            );
          }
        }
      }
    },

    // Fetch users from the server
    async fetchUsers() {
      try {
        const response = await this.apiRequest('/api/plex/users', 'post', {
          PLEX_API_URL: this.config.PLEX_API_URL,
          PLEX_TOKEN: this.config.PLEX_TOKEN,
        });

        if (response.status === 200 && response.data.users) {
          this.users = response.data.users;
          this.loadSelectedUsers();
        } else {
          this.$toast.error('Failed to fetch users.');
        }
      } catch (error) {
        this.$toast.error('Error fetching users.');
      }
    },

    async apiRequest(url, method = 'get', data = null) {
      try {
        const response = await axios({
          url,
          method,
          data,
          headers: this.config.headers,
        });
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
      this.libraries = []; // Reset libraries if a new server is selected
      this.users = []
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
        if (server.connections) {
          // Filtra e ordina le connessioni per priorità
          const filteredConnections = server.connections
            .filter(conn => {
              // Escludi connessioni relay (troppo lente)
              if (conn.relay === true || conn.relay === 1) return false;
              return true;
            })
            .sort((a, b) => {
              // Priorità: locale HTTPS > locale HTTP > remota HTTPS > remota HTTP
              const aLocal = a.local === true || a.local === 1;
              const bLocal = b.local === true || b.local === 1;
              const aHttps = a.protocol === 'https';
              const bHttps = b.protocol === 'https';

              if (aLocal !== bLocal) return bLocal - aLocal; // locali prima
              if (aHttps !== bHttps) return bHttps - aHttps; // HTTPS prima
              return 0;
            });

          // Prendi solo le prime 3 connessioni migliori per server
          filteredConnections.slice(0, 3).forEach(connection => {
            const localLabel = (connection.local === true || connection.local === 1) ? ' [Local]' : ' [Remote]';
            connections.push({
              serverName: server.name,
              address: connection.address,
              port: connection.port,
              protocol: connection.protocol,
              secure: connection.protocol === 'https',
              local: connection.local,
              localLabel: localLabel
            });
          });
        }
        return connections;
      }, []);
    },
    async fetchLibraries() {
      this.loadingLibraries = true;
      try {
        const response = await this.apiRequest('/api/plex/libraries', 'post', {
          PLEX_API_URL: this.config.PLEX_API_URL,
          PLEX_TOKEN: this.config.PLEX_TOKEN,
        });

        if (response.status === 200 && response.data.items) {
          this.libraries = response.data.items;
          this.loadSelectedLibraries();
        } else {
          this.$toast.error('Failed to fetch libraries.');
        }
      } catch (error) {
        this.$toast.error('Error fetching libraries.');
      } finally {
        this.loadingLibraries = false;
        this.fetchUsers();
      }
    },
  },
  mounted() {
    const authToken = this.config.PLEX_TOKEN;
    if (authToken) {
      this.isLoggedIn = true;
      this.fetchPlexServers(authToken);
      this.fetchUsers();       // Fetch users on component mount
      this.fetchLibraries();    // Fetch libraries on component mount
    }
  },
};