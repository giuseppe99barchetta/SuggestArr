<template>
    <div class="flex flex-col gap-5">
        <p class="m-0 flex items-start gap-2 text-[0.85rem] leading-normal text-ink-4">
            <i aria-hidden="true" class="fas fa-info-circle mt-0.5 shrink-0 opacity-70"></i>
            <span>All settings below are optional and use sensible defaults. You can fine-tune everything anytime from <strong>Settings → Jobs</strong>.</span>
        </p>

        <section class="rounded-card border border-edge bg-white/5 p-6">
            <h4 class="m-0 mb-5 border-b border-edge pb-3 text-[1.1rem] font-semibold text-ink">Rating & Popularity Filters</h4>

            <div class="grid gap-4 md:grid-cols-2">
                <label v-for="field in ratingFields" :key="field.key" class="ui-label" :for="field.key">
                    {{ field.label }}
                    <input type="number" :value="config[field.key]"
                        @input="field.validate($event.target.value)"
                        class="ui-input"
                        :id="field.key" :placeholder="field.placeholder" min="0" :max="field.max">
                    <span v-if="errors[field.key]" class="text-[0.8125rem] font-medium text-bad">{{ errors[field.key] }}</span>
                </label>
            </div>
            <p class="m-0 mt-2 flex items-center gap-2 text-[0.8rem] text-ink-4">
                <i aria-hidden="true" class="fas fa-info-circle"></i>
                Based on TMDB community ratings. Leave empty to include all content regardless of rating.
            </p>
        </section>

        <section class="rounded-card border border-edge bg-white/5 p-6">
            <h4 class="m-0 mb-5 border-b border-edge pb-3 text-[1.1rem] font-semibold text-ink">Content Exclusion Options</h4>

            <div class="flex flex-col gap-3">
                <button
                    v-for="toggle in toggles"
                    :key="toggle.key"
                    type="button"
                    role="switch"
                    :aria-checked="config[toggle.key] ? 'true' : 'false'"
                    class="flex cursor-pointer items-center gap-4 rounded-ctl border border-edge bg-white/2 p-4 text-left transition hover:border-brand hover:bg-white/4"
                    @click="handleUpdate(toggle.key, !config[toggle.key])"
                >
                    <span class="flex flex-1 flex-col gap-1">
                        <span class="text-[0.9rem] font-semibold text-ink">{{ toggle.title }}</span>
                        <span class="text-[0.8125rem] text-ink-4">{{ toggle.hint }}</span>
                    </span>
                    <span class="relative inline-block h-[22px] w-10 shrink-0 rounded-full transition-colors" :class="config[toggle.key] ? 'bg-brand' : 'bg-edge-strong'"><span class="absolute top-[3px] h-4 w-4 rounded-full bg-white transition-all" :class="config[toggle.key] ? 'left-[21px]' : 'left-[3px]'"></span></span>
                </button>
            </div>
        </section>

        <p class="m-0 flex items-start gap-2 rounded-lg border border-white/7 bg-white/3 px-4 py-3 text-[0.85rem] leading-normal text-ink-4">
            <i aria-hidden="true" class="fas fa-sliders-h mt-0.5 shrink-0 opacity-70"></i>
            <span>More advanced filters (genres, language, streaming services, runtime) are available in <strong>Settings → Jobs</strong> after setup.</span>
        </p>
    </div>
</template>


<script>
export default {
    props: {
        config: { type: Object, required: true },
    },
    emits: ['update-config', 'validation-changed'],
    data() {
        return {
            ratingFields: [
                { key: 'FILTER_TMDB_THRESHOLD', label: 'Minimum Rating (0–100)', placeholder: 'Leave empty to allow all ratings', max: 100, validate: this.validateThreshold },
                { key: 'FILTER_TMDB_MIN_VOTES', label: 'Minimum Votes', placeholder: 'Leave empty to allow all', validate: this.validateMinVotes },
            ],
            toggles: [
                { key: 'FILTER_INCLUDE_NO_RATING', title: 'Include content with missing ratings', hint: 'Show recommendations even without rating information' },
                { key: 'EXCLUDE_DOWNLOADED', title: 'Exclude downloaded content', hint: 'Skip suggesting items already in your library' },
                { key: 'EXCLUDE_REQUESTED', title: 'Exclude requested content', hint: "Avoid recommending shows or movies you've already requested" },
            ],
            errors: {
                FILTER_TMDB_THRESHOLD: '',
                FILTER_TMDB_MIN_VOTES: '',
            }
        };
    },
    computed: {
        hasErrors() {
            return Object.values(this.errors).some(error => error !== '');
        }
    },
    watch: {
        hasErrors(val) {
            this.$emit('validation-changed', !val);
        },
    },
    methods: {
        handleUpdate(key, value) {
            this.$emit('update-config', key, value);
        },
        validateThreshold(value) {
            if (value < 0 || value > 100) {
                this.errors.FILTER_TMDB_THRESHOLD = "Rating must be between 0 and 100.";
            } else {
                this.errors.FILTER_TMDB_THRESHOLD = "";
                this.handleUpdate('FILTER_TMDB_THRESHOLD', value);
            }
        },
        validateMinVotes(value) {
            if (value < 0) {
                this.errors.FILTER_TMDB_MIN_VOTES = "Minimum votes cannot be negative.";
            } else {
                this.errors.FILTER_TMDB_MIN_VOTES = "";
                this.handleUpdate('FILTER_TMDB_MIN_VOTES', value);
            }
        },
    },
};
</script>
