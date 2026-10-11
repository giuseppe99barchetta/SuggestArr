<template>
  <AppDialog width="max-w-4xl" labelledby="media-details-title" @close="$emit('close')">
    <div class="relative grid gap-6 p-5 sm:grid-cols-[220px_1fr] sm:p-7">
      <button
        type="button"
        class="absolute right-3 top-3 h-9 w-9 cursor-pointer rounded-[8px] border-0 bg-transparent text-ink-3 hover:bg-raised hover:text-ink"
        aria-label="Close details"
        @click="$emit('close')"
      >
        <i aria-hidden="true" class="fas fa-times"></i>
      </button>

      <div class="flex flex-col gap-4">
        <img v-if="item.poster_path" :src="item.poster_path" :alt="item.title" class="mx-auto w-40 rounded-ctl sm:w-full" />
        <div v-else class="mx-auto flex aspect-[2/3] w-40 items-center justify-center rounded-ctl text-4xl text-white/90 sm:w-full" :style="{ background: placeholderBackground }">
          <i aria-hidden="true" :class="placeholderIcon"></i>
        </div>
        <slot name="aside" />
      </div>

      <div class="flex min-w-0 flex-col gap-4">
        <div class="flex flex-col gap-3 pr-8">
          <h2 id="media-details-title" class="m-0 text-2xl font-extrabold tracking-tight">{{ item.title }}</h2>
          <div class="flex flex-wrap gap-2 text-xs font-semibold *:inline-flex *:items-center *:gap-1.5">
            <span v-if="item.media_type" class="rounded-md bg-raised px-2 py-1 text-ink-2"><i aria-hidden="true" :class="item.media_type === 'movie' ? 'fas fa-film' : 'fas fa-tv'"></i> {{ item.media_type === 'movie' ? 'Movie' : 'TV' }}</span>
            <span v-if="rating" class="rounded-md bg-raised px-2 py-1 text-ink-2"><i aria-hidden="true" class="fas fa-star text-caution"></i> {{ rating }}</span>
            <span v-if="item.release_date" class="rounded-md bg-raised px-2 py-1 text-ink-2"><i aria-hidden="true" class="fas fa-calendar"></i> {{ item.release_date }}</span>
            <slot name="badges" />
            <a v-if="trailerUrl" :href="trailerUrl" target="_blank" rel="noopener noreferrer" class="rounded-md bg-bad/15 px-2 py-1 text-bad"><i aria-hidden="true" class="fab fa-youtube"></i> Watch trailer</a>
          </div>
        </div>

        <dl v-if="item.source_title || item.user_name || item.user_id" class="m-0 grid gap-1.5 text-sm">
          <div v-if="item.source_title" class="flex gap-2"><dt class="text-ink-4">Suggested from</dt><dd class="m-0 font-semibold text-ink">{{ item.source_title }}</dd></div>
          <div v-if="item.user_name || item.user_id" class="flex gap-2"><dt class="text-ink-4">Requested for</dt><dd class="m-0 font-semibold text-ink">{{ item.user_name || item.user_id }}</dd></div>
        </dl>

        <slot />

        <section>
          <h3 class="m-0 mb-1.5 text-xs font-bold uppercase tracking-wider text-ink-4">Overview</h3>
          <p class="m-0 leading-relaxed text-ink-2">{{ item.overview || 'No overview available.' }}</p>
        </section>
      </div>
    </div>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';

/**
 * Detail view for one title (request, suggestion or AI result).
 * Extra sections go in the default slot, extra controls under the poster in `aside`.
 */
export default {
  name: 'MediaDetailsModal',
  components: { AppDialog },
  props: {
    item: { type: Object, required: true },
    trailerUrl: { type: String, default: null },
    placeholderIcon: { type: String, default: 'fas fa-image' },
    placeholderBackground: { type: String, default: 'var(--color-raised)' },
  },
  emits: ['close'],
  computed: {
    rating() {
      const value = Number(this.item.rating);
      return this.item.rating !== null && this.item.rating !== '' && Number.isFinite(value) ? value.toFixed(1) : '';
    },
  },
};
</script>
