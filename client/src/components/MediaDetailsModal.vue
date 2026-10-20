<template>
  <AppDialog
    :width="playingTrailer ? 'max-w-6xl' : 'max-w-4xl'"
    labelledby="media-details-title"
    @close="$emit('close')"
  >
    <header class="relative isolate overflow-hidden">
      <!-- Without a backdrop the blurred poster stands in for one. -->
      <div aria-hidden="true" class="absolute inset-0 -z-10">
        <Transition
          enter-active-class="transition-opacity duration-700 ease-out motion-reduce:transition-none"
          enter-from-class="opacity-0"
          enter-to-class="opacity-100"
        >
          <div v-if="backgroundImage" v-show="backgroundLoaded" :key="backgroundImage" class="h-full w-full">
            <img
              :src="backgroundImage"
              alt=""
              class="h-full w-full object-cover"
              :class="backdrop ? 'object-top opacity-60' : 'scale-125 opacity-50 blur-3xl saturate-150'"
              @load="backgroundLoaded = true"
            />
          </div>
        </Transition>
        <div v-if="!backgroundImage" class="h-full w-full opacity-50" :style="{ background: placeholderBackground }"></div>
        <div class="absolute inset-0 bg-gradient-to-r from-panel via-panel/85 to-panel/30 max-sm:bg-gradient-to-t max-sm:via-panel/90"></div>
      </div>

      <button
        type="button"
        class="absolute right-3 top-3 z-10 grid h-9 w-9 cursor-pointer place-items-center rounded-full border-0 bg-canvas/60 text-ink-2 backdrop-blur hover:bg-canvas hover:text-ink"
        aria-label="Close details"
        @click="$emit('close')"
      >
        <i aria-hidden="true" class="fas fa-times"></i>
      </button>

      <div v-if="playingTrailer" key="trailer" ref="swap" class="flex flex-col gap-3 p-4 max-sm:p-3">
        <div class="flex min-h-9 items-center gap-3 pr-12">
          <button
            type="button"
            class="inline-flex h-9 shrink-0 cursor-pointer items-center gap-2 rounded-ctl border-0 bg-canvas/60 px-3 text-sm font-semibold text-ink-2 backdrop-blur hover:bg-canvas hover:text-ink"
            @click="toggleTrailer(false)"
          >
            <i aria-hidden="true" class="fas fa-arrow-left text-xs"></i> Details
          </button>
          <h2 id="media-details-title" class="m-0 min-w-0 truncate text-lg font-bold text-ink">{{ item.title }}</h2>
        </div>
        <TrailerPlayer :url="trailerUrl" :title="item.title" class="rounded-ctl shadow-2xl shadow-black/60 ring-1 ring-white/10" />
      </div>
      <div v-else key="details" ref="swap" class="grid grid-cols-[auto_1fr] gap-x-7 gap-y-4 p-7 max-sm:gap-x-4 max-sm:p-4 max-sm:pt-5">
        <img
          v-if="item.poster_path"
          :src="item.poster_path"
          :alt="item.title"
          class="w-44 rounded-ctl shadow-2xl shadow-black/60 ring-1 ring-white/10 sm:row-span-2 max-sm:w-24"
        />
        <div
          v-else
          aria-hidden="true"
          class="flex aspect-[2/3] w-44 items-center justify-center rounded-ctl text-5xl text-white/90 shadow-2xl shadow-black/60 ring-1 ring-white/10 sm:row-span-2 max-sm:w-24 max-sm:text-2xl"
          :style="{ background: placeholderBackground }"
        >
          <i aria-hidden="true" :class="placeholderIcon"></i>
        </div>

        <div class="flex min-w-0 flex-col justify-end gap-2 pr-8 sm:self-end">
          <!-- Always one line: details that arrive later are cut, never wrapped, so the title stays put. -->
          <p class="m-0 flex min-w-0 items-center gap-x-2 overflow-hidden whitespace-nowrap text-[13px] font-semibold text-ink-3 *:shrink-0" :title="genreLabel || null">
            <span v-if="mediaLabel"><i aria-hidden="true" :class="item.media_type === 'tv' ? 'fas fa-tv' : 'fas fa-film'" class="mr-1.5"></i>{{ mediaLabel }}</span>
            <span v-if="year" aria-hidden="true">·</span>
            <span v-if="year">{{ year }}</span>
            <template v-if="runtimeLabel">
              <span aria-hidden="true">·</span>
              <span>{{ runtimeLabel }}</span>
            </template>
            <template v-if="rating">
              <span aria-hidden="true">·</span>
              <span class="text-caution"><i aria-hidden="true" class="fas fa-star mr-1"></i>{{ rating }}</span>
            </template>
            <template v-if="genreLabel">
              <span aria-hidden="true">·</span>
              <span class="!shrink truncate font-medium">{{ genreLabel }}</span>
            </template>
          </p>
          <h2 id="media-details-title" class="m-0 text-3xl font-extrabold leading-tight tracking-tight text-ink max-sm:text-xl">{{ item.title }}</h2>
          <div v-if="$slots.badges || status" class="flex flex-wrap gap-2 text-xs font-semibold *:inline-flex *:items-center *:gap-1.5">
            <slot name="badges" />
            <span v-if="status" class="rounded-md bg-raised px-2 py-1" :class="statusText"><i aria-hidden="true" :class="status.icon"></i> {{ status.label }}</span>
          </div>
        </div>

        <div class="flex min-w-0 flex-col gap-4 sm:self-start max-sm:col-span-2">
          <div>
            <p ref="overview" class="m-0 leading-relaxed text-ink-2" :class="{ 'line-clamp-4': !overviewExpanded }">{{ item.overview || 'No overview available.' }}</p>
            <button
              v-if="overviewClamped || overviewExpanded"
              type="button"
              class="mt-1 cursor-pointer border-0 bg-transparent p-0 text-sm font-semibold text-ink-3 hover:text-ink"
              :aria-expanded="overviewExpanded.toString()"
              @click="overviewExpanded = !overviewExpanded"
            >
              {{ overviewExpanded ? 'Show less' : 'Show more' }}
            </button>
          </div>
          <!-- The trailer slot is reserved while the lookup runs, so nothing moves when it answers. -->
          <div v-if="hasTrailerSlot || $slots.actions || playUrl" class="flex flex-wrap items-center gap-2">
            <slot name="actions" />
            <a
              v-if="playUrl"
              :href="playUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex h-10 items-center gap-2 rounded-ctl bg-brand px-4 text-sm font-bold text-white no-underline hover:text-white hover:brightness-110"
            >
              <i aria-hidden="true" class="fas fa-play text-xs"></i> Watch now
            </a>
            <button
              v-if="trailerState === 'ready'"
              type="button"
              class="inline-flex h-10 cursor-pointer items-center gap-2 rounded-ctl border-0 bg-ink px-4 text-sm font-bold text-canvas hover:bg-ink-2"
              @click="toggleTrailer(true)"
            >
              <i aria-hidden="true" class="fas fa-film text-xs"></i> Watch trailer
            </button>
            <span
              v-else-if="hasTrailerSlot"
              class="inline-flex h-10 cursor-default items-center gap-2 rounded-ctl border border-edge-strong px-4 text-sm font-bold text-ink-4"
              :aria-busy="(trailerState === 'loading').toString()"
            >
              <template v-if="trailerState === 'loading'"><i aria-hidden="true" class="fas fa-spinner fa-spin text-xs"></i> Watch trailer</template>
              <template v-else><i aria-hidden="true" class="fas fa-video-slash text-xs"></i> No trailer</template>
            </span>
            <a
              v-if="seerUrl"
              :href="seerUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex h-10 items-center gap-2 rounded-ctl border border-edge-strong bg-panel-2/80 px-3.5 text-sm font-semibold text-ink-2 no-underline hover:text-ink"
              title="Open in Seer"
            >
              <i aria-hidden="true" class="fas fa-external-link-alt text-xs"></i> Seer
            </a>
          </div>
        </div>
      </div>
    </header>

    <div v-if="!playingTrailer && (item.rationale || hasExtraDetails || hasOrigin || $slots.default)" class="flex flex-col gap-4 border-t border-edge p-7 max-sm:p-4">
      <section v-if="item.rationale" class="rounded-ctl border border-brand-ink/25 bg-brand-soft/40 p-4">
        <h3 class="m-0 mb-1.5 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-brand-ink">
          <i aria-hidden="true" class="fas fa-lightbulb"></i> {{ rationaleTitle }}
        </h3>
        <p class="m-0 whitespace-pre-wrap leading-relaxed text-ink-2">{{ item.rationale }}</p>
        <p v-if="hasOrigin" class="m-0 mt-3 border-t border-brand-ink/15 pt-2.5 text-xs text-ink-3"><template v-if="item.source_title">From <strong class="font-semibold text-ink-2">{{ item.source_title }}</strong></template><template v-if="item.source_title && requestedFor"> · </template><template v-if="requestedFor">for <strong class="font-semibold text-ink-2">{{ requestedFor }}</strong></template></p>
      </section>
      <p v-else-if="hasOrigin" class="m-0 text-sm text-ink-3"><template v-if="item.source_title">From <strong class="font-semibold text-ink-2">{{ item.source_title }}</strong></template><template v-if="item.source_title && requestedFor"> · </template><template v-if="requestedFor">for <strong class="font-semibold text-ink-2">{{ requestedFor }}</strong></template></p>

      <dl v-if="hasExtraDetails" class="m-0 grid grid-cols-[max-content_1fr] items-center gap-x-6 gap-y-2.5 text-sm">
        <template v-if="details.cast.length">
          <dt class="text-ink-4">Cast</dt>
          <!-- One line with a few faces; the rest on request. -->
          <dd v-if="!castExpanded" class="m-0 flex min-w-0 items-center gap-2.5">
            <span class="flex shrink-0 -space-x-2">
              <template v-for="person in details.cast.slice(0, 4)" :key="person.name">
                <img v-if="person.profile_path" :src="`https://image.tmdb.org/t/p/w45${person.profile_path}`" alt="" loading="lazy" class="h-7 w-7 rounded-full object-cover ring-2 ring-panel" />
                <span v-else aria-hidden="true" class="grid h-7 w-7 place-items-center rounded-full bg-raised text-[11px] font-bold text-ink-3 ring-2 ring-panel">{{ person.name.charAt(0) }}</span>
              </template>
            </span>
            <span class="min-w-0 truncate text-ink-2">{{ castPreview }}</span>
            <button v-if="details.cast.length > 2" type="button" class="shrink-0 cursor-pointer rounded-full border-0 bg-raised px-2 py-0.5 text-xs font-semibold text-ink-3 hover:text-ink" :aria-label="`Show all ${details.cast.length} cast members`" @click="castExpanded = true">+{{ details.cast.length - 2 }}</button>
          </dd>
          <dd v-else class="m-0 flex flex-wrap gap-x-4 gap-y-1.5">
            <span v-for="person in details.cast" :key="person.name" class="inline-flex items-center gap-1.5 text-ink-2" :title="person.character ? `${person.name} as ${person.character}` : person.name">
              <img v-if="person.profile_path" :src="`https://image.tmdb.org/t/p/w45${person.profile_path}`" alt="" loading="lazy" class="h-6 w-6 rounded-full object-cover" />
              <span v-else aria-hidden="true" class="grid h-6 w-6 place-items-center rounded-full bg-raised text-[10px] font-bold text-ink-3">{{ initials(person.name) }}</span>
              {{ person.name }}
            </span>
          </dd>
        </template>
        <template v-if="streamLogos.length">
          <dt class="text-ink-4">Stream on<template v-if="details.region"> ({{ details.region }})</template></dt>
          <dd class="m-0 flex flex-wrap items-center gap-1.5">
            <img v-for="provider in streamLogos" :key="provider.name" :src="`https://image.tmdb.org/t/p/w45${provider.logo_path}`" :alt="provider.name" :title="provider.name" loading="lazy" class="h-7 w-7 rounded-md" />
          </dd>
        </template>
      </dl>

      <div v-if="$slots.default" :class="{ 'border-t border-edge pt-4': item.rationale || hasExtraDetails || hasOrigin }">
        <slot />
      </div>
    </div>
  </AppDialog>
