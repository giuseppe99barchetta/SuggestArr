<template>
  <AppDialog width="max-w-4xl" labelledby="media-details-title" @close="$emit('close')">
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

    <div v-if="item.rationale || hasExtraDetails || origin.length || $slots.default" class="flex flex-col gap-5 border-t border-edge p-7 max-sm:p-4">
      <section v-if="item.rationale" class="rounded-ctl border border-brand-ink/25 bg-brand-soft/40 p-4">
        <h3 class="m-0 mb-1.5 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-brand-ink">
          <i aria-hidden="true" class="fas fa-lightbulb"></i> {{ rationaleTitle }}
        </h3>
        <p class="m-0 whitespace-pre-wrap leading-relaxed text-ink-2">{{ item.rationale }}</p>
      </section>

      <!-- One label/value list, so title facts and where the suggestion came from read the same way. -->
      <dl v-if="hasExtraDetails || origin.length" class="m-0 grid grid-cols-[max-content_1fr] items-baseline gap-x-6 gap-y-2.5 text-sm">
        <template v-if="details?.genres.length || runtimeLabel">
          <dt class="text-ink-4">Genre</dt>
          <dd class="m-0 text-ink-2">{{ details.genres.join(', ') }}<span v-if="runtimeLabel" class="text-ink-4"><template v-if="details.genres.length"> · </template>{{ runtimeLabel }}</span></dd>
        </template>
        <template v-if="details?.cast.length">
          <dt class="text-ink-4">Cast</dt>
          <dd class="m-0 flex flex-wrap gap-x-4 gap-y-1.5">
            <span v-for="person in details.cast" :key="person.name" class="inline-flex items-center gap-1.5 text-ink-2" :title="person.character ? `${person.name} as ${person.character}` : person.name">
              <img v-if="person.profile_path" :src="`https://image.tmdb.org/t/p/w45${person.profile_path}`" alt="" loading="lazy" class="h-6 w-6 rounded-full object-cover" />
              <span v-else aria-hidden="true" class="grid h-6 w-6 place-items-center rounded-full bg-raised text-[10px] font-bold text-ink-3">{{ initials(person.name) }}</span>
              {{ person.name }}
            </span>
          </dd>
        </template>
        <template v-if="details?.providers.length">
          <dt class="text-ink-4">Stream on<template v-if="details.region"> ({{ details.region }})</template></dt>
          <dd class="m-0 flex flex-wrap gap-x-4 gap-y-1.5">
            <span v-for="provider in details.providers" :key="provider.name" class="inline-flex items-center gap-1.5 text-ink-2">
              <img v-if="provider.logo_path" :src="`https://image.tmdb.org/t/p/w45${provider.logo_path}`" alt="" loading="lazy" class="h-6 w-6 rounded-md" />{{ provider.name }}
            </span>
          </dd>
        </template>
        <template v-for="part in origin" :key="part.label">
          <dt class="text-ink-4">{{ part.label }}</dt>
          <dd class="m-0 font-semibold text-ink">{{ part.value }}</dd>
        </template>
      </dl>

      <div v-if="$slots.default" :class="{ 'border-t border-edge pt-5': item.rationale || hasExtraDetails || origin.length }">
        <slot />
      </div>
    </div>
  </AppDialog>
</template>

<script>
import axios from 'axios';
import AppDialog from '@/components/ui/AppDialog.vue';
import { loadTitleDetails, trailerTarget } from '@/utils/trailer.js';

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
      backgroundLoaded: false,
      trailerUrl: null,
      trailerState: 'loading', // 'loading' | 'ready' | 'none'
      details: null,
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
    hasExtraDetails() {
      const d = this.details;
      return Boolean(d && (d.genres.length || d.runtime || d.cast.length || d.providers.length));
    },
    runtimeLabel() {
      const minutes = Number(this.details?.runtime) || 0;
      if (!minutes) return '';
      const text = minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes}m`;
      return this.item.media_type === 'tv' ? `${text} per episode` : text;
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
    backgroundImage() {
      this.backgroundLoaded = false;
    },
    // Related titles open in the same modal, so a new item starts collapsed again.
    item: {
      immediate: true,
      handler() {
        this.overviewExpanded = false;
        this.$nextTick(this.measureOverview);
        this.loadDetails();
      },
    },
  },
  methods: {
    async loadDetails() {
      const shown = this.item;
      this.trailerUrl = null;
      this.trailerState = 'loading';
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
