import axios from 'axios';

export const fetchRandomMovieImage = async (apiKey) => {
  if (!apiKey) return null;

  const randomPage = Math.floor(Math.random() * 100) + 1;
  try {
    const response = await axios.get('https://api.themoviedb.org/3/movie/popular', {
      params: { api_key: apiKey, page: randomPage },
    });

    const movies = response.data.results;
    const randomMovie = movies[Math.floor(Math.random() * movies.length)];
    return `https://image.tmdb.org/t/p/w1280${randomMovie.backdrop_path}`;
  } catch (error) {
    console.error('Failed to fetch movie image:', error);
    return null;
  }
};