import { ref, onUnmounted } from 'vue';
import { fetchRandomMovieImage } from '@/api/tmdbApi';

export function useBackgroundImage() {
  const backgroundImageUrl = ref('');
  const intervalId = ref(null);
  const defaultImages = ['/images/default1.jpg', '/images/default2.jpg', '/images/default3.jpg'];
  const currentDefaultImageIndex = ref(0);

  function startDefaultImageRotation() {
    backgroundImageUrl.value = defaultImages[currentDefaultImageIndex.value];
    intervalId.value = setInterval(() => {
      currentDefaultImageIndex.value = (currentDefaultImageIndex.value + 1) % defaultImages.length;
      backgroundImageUrl.value = defaultImages[currentDefaultImageIndex.value];
    }, 10000);
  }

  async function fetchRandomMovieImageAsync(apiKey) {
    const imageUrl = await fetchRandomMovieImage(apiKey);
    if (imageUrl) {
      const img = new Image();
      img.src = imageUrl;
      img.onload = () => {
        backgroundImageUrl.value = imageUrl;
      };
    }
  }

  function startBackgroundImageRotation(apiKey) {
    fetchRandomMovieImageAsync(apiKey);
    intervalId.value = setInterval(() => fetchRandomMovieImageAsync(apiKey), 10000);
  }

  function stopBackgroundImageRotation() {
    if (intervalId.value) {
      clearInterval(intervalId.value);
      intervalId.value = null;
    }
  }

  onUnmounted(() => {
    stopBackgroundImageRotation();
  });

  return {
    backgroundImageUrl,
    startDefaultImageRotation,
    startBackgroundImageRotation,
    stopBackgroundImageRotation,
  };
}
