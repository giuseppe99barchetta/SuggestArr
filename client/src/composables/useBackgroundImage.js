import { ref, onUnmounted } from 'vue';
import { fetchRandomMovieImage } from '@/api/tmdbApi';

export function useBackgroundImage() {
  const currentBackgroundUrl = ref('/images/default1.jpg');
  const nextBackgroundUrl = ref('/images/default1.jpg');
  const isTransitioning = ref(false);
  const intervalId = ref(null);
  const defaultImages = ['/images/default1.jpg', '/images/default2.jpg', '/images/default3.jpg'];
  const currentDefaultImageIndex = ref(0);

  // Function to change the image with a smooth crossfade
  async function changeBackground(newUrl) {
    if (!newUrl) return;

    const img = new Image();
    img.src = newUrl;

    img.onload = () => {
      // 1. Set the new image in the hidden layer
      nextBackgroundUrl.value = newUrl;
      
      // 2. Start the transition
      isTransitioning.value = true;

      // 3. Wait for the transition to complete (800ms)
      setTimeout(() => {
        // 4. Swap the images
        currentBackgroundUrl.value = nextBackgroundUrl.value;
        isTransitioning.value = false;
      }, 800); // Matches the CSS transition duration
    };
  }

  function startDefaultImageRotation() {
    stopBackgroundImageRotation(); // Safety check: clear existing intervals
    intervalId.value = setInterval(() => {
      currentDefaultImageIndex.value = (currentDefaultImageIndex.value + 1) % defaultImages.length;
      changeBackground(defaultImages[currentDefaultImageIndex.value]);
    }, 10000);
  }

  function startBackgroundImageRotation(apiKey) {
    stopBackgroundImageRotation();
    // Load the first image immediately
    fetchRandomMovieImageAsync(apiKey);
    // Then start the interval
    intervalId.value = setInterval(() => fetchRandomMovieImageAsync(apiKey), 10000);
  }

  async function fetchRandomMovieImageAsync(apiKey) {
    try {
      const imageUrl = await fetchRandomMovieImage(apiKey);
      if (imageUrl) {
        await changeBackground(imageUrl);
      }
    } catch (error) {
      console.error("Background rotation error:", error);
    }
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
    currentBackgroundUrl,
    nextBackgroundUrl,
    isTransitioning,
    startDefaultImageRotation,
    startBackgroundImageRotation,
    stopBackgroundImageRotation,
  };
}