import axios from 'axios';

const MAX_RETRIES = 3;
const BASE_RETRY_DELAY = 1000; // ms
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

export const fetchRandomMovieImage = async (apiKey) => {
  if (!apiKey) return null;

  const randomPage = Math.floor(Math.random() * 100) + 1;
  
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await axios.get('https://api.themoviedb.org/3/movie/popular', {
        params: { api_key: apiKey, page: randomPage, include_adult: false },
        timeout: 10000,
      });

      if (!response.data || !response.data.results) {
        throw new Error('Api response not valid');
      }

      const movies = response.data.results;
      if (!movies.length) {
        throw new Error('No movies found on page');
      }
      
      const randomMovie = movies[Math.floor(Math.random() * movies.length)];
      if (!randomMovie || !randomMovie.backdrop_path) {
        throw new Error('Selected movie has no backdrop');
      }
      
      return `https://image.tmdb.org/t/p/w1280${randomMovie.backdrop_path}`;
    } catch (error) {
      // Gestione specifica per rate limit TMDB (429)
      if (error.response?.status === 429 && error.response.headers['retry-after']) {
        const retryAfter = parseInt(error.response.headers['retry-after']) * 1000;
        console.warn(`Rate limit TMDB (429). Wait ${retryAfter}ms...`);
        await delay(retryAfter);
        continue;
      }

      if (attempt === MAX_RETRIES) {
        console.error('Failed to fetch movie image after retries:', error.message || error);
        return null;
      }
      
      const delayMs = BASE_RETRY_DELAY * Math.pow(2, attempt - 1); // Exponential backoff
      console.warn(`Attempt ${attempt} failed (${error.message || error.code}), retry in ${delayMs}ms...`);
      await delay(delayMs);
    }
  }
  
  return null;
};