</template>

<script>
import axios from 'axios';
import AppDialog from '@/components/ui/AppDialog.vue';
import TrailerPlayer from '@/components/TrailerPlayer.vue';
import { loadTitleDetails, trailerTarget } from '@/utils/trailer.js';
import { mediaStatus } from '@/utils/mediaStatus.js';
import { loadSeerWebUrl, seerTitleUrl } from '@/utils/seerLink.js';

/**
 * Detail view for one title (request, suggestion or AI result).
 * Extra chips go in `badges`, primary buttons beside the trailer link in `actions`,
 * extra sections (feedback, related titles) in the default slot at the bottom.
 */
export default {
  name: 'MediaDetailsModal',
  components: { AppDialog, TrailerPlayer },
  props: {
    item: { type: Object, required: true },
    rationaleTitle: { type: String, default: 'Why it was suggested' },
    placeholderIcon: { type: String, default: 'fas fa-image' },
    placeholderBackground: { type: String, default: 'var(--color-raised)' },
  },
  emits: ['close'],
  data() {
    return {
      overviewExpanded: false,
      overviewClamped: false,
      backgroundLoaded: false,
      trailerUrl: null,
      trailerState: 'loading', // 'loading' | 'ready' | 'none'
      playingTrailer: false,
      trailerAnimating: false,
      detailsBox: null, // the details' size, measured when the trailer opens, to shrink back to
      details: null,
      castExpanded: false,
      seerBase: null,
    };
  },
  computed: {
    // Known before the lookup: only a single movie or TV show can have a trailer.
    hasTrailerSlot() {
      return trailerTarget(this.item) !== null;
    },
    backdrop() {
      const path = this.item.backdrop_path;
      if (!path) return '';
      return path.startsWith('/') ? `https://image.tmdb.org/t/p/w1280${path}` : path;
    },
    backgroundImage() {
      return this.backdrop || this.item.poster_path || '';
    },
    rating() {
      const value = Number(this.item.rating);
      return this.item.rating !== null && this.item.rating !== '' && Number.isFinite(value) ? value.toFixed(1) : '';
    },
    mediaLabel() {
      return { movie: 'Movie', tv: 'TV show' }[this.item.media_type] || '';
    },
    year() {
      const year = String(this.item.release_date || '').slice(0, 4);
      return /^\d{4}$/.test(year) ? year : '';
    },
    // Seer's link to the title on Jellyfin, Emby or Plex; only http(s) links reach the client.
    playUrl() {
      return ['available', 'partial'].includes(this.item.availability) ? this.item.media_url || '' : '';
    },
    hasExtraDetails() {
      return Boolean(this.details && (this.details.cast.length || this.streamLogos.length));
    },
    streamLogos() {
      return (this.details?.providers || []).filter(provider => provider.logo_path);
    },
    castPreview() {
      return this.details.cast.slice(0, 2).map(person => person.name).join(', ');
    },
    genreLabel() {
      return this.details?.genres.join(', ') || '';
    },
    seerUrl() {
      return seerTitleUrl(this.seerBase, this.item);
    },
    // Only sent requests carry `availability`; suggestions and AI results have no Seer progress.
    status() {
      return 'availability' in this.item ? mediaStatus(this.item.watched_at, this.item.availability) : null;
    },
    statusText() {
      return { watched: 'text-good', available: 'text-brand-ink', partial: 'text-brand-ink' }[this.status?.key] || 'text-ink-2';
    },
    requestedFor() {
      return this.item.user_name || this.item.user_id || '';
    },
    hasOrigin() {
      return Boolean(this.item.source_title || this.requestedFor);
    },
    runtimeLabel() {
      const minutes = Number(this.details?.runtime) || 0;
      if (!minutes) return '';
      const text = minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes}m`;
      return this.item.media_type === 'tv' ? `${text} per episode` : text;
    },
  },
  watch: {
    backgroundImage() {
      this.backgroundLoaded = false;
    },
    // Related titles open in the same modal, so a new item starts collapsed again.
    item: {
      immediate: true,
      handler() {
        this.overviewExpanded = false;
        this.castExpanded = false;
        this.$nextTick(this.measureOverview);
        this.loadDetails();
      },
    },
  },
  async mounted() {
    this.seerBase = await loadSeerWebUrl(axios);
  },
  methods: {
    async loadDetails() {
      const shown = this.item;
      this.trailerUrl = null;
      this.trailerState = 'loading';
      this.playingTrailer = false;
      this.details = null;
      if (!this.hasTrailerSlot) return;
      const details = await loadTitleDetails(axios, shown);
      // Another title may be open by the time the answer arrives.
      if (this.item !== shown) return;
      this.details = details && {
        ...details,
        genres: details.genres || [],
        cast: details.cast || [],
        providers: details.providers || [],
      };
      this.trailerUrl = details?.trailer_url || null;
      this.trailerState = this.trailerUrl ? 'ready' : 'none';
    },

    /**
     * Swap details and trailer, resizing the dialog in one motion (FLIP).
     * Opening grows the box while the trailer fades in; closing plays the same motion backwards.
     */
    async toggleTrailer(on) {
      if (this.trailerAnimating) return;
      const dialog = this.$el;
      const box = (rect) => ({ width: `${rect.width}px`, height: `${rect.height}px` });
      const timing = { duration: 450, easing: 'cubic-bezier(0.2, 0, 0, 1)' };
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        this.playingTrailer = on;
        return;
      }

      if (on) {
        const first = dialog.getBoundingClientRect();
        this.detailsBox = first;
        this.playingTrailer = true;
        await this.$nextTick();
        dialog.animate([box(first), box(dialog.getBoundingClientRect())], timing);
        // Faded here, not with <Transition>: that keeps the old view in the DOM a frame longer and skews the measure.
        this.$refs.swap?.animate([{ opacity: 0 }, { opacity: 1 }], timing);
        return;
      }

      // Backwards: the live trailer shrinks and fades out, the details return once the box has their size.
      // shortcut: reuses the size measured on opening, so a window resized meanwhile ends in a small jump.
      this.trailerAnimating = true;
      try {
        // Quicker than opening: the details are what the reader is waiting for.
        const resize = dialog.animate([box(dialog.getBoundingClientRect()), box(this.detailsBox)], { ...timing, duration: 200, fill: 'forwards' });
        this.$refs.swap?.animate([{ opacity: 1 }, { opacity: 0 }], { ...timing, duration: 120, fill: 'forwards' });
        await resize.finished;
        this.playingTrailer = false;
        await this.$nextTick();
        resize.cancel();
        this.$refs.swap?.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 100, easing: 'ease-out' });
      } finally {
        this.trailerAnimating = false;
      }
    },

    initials(name) {
      return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
    },

    /** "Show more" only when the four-line clamp actually hides text. */
    measureOverview() {
      const el = this.$refs.overview;
      this.overviewClamped = Boolean(el) && el.scrollHeight > el.clientHeight + 1;
    },
  },
};
</script>
