import axios from 'axios';

// Funzione per testare la chiave API di TMDB
export const testTmdbApi = (apiKey) => {
    const tmdbApiUrl = `https://api.themoviedb.org/3/movie/550?api_key=${apiKey}`; // ID 550 è Fight Club
    return axios.get(tmdbApiUrl);
};

// Funzione per testare la configurazione Jellyfin
export const testJellyfinApi = (url, token) => {
    const jellyfinApiUrl = `${url}/Users`; // Endpoint per ottenere gli utenti Jellyfin
    return axios.get(jellyfinApiUrl, {
        headers: {
            'X-Emby-Token': token // Invia la chiave API di Jellyfin nell'header
        }
    });
};

// Funzione per testare la configurazione Jellyseer e ottenere gli utenti
export const testJellyseerApi = (url, token) => {
    return axios.post('http://localhost:5000/api/jellyseer/get_users', {
        JELLYSEER_API_URL: url,
        JELLYSEER_TOKEN: token
    });
};

// Funzione per autenticare un utente in Jellyseer
export const authenticateUser = (url, token, userName, password) => {
    return axios.post('http://localhost:5000/api/jellyseer/login', {
        JELLYSEER_API_URL: url,
        JELLYSEER_TOKEN: token,
        JELLYSEER_USER_NAME: userName,
        JELLYSEER_PASSWORD: password
    });
};

export function fetchJellyfinLibraries(apiUrl, apiKey) {
    return axios.post(`http://localhost:5000/api/jellyfin/libraries`, {
        JELLYFIN_API_URL: apiUrl,
        JELLYFIN_TOKEN: apiKey
    });
}