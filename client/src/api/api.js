import axios from 'axios';

// Function to test the TMDB API key via the backend proxy (key never exposed client-side)
export const testTmdbApi = (apiKey) => {
    return axios.post('/api/tmdb/test', { api_key: apiKey });
};

// Function to test the OMDb API key (IMDB ratings integration)
export const testOmdbApi = (apiKey) => {
    return axios.post('/api/omdb/test', { api_key: apiKey });
};

// Function to test Jellyfin configuration
export const testJellyfinApi = (url, token) => {
    const jellyfinApiUrl = `${url}/Users`; // Endpoint to retrieve Jellyfin users
    return axios.get(jellyfinApiUrl, {
        headers: {
            'X-Emby-Token': token // Send Jellyfin API token in the header
        }
    });
};

// Function to test the Jellyseer/Overseer configuration and fetch users
export const testJellyseerApi = () => {
    return axios.get('/api/seer/get_users');
};

// Function to authenticate a user in Jellyseer/Overseer
export const authenticateUser = (url, token, userName, password) => {
    return axios.post('/api/seer/login', {
        SEER_API_URL: url,
        SEER_TOKEN: token,
        SEER_USER_NAME: userName,
        SEER_PASSWORD: password
    });
};

// Function to fetch Jellyfin libraries
export function fetchJellyfinLibraries() {
    return axios.get('/api/jellyfin/libraries');
}

// Function to fetch Jellyfin Users
export function fetchJellyfinUsers() {
    return axios.get('/api/jellyfin/users');
}

// Function to fetch Plex libraries
export function fetchPlexLibraries() {
    return axios.get('/api/plex/libraries');
}

// Function to fetch Plex Users
export function fetchPlexUsers() {
    return axios.get('/api/plex/users');
}

// Function to fetch Radarr servers from Overseerr for anime profile configuration
export const fetchRadarrServers = () => {
    return axios.get('/api/seer/radarr-servers');
};

// Function to fetch Sonarr servers from Overseerr for anime profile configuration
export const fetchSonarrServers = () => {
    return axios.get('/api/seer/sonarr-servers');
};

// AI Search: semantic content search powered by LLM + TMDB
export const aiSearch = (query, mediaType = 'movie', userIds = [], maxResults = 12, useHistory = true, excludeWatched = true) => {
    return axios.post('/api/ai-search/query', {
        query,
        media_type: mediaType,
        user_ids: userIds,
        max_results: maxResults,
        use_history: useHistory,
        exclude_watched: excludeWatched,
    });
};

// AI Search: fetch requests made via AI Search
export const getAiSearchRequests = (page = 1, perPage = 12, sortBy = 'date-desc') => {
    return axios.get('/api/automation/requests/ai-search', {
        params: { page, per_page: perPage, sort_by: sortBy },
    });
};

// AI Search: request a specific TMDB item via Jellyseer/Overseer
export const aiSearchRequest = (tmdbId, mediaType, rationale = '', metadata = {}, searchQuery = '') => {
    return axios.post('/api/ai-search/request', {
        tmdb_id: tmdbId,
        media_type: mediaType,
        rationale,
        metadata,
        search_query: searchQuery,
    });
};

// AI Search: check whether LLM is configured and AI search is available
export const aiSearchStatus = () => {
    return axios.get('/api/ai-search/status');
};

// Config export: download a full configuration snapshot (admin only, includes API keys)
export const exportConfig = () => {
    return axios.get('/api/config/export', { responseType: 'json' });
};

// Config import: restore a configuration snapshot (admin only)
export const importConfig = (snapshot) => {
    return axios.post('/api/config/import', snapshot);
};

// User management (admin only)
export const getUsers = () => axios.get('/api/users');
export const createUserAdmin = (data) => axios.post('/api/users', data);
export const updateUser = (id, data) => axios.patch(`/api/users/${id}`, data);
export const deleteUser = (id) => axios.delete(`/api/users/${id}`);

// Media profile linking (any authenticated user)
export const getMyLinks = () => axios.get('/api/users/me/links');
export const linkJellyfin = (data) => axios.post('/api/users/me/link/jellyfin', data);
export const linkEmby = (data) => axios.post('/api/users/me/link/emby', data);
export const unlinkProvider = (provider) => axios.delete(`/api/users/me/link/${provider}`);
export const plexOAuthStart = () => axios.get('/api/users/me/link/plex/oauth-start');
export const plexOAuthPoll = (pinId) => axios.post('/api/users/me/link/plex/oauth-poll', { pin_id: pinId });