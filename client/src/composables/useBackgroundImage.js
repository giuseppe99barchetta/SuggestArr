import { ref, onUnmounted } from 'vue';
import { fetchRandomMovieImage } from '@/api/tmdbApi';

export function useBackgroundImage() {
  const backgroundImageUrl = ref('/images/default1.jpg');
  const isTransitioning = ref(false);
  const intervalId = ref(null);
  const defaultImages = ['/images/default1.jpg', '/images/default2.jpg', '/images/default3.jpg'];
  const currentDefaultImageIndex = ref(0);

  // Funzione per cambiare immagine con un piccolo "stato" di transizione
  async function changeBackground(newUrl) {
    if (!newUrl) return;

    const img = new Image();
    img.src = newUrl;

    img.onload = () => {
      // 1. Inizia la sfumatura (l'opacità scende)
      isTransitioning.value = true;

      // 2. Aspetta che la sfumatura in uscita sia a metà (es. 400ms)
      setTimeout(() => {
        // 3. Cambia l'immagine mentre è "sbiadita"
        backgroundImageUrl.value = newUrl;

        // 4. Aspetta un attimo e fai risalire l'opacità
        setTimeout(() => {
          isTransitioning.value = false;
        }, 50); 
      }, 400); // Questo tempo deve essere circa la metà della transition CSS
    };
  }

  function startDefaultImageRotation() {
    stopBackgroundImageRotation(); // Sicurezza: pulisci intervalli esistenti
    intervalId.value = setInterval(() => {
      currentDefaultImageIndex.value = (currentDefaultImageIndex.value + 1) % defaultImages.length;
      changeBackground(defaultImages[currentDefaultImageIndex.value]);
    }, 10000);
  }

  function startBackgroundImageRotation(apiKey) {
    stopBackgroundImageRotation();
    // Carica la prima immagine immediatamente
    fetchRandomMovieImageAsync(apiKey);
    // Poi avvia l'intervallo
    intervalId.value = setInterval(() => fetchRandomMovieImageAsync(apiKey), 10000);
  }

  async function fetchRandomMovieImageAsync(apiKey) {
    try {
      const imageUrl = await fetchRandomMovieImage(apiKey);
      if (imageUrl) {
        await changeBackground(imageUrl);
      }
    } catch (error) {
      console.error("Errore rotazione sfondo:", error);
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
    backgroundImageUrl,
    isTransitioning,
    startDefaultImageRotation,
    startBackgroundImageRotation,
    stopBackgroundImageRotation,
  };
}