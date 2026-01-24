export default {
  data() {
    return {
      backgroundImageUrl: "",
      nextBackgroundImageUrl: "",
      isTransitioning: false,
      intervalId: null,
      defaultImages: ["/images/default1.jpg", "/images/default2.jpg", "/images/default3.jpg"],
      currentDefaultImageIndex: 0,
    };
  },
  methods: {
    async changeBackground(newUrl) {
      this.nextBackgroundImageUrl = newUrl;
      this.isTransitioning = true; 
    },
    startDefaultImageRotation() {
      this.changeBackground(this.defaultImages[this.currentDefaultImageIndex]);
      this.intervalId = setInterval(() => {
        this.currentDefaultImageIndex = (this.currentDefaultImageIndex + 1) % this.defaultImages.length;
        this.changeBackground(this.defaultImages[this.currentDefaultImageIndex]);
      }, 10000);
    },
    async fetchRandomMovieImage(fetchImageCallback, tmdbApiKey) {
      const imageUrl = await fetchImageCallback(tmdbApiKey);
      if (imageUrl) {
        const img = new Image();
        img.src = imageUrl;
        img.onload = () => this.changeBackground(imageUrl);
      }
    },
    startBackgroundImageRotation(fetchImageCallback, tmdbApiKey) {
      this.fetchRandomMovieImage(fetchImageCallback, tmdbApiKey);
      this.intervalId = setInterval(() => {
        this.fetchRandomMovieImage(fetchImageCallback, tmdbApiKey);
      }, 10000);
    },
    stopBackgroundImageRotation() {
      if (this.intervalId) clearInterval(this.intervalId);
    },
  },
};
