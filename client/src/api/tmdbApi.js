import axios from 'axios';

const MAX_RETRIES = 3;
const BASE_RETRY_DELAY = 1000; // ms
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Fetch a random movie backdrop URL via the backend TMDB proxy.
 *
 * The backend loads the API key from the database and calls TMDB on behalf
 * of the client. The key is never sent to or visible in the browser.
 *
 * @returns {Promise<string|null>} Full image URL or null on failure / not configured.
 */
export const fetchRandomMovieImage = async () => {
  const randomPage = Math.floor(Math.random() * 100) + 1;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await axios.get('/api/tmdb/popular', {
        params: { page: randomPage, include_adult: false },
        timeout: 10000,
      });

      const movies = response.data?.results;
      if (!movies?.length) {
        throw new Error('No movies found on page');
      }

      const randomMovie = movies[Math.floor(Math.random() * movies.length)];
      if (!randomMovie?.backdrop_path) {
        throw new Error('Selected movie has no backdrop');
      }

      return `https://image.tmdb.org/t/p/w1280${randomMovie.backdrop_path}`;
    } catch (error) {
      // Backend rate-limit pass-through
      if (error.response?.status === 429 && error.response.headers['retry-after']) {
        const retryAfter = parseInt(error.response.headers['retry-after']) * 1000;
        console.warn(`Rate limit hit. Waiting ${retryAfter}ms...`);
        await delay(retryAfter);
        continue;
      }

      // TMDB not configured — fail silently, fallback to default images
      if (error.response?.status === 400) {
        return null;
      }

      if (attempt === MAX_RETRIES) {
        console.error('Failed to fetch movie image after retries:', error.message || error);
        return null;
      }

      const delayMs = BASE_RETRY_DELAY * Math.pow(2, attempt - 1);
      console.warn(`Attempt ${attempt} failed (${error.message || error.code}), retry in ${delayMs}ms...`);
      await delay(delayMs);
    }
  }

  return null;
};
