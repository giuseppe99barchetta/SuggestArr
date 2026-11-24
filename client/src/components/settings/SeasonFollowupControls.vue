<template>
  <div class="mt-4 border-t border-edge pt-4">
    <button type="button" class="ui-btn" :disabled="disabled || !enabled || running" @click="run">
      <i aria-hidden="true" class="fas fa-sync-alt" :class="{ 'fa-spin': running }"></i>
      {{ running ? 'Checking…' : 'Run now' }}
    </button>
    <p v-if="disabled" class="m-0 mt-2 text-xs text-ink-4">Save your changes before running the follow-up.</p>
    <p v-if="summary" role="status" class="m-0 mt-3 text-sm text-ink-3">{{ summary }}</p>
    <p v-if="runError" role="alert" class="ui-alert-bad mt-3">{{ runError }}</p>
  </div>
</template>

<script>
import { runSeasonFollowup } from '@/api/api.js';

export default {
  name: 'SeasonFollowupControls',
  props: { enabled: Boolean, disabled: Boolean },
  data() {
    return { runError: '', running: false, summary: '' };
  },
  methods: {
    async run() {
      if (this.running || this.disabled || !this.enabled) return;
      this.running = true;
      this.runError = '';
      this.summary = '';
      try {
        const { data } = await runSeasonFollowup();
        const r = data.result;
        if (r.status !== 'ok') {
          this.summary = r.status === 'disabled' ? 'Follow-up is disabled.' : 'Media server or request backend is not configured.';
        } else {
          this.summary = `Shows checked: ${r.shows}. Seasons requested: ${r.requested}. Skipped: ${r.skipped}. Errors: ${r.errors}.${r.truncated ? ' Watch history was truncated; older plays may be missed.' : ''}`;
          if (r.errors) this.$toast.error('Follow-up finished with errors. See the server log.');
          else this.$toast.success('Season follow-up complete.');
        }
      } catch (error) {
        this.runError = error.response?.status === 409 ? 'A follow-up run is already in progress.' : (error.response?.data?.message || 'Season follow-up failed.');
        this.$toast.error(this.runError);
      } finally {
        this.running = false;
      }
    },
  },
};
</script>
