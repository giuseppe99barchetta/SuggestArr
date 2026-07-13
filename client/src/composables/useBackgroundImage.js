import { ref, onUnmounted } from 'vue';
import { fetchRandomMovieImages } from '@/api/tmdbApi';

const ROTATION_INTERVAL = 10000;

export function useBackgroundImage() {
  const bg1Url = ref('/images/default1.jpg');
  const bg2Url = ref('/images/default1.jpg');
  // 'bg1' is initially visible; 'bg2' is the hidden layer waiting for the next image
  const activeBg = ref('bg1');
  const isTransitioning = ref(false);
  const intervalId = ref(null);
  const defaultImages = ['/images/default1.jpg', '/images/default2.jpg', '/images/default3.jpg'];
  const currentDefaultImageIndex = ref(0);
  const movieImages = ref([]);
  const currentMovieImageIndex = ref(0);
  const rotationMode = ref(null);

  // Crossfade to a new image using two alternating layers.
  // Step 1: write the new URL onto the hidden layer.
  // Step 2: after two animation frames (so Vue has painted the new image),
  //         swap which layer is "visible" – the CSS opacity transition does the rest.
  function changeBackground(newUrl) {
    if (!newUrl) return;
    const currentUrl = activeBg.value === 'bg1' ? bg1Url.value : bg2Url.value;
    if (newUrl === currentUrl) return;
    if (isTransitioning.value) return;

    const img = new Image();
    img.decoding = 'async';
    let transitionStarted = false;

    const showPreloadedImage = () => {
      if (transitionStarted) return;
      transitionStarted = true;
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

    img.onload = showPreloadedImage;
    img.onerror = () => {
      isTransitioning.value = false;
    };
    img.src = newUrl;

    if (img.complete) {
      showPreloadedImage();
    }
  }

  function startDefaultImageRotation() {
    clearRotationTimer();
    rotationMode.value = 'default';
    intervalId.value = setInterval(() => {
      currentDefaultImageIndex.value = (currentDefaultImageIndex.value + 1) % defaultImages.length;
      changeBackground(defaultImages[currentDefaultImageIndex.value]);
    }, ROTATION_INTERVAL);
  }

  function startBackgroundImageRotation() {
    clearRotationTimer();
    rotationMode.value = 'tmdb';
    showNextMovieImage();
    intervalId.value = setInterval(showNextMovieImage, ROTATION_INTERVAL);
  }

  async function showNextMovieImage() {
    try {
      const images = await fetchRandomMovieImages();
      if (images?.length) {
        movieImages.value = images;
        currentMovieImageIndex.value %= images.length;
        changeBackground(images[currentMovieImageIndex.value]);
        currentMovieImageIndex.value = (currentMovieImageIndex.value + 1) % images.length;
      } else {
        console.warn("TMDB not configured or no image, falling back to default rotation.");
        startDefaultImageRotation();
      }
    } catch (error) {
      console.error("Background rotation error:", error);
      startDefaultImageRotation();
    }
  }

  function clearRotationTimer() {
    if (intervalId.value) {
      clearInterval(intervalId.value);
      intervalId.value = null;
    }
  }

  function stopBackgroundImageRotation() {
    clearRotationTimer();
    rotationMode.value = null;
  }

  function handleVisibilityChange() {
    if (document.hidden) {
      clearRotationTimer();
    } else if (rotationMode.value === 'tmdb') {
      startBackgroundImageRotation();
    } else if (rotationMode.value === 'default') {
      startDefaultImageRotation();
    }
  }

  document.addEventListener('visibilitychange', handleVisibilityChange);

  onUnmounted(() => {
    stopBackgroundImageRotation();
    document.removeEventListener('visibilitychange', handleVisibilityChange);
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
