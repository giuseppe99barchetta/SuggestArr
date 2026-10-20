<template>
  <!-- Image and shade are the card's own background. The shade is 2px taller than the card
       and anchored to the bottom: the 16:9 height is fractional, Chrome rounds the gradient down
       to whole pixels, and the uncovered sliver showed the bright image as a line along the
       bottom edge. Hover zooms by growing the image layer. -->
  <article
    class="group relative isolate aspect-video w-full overflow-hidden rounded-card bg-black bg-no-repeat [background-position:bottom,center] [background-size:100%_calc(100%_+_2px),100%_auto] transition-[background-size] duration-300 hover:[background-size:100%_calc(100%_+_2px),106%_auto] motion-reduce:transition-none"
    :style="{ backgroundImage: layers }"
  >

    <!-- The whole card opens the details; the play button sits above it. -->
    <button type="button" class="absolute inset-0 z-0 cursor-pointer border-0 bg-transparent p-0" :aria-label="`Show details for ${title}`" @click="$emit('open')"></button>

    <span v-if="badge" class="pointer-events-none absolute left-2.5 top-2.5 rounded-md bg-black/55 px-2 py-0.5 text-[11px] font-bold text-white backdrop-blur-sm">{{ badge }}</span>

    <div class="pointer-events-none absolute inset-x-0 bottom-0 flex items-end gap-3 p-3.5">
      <div class="flex min-w-0 flex-1 flex-col gap-1">
        <img v-if="logo && !logoFailed" :src="logo" :alt="title" class="max-h-11 max-w-[70%] self-start object-contain object-left drop-shadow-[0_2px_6px_rgba(0,0,0,0.6)]" @error="logoFailed = true" />
        <h3 v-else class="m-0 line-clamp-2 text-base font-extrabold leading-tight text-white [text-shadow:0_1px_8px_rgba(0,0,0,0.6)]">{{ title }}</h3>
        <span v-if="subtitle" class="truncate text-xs text-white/75">{{ subtitle }}</span>
      </div>
      <a
        v-if="playUrl"
        :href="playUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="pointer-events-auto relative z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-black/40 text-xs text-white no-underline ring-1 ring-white/40 backdrop-blur-sm transition hover:bg-white hover:text-black focus-visible:opacity-100 group-hover:opacity-100 motion-reduce:transition-none [@media(hover:hover)]:opacity-0"
        :aria-label="`Watch ${title} now`"
        title="Watch now"
      >
        <i aria-hidden="true" class="fas fa-play ml-0.5"></i>
      </a>
    </div>
  </article>
</template>

<script>
import { tmdbImage } from '@/utils/tmdbImage.js';

/**
 * Landscape title card (backdrop, title logo, play button) for rows like "Ready to watch".
 * Falls back to a blurred poster when there is no backdrop, and to the title text without a logo.
 */
export default {
  name: 'BackdropCard',
  props: {
    title: { type: String, required: true },
    backdrop: { type: String, default: '' },
    poster: { type: String, default: '' },
    logo: { type: String, default: '' },
    badge: { type: String, default: '' },
    subtitle: { type: String, default: '' },
    playUrl: { type: String, default: '' },
  },
  emits: ['open'],
  data() {
    return { logoFailed: false };
  },
  computed: {
    image() {
      return this.backdrop ? tmdbImage(this.backdrop, 'w780') : tmdbImage(this.poster, 'w342');
    },
    layers() {
      const shade = 'linear-gradient(to top, rgb(0 0 0 / 0.9), rgb(0 0 0 / 0.3) 50%, transparent)';
      return this.image ? `${shade}, url("${encodeURI(this.image)}")` : shade;
    },
  },
};
</script>
