<template>
  <AppDialog
    :title="`Seen ${item.title || 'it'}`"
    subtitle="Your rating is sent to your Trakt account."
    icon="fas fa-eye"
    width="max-w-md"
    @close="$emit('close')"
  >
    <div class="flex flex-col gap-4">
      <div role="radiogroup" aria-label="Rating out of 10" class="flex justify-between gap-1" @mouseleave="hover = 0">
        <button
          v-for="star in 10"
          :key="star"
          type="button"
          role="radio"
          :aria-checked="rating === star ? 'true' : 'false'"
          :aria-label="`${star} out of 10`"
          class="grid h-9 flex-1 cursor-pointer place-items-center rounded-[8px] border-0 bg-transparent text-lg hover:bg-raised disabled:opacity-50"
          :disabled="busy"
          @mouseenter="hover = star"
          @focus="hover = star"
          @blur="hover = 0"
          @click="rating = rating === star ? null : star"
        ><i aria-hidden="true" class="fas fa-star" :class="star <= (hover || rating || 0) ? 'text-caution' : 'text-ink-4'"></i></button>
      </div>
      <p class="m-0 text-center text-sm text-ink-3" aria-live="polite">{{ ratingText }}</p>
      <BaseCheckbox
        v-if="item.media_type === 'tv'"
        v-model="markWatched"
        :disabled="busy"
        label="Mark all episodes as watched"
        description="Leave this off if you have only seen part of it. The show is then only rated."
      />
      <p v-if="localOnly && !rating" class="m-0 text-xs leading-snug text-ink-4">Without stars or the episodes box, this is saved in SuggestArr only and nothing is sent to Trakt.</p>
    </div>
    <template #footer>
      <button type="button" class="ui-btn" :disabled="busy" @click="save(null)">{{ localOnly ? 'Seen it, SuggestArr only' : 'Seen it, no rating' }}</button>
      <button type="button" class="ui-btn-primary" :disabled="busy || !rating" @click="save(rating)">Save rating</button>
    </template>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import { ratedSeenOption } from '@/utils/suggestionFeedback.js';

const VERDICTS = { seen_liked: 'liked it', seen_disliked: 'did not like it', already_seen: 'neutral' };

/**
 * Star picker shown for "Seen it" when the rating is also written to Trakt.
 *
 * Emits `save` with `{ rating, markWatched }` (rating is null for "no rating") and
 * `close` when dismissed. Mount it with v-if, like AppDialog.
 */
export default {
  name: 'SeenRatingDialog',
  components: { AppDialog, BaseCheckbox },
  props: {
    item: { type: Object, required: true },
    busy: { type: Boolean, default: false },
  },
  emits: ['save', 'close'],
  data() {
    // A show added to Trakt history has every aired episode marked watched, which is
    // wrong for a series seen only in part, so for TV that is an explicit choice.
    return { rating: null, hover: 0, markWatched: this.item.media_type !== 'tv' };
  },
  computed: {
    // A show saved with no stars and no episodes has nothing to send to Trakt.
    localOnly() {
      return this.item.media_type === 'tv' && !this.markWatched;
    },
    ratingText() {
      const shown = this.hover || this.rating;
      if (!shown) return 'Pick 1 to 10 stars, or save without a rating.';
      return `${shown}/10 - counts as ${VERDICTS[ratedSeenOption(shown).feedback]} for suggestions`;
    },
  },
  methods: {
    save(rating) {
      this.$emit('save', { rating, markWatched: this.markWatched });
    },
  },
};
</script>
