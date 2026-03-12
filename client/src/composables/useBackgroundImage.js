import { ref, onUnmounted } from 'vue';
import { fetchRandomMovieImage } from '@/api/tmdbApi';

export function useBackgroundImage() {
  const bg1Url = ref('/images/default1.jpg');
  const bg2Url = ref('/images/default1.jpg');
  // 'bg1' is initially visible; 'bg2' is the hidden layer waiting for the next image
  const activeBg = ref('bg1');
  const isTransitioning = ref(false);
  const intervalId = ref(null);
  const defaultImages = ['/images/default1.jpg', '/images/default2.jpg', '/images/default3.jpg'];
  const currentDefaultImageIndex = ref(0);

  // Crossfade to a new image using two alternating layers.
  // Step 1: write the new URL onto the hidden layer.
  // Step 2: after two animation frames (so Vue has painted the new image),
  //         swap which layer is "visible" – the CSS opacity transition does the rest.
  function changeBackground(newUrl) {
    if (!newUrl) return;
    if (isTransitioning.value) return;

    const img = new Image();
    img.src = newUrl;

    img.onload = () => {
      isTransitioning.value = true;

      const nextBg = activeBg.value === 'bg1' ? 'bg2' : 'bg1';

      // Write the new image onto the currently-hidden layer
      if (nextBg === 'bg1') {
        bg1Url.value = newUrl;
      } else {
        bg2Url.value = newUrl;
      }

      // Double rAF: first frame lets Vue render the new background-image onto the
      // hidden layer; second frame triggers the class swap and starts the CSS fade.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          activeBg.value = nextBg;
          setTimeout(() => {
            isTransitioning.value = false;
          }, 1000); // matches CSS transition: opacity 1s
        });
      });
    };
  }

  function startDefaultImageRotation() {
    stopBackgroundImageRotation();
    intervalId.value = setInterval(() => {
      currentDefaultImageIndex.value = (currentDefaultImageIndex.value + 1) % defaultImages.length;
      changeBackground(defaultImages[currentDefaultImageIndex.value]);
    }, 10000);
  }

  function startBackgroundImageRotation() {
    stopBackgroundImageRotation();
    fetchRandomMovieImageAsync();
    intervalId.value = setInterval(() => fetchRandomMovieImageAsync(), 10000);
  }

  async function fetchRandomMovieImageAsync() {
    try {
      const imageUrl = await fetchRandomMovieImage();
      if (imageUrl) {
        changeBackground(imageUrl);
      } else if (imageUrl === null) {
        console.warn("TMDB not configured or no image, falling back to default rotation.");
        startDefaultImageRotation();
      }
    } catch (error) {
      console.error("Background rotation error:", error);
      startDefaultImageRotation();
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
    bg1Url,
    bg2Url,
    activeBg,
    isTransitioning,
    startDefaultImageRotation,
    startBackgroundImageRotation,
    stopBackgroundImageRotation,
  };
}