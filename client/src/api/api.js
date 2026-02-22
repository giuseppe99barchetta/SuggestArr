import axios from 'axios';

// Function to test the TMDB API key
export const testTmdbApi = (apiKey) => {
    const tmdbApiUrl = `https://api.themoviedb.org/3/movie/550?api_key=${apiKey}`; // Movie ID 550 is Fight Club
    return axios.get(tmdbApiUrl);
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
export const testJellyseerApi = (url, token) => {
    return axios.post('/api/seer/get_users', {
        SEER_API_URL: url,
        SEER_TOKEN: token
    });
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
export function fetchJellyfinLibraries(apiUrl, apiKey) {
    return axios.post(`/api/jellyfin/libraries`, {
        JELLYFIN_API_URL: apiUrl,
        JELLYFIN_TOKEN: apiKey
    });
}

// Function to fetch Jellyfin Users
export function fetchJellyfinUsers(apiUrl, apiKey) {
    return axios.post(`/api/jellyfin/users`, {
        JELLYFIN_API_URL: apiUrl,
        JELLYFIN_TOKEN: apiKey
    });
}

// Function to fetch Plex libraries
export function fetchPlexLibraries(apiUrl, token) {
    return axios.post('/api/plex/libraries', {
        PLEX_API_URL: apiUrl,
        PLEX_TOKEN: token
    });
}

// Function to fetch Plex Users
export function fetchPlexUsers(apiUrl, token) {
    return axios.post('/api/plex/users', {
        PLEX_API_URL: apiUrl,
        PLEX_TOKEN: token
    });
}

// Function to fetch Radarr servers from Overseerr for anime profile configuration
export const fetchRadarrServers = (url, token, sessionToken) => {
    return axios.post('/api/seer/radarr-servers', {
        SEER_API_URL: url,
        SEER_TOKEN: token,
        SEER_SESSION_TOKEN: sessionToken
    });
};

// Function to fetch Sonarr servers from Overseerr for anime profile configuration
export const fetchSonarrServers = (url, token, sessionToken) => {
    return axios.post('/api/seer/sonarr-servers', {
        SEER_API_URL: url,
        SEER_TOKEN: token,
        SEER_SESSION_TOKEN: sessionToken
    });
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
export const aiSearchRequest = (tmdbId, mediaType, rationale = '', metadata = {}) => {
    return axios.post('/api/ai-search/request', {
        tmdb_id: tmdbId,
        media_type: mediaType,
        rationale,
        metadata,
    });
};

// AI Search: check whether LLM is configured and AI search is available
export const aiSearchStatus = () => {
    return axios.get('/api/ai-search/status');
};