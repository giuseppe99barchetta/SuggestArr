<template>
  <AppDialog width="max-w-3xl" labelledby="media-details-title" @close="$emit('close')">
    <header class="relative isolate overflow-hidden">
      <!-- Without a backdrop the blurred poster stands in for one. -->
      <div aria-hidden="true" class="absolute inset-0 -z-10">
        <img v-if="backdrop" :src="backdrop" alt="" class="h-full w-full object-cover object-top opacity-60" />
        <img v-else-if="item.poster_path" :src="item.poster_path" alt="" class="h-full w-full scale-125 object-cover opacity-50 blur-3xl saturate-150" />
        <div v-else class="h-full w-full opacity-50" :style="{ background: placeholderBackground }"></div>
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

      <div class="grid grid-cols-[auto_1fr] gap-x-7 gap-y-4 p-7 max-sm:gap-x-4 max-sm:p-4 max-sm:pt-5">
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
          <p class="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] font-semibold text-ink-3">
            <span v-if="mediaLabel"><i aria-hidden="true" :class="item.media_type === 'tv' ? 'fas fa-tv' : 'fas fa-film'" class="mr-1.5"></i>{{ mediaLabel }}</span>
            <span v-if="year" aria-hidden="true">·</span>
            <span v-if="year">{{ year }}</span>
            <template v-if="rating">
              <span aria-hidden="true">·</span>
              <span class="text-caution"><i aria-hidden="true" class="fas fa-star mr-1"></i>{{ rating }}</span>
            </template>
          </p>
          <h2 id="media-details-title" class="m-0 text-3xl font-extrabold leading-tight tracking-tight text-ink max-sm:text-xl">{{ item.title }}</h2>
          <div v-if="$slots.badges" class="flex flex-wrap gap-2 text-xs font-semibold *:inline-flex *:items-center *:gap-1.5">
            <slot name="badges" />
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
          <div v-if="hasTrailerSlot || $slots.actions" class="flex flex-wrap items-center gap-2">
            <slot name="actions" />
            <a
              v-if="trailerState === 'ready'"
              :href="trailerUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex h-10 items-center gap-2 rounded-ctl bg-ink px-4 text-sm font-bold text-canvas no-underline hover:bg-ink-2"
            >
              <i aria-hidden="true" class="fas fa-play text-xs"></i> Watch trailer
            </a>
            <span
              v-else-if="hasTrailerSlot"
              class="inline-flex h-10 cursor-default items-center gap-2 rounded-ctl border border-edge-strong px-4 text-sm font-bold text-ink-4"
              :aria-busy="(trailerState === 'loading').toString()"
            >
              <template v-if="trailerState === 'loading'"><i aria-hidden="true" class="fas fa-spinner fa-spin text-xs"></i> Watch trailer</template>
              <template v-else><i aria-hidden="true" class="fas fa-video-slash text-xs"></i> No trailer</template>
            </span>
          </div>
        </div>
      </div>
    </header>

    <div v-if="item.rationale || origin.length || $slots.default" class="flex flex-col gap-5 border-t border-edge p-7 max-sm:p-4">
      <section v-if="item.rationale" class="rounded-ctl border border-brand-ink/25 bg-brand-soft/40 p-4">
        <h3 class="m-0 mb-1.5 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-brand-ink">
          <i aria-hidden="true" class="fas fa-lightbulb"></i> {{ rationaleTitle }}
        </h3>
        <p class="m-0 whitespace-pre-wrap leading-relaxed text-ink-2">{{ item.rationale }}</p>
      </section>

      <p v-if="origin.length" class="m-0 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-4">
        <span v-for="part in origin" :key="part.label">{{ part.label }} <strong class="font-semibold text-ink">{{ part.value }}</strong></span>
      </p>

      <slot />
    </div>
  </AppDialog>
</template>

<script>
import axios from 'axios';
import AppDialog from '@/components/ui/AppDialog.vue';
import { loadTrailerUrl, trailerTarget } from '@/utils/trailer.js';

/**
 * Detail view for one title (request, suggestion or AI result).
 * Extra chips go in `badges`, primary buttons beside the trailer link in `actions`,
 * extra sections (feedback, related titles) in the default slot at the bottom.
 */
export default {
  name: 'MediaDetailsModal',
  components: { AppDialog },
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
      trailerUrl: null,
      trailerState: 'loading', // 'loading' | 'ready' | 'none'
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
    origin() {
      const { source_title: source, user_name: userName, user_id: userId } = this.item;
      return [
        { label: 'Suggested from', value: source },
        { label: 'Requested for', value: userName || userId },
      ].filter((part) => part.value);
    },
  },
  watch: {
    // Related titles open in the same modal, so a new item starts collapsed again.
    item: {
      immediate: true,
      handler() {
        this.overviewExpanded = false;
        this.$nextTick(this.measureOverview);
        this.loadTrailer();
      },
    },
  },
  methods: {
    async loadTrailer() {
      const shown = this.item;
      this.trailerUrl = null;
      this.trailerState = 'loading';
      if (!this.hasTrailerSlot) return;
      const url = await loadTrailerUrl(axios, shown);
      // Another title may be open by the time the answer arrives.
      if (this.item !== shown) return;
      this.trailerUrl = url;
      this.trailerState = url ? 'ready' : 'none';
    },

    /** "Show more" only when the four-line clamp actually hides text. */
    measureOverview() {
      const el = this.$refs.overview;
      this.overviewClamped = Boolean(el) && el.scrollHeight > el.clientHeight + 1;
    },
  },
};
</script>
