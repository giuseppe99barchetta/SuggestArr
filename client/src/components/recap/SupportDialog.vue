<template>
  <AppDialog title="Support SuggestArr" subtitle="Help the next discovery happen." icon="fas fa-heart" @close="$emit('close')">
    <p class="m-0 text-sm leading-relaxed text-ink-2">I build SuggestArr in my spare time. If it makes discovering your next watch easier, a coffee helps support its continued development. Sharing your recap or leaving a GitHub star helps too.</p>
    <div class="mt-5 flex flex-col gap-3">
      <a href="https://ko-fi.com/ciuse99" target="_blank" rel="noopener noreferrer" class="ui-btn-primary justify-center no-underline"><i aria-hidden="true" class="fas fa-heart"></i>Support on Ko-fi</a>
      <a href="https://buymeacoffee.com/suggestarr" target="_blank" rel="noopener noreferrer" class="ui-btn justify-center no-underline"><i aria-hidden="true" class="fas fa-mug-hot"></i>Buy Me a Coffee</a>
      <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank" rel="noopener noreferrer" class="ui-btn justify-center no-underline"><i aria-hidden="true" class="fab fa-github"></i>Star SuggestArr on GitHub</a>
    </div>
    <p v-if="error" role="alert" class="ui-alert-bad mt-4">{{ error }}</p>
    <template #footer>
      <button type="button" class="ui-btn" :disabled="saving" @click="save('supported')">I already supported</button>
      <button type="button" class="ui-btn" :disabled="saving" @click="save('disable')">Don't show these reminders</button>
    </template>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import { saveRecapPreference } from '@/api/recapApi.js';

export default {
  name: 'SupportDialog',
  components: { AppDialog },
  emits: ['close', 'preferences-changed'],
  data: () => ({ saving: false, error: '' }),
  methods: {
    async save(action) {
      this.saving = true;
      this.error = '';
      try {
        const preferences = await saveRecapPreference(action);
        this.$emit('preferences-changed', preferences);
        this.$toast.success('Support reminder preferences saved.');
        this.$emit('close');
      } catch { this.error = 'Unable to save your preferences. Please try again.'; }
      finally { this.saving = false; }
    },
  },
};
</script>
