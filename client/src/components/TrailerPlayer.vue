<template>
  <div class="aspect-video w-full overflow-hidden bg-black">
    <iframe
      :src="embedUrl"
      :title="title ? `${title} trailer` : 'Trailer'"
      class="h-full w-full border-0"
      allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
      allowfullscreen
      referrerpolicy="strict-origin-when-cross-origin"
    ></iframe>
  </div>
</template>

<script>
import { trailerEmbedUrl } from '@/utils/trailer.js';

/** Plays a YouTube trailer in place; unmounting it (v-if) stops playback. */
export default {
  name: 'TrailerPlayer',
  props: {
    url: { type: String, required: true },
    title: { type: String, default: '' },
  },
  computed: {
    embedUrl() {
      return trailerEmbedUrl(this.url);
    },
  },
};
</script>
