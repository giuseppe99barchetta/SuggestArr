<template>
  <AppDialog title="Support SuggestArr" subtitle="Help the next discovery happen." icon="fas fa-heart" width="max-w-lg" @close="$emit('close')">
    <p class="m-0 text-sm leading-relaxed text-ink-2">I build SuggestArr in my spare time. If it helps you find your next watch, buying me a coffee is a lovely way to keep it growing.</p>

    <div class="mt-5 rounded-card border border-brand-ink/15 bg-brand-soft/20 p-4 sm:p-5">
      <a href="https://ko-fi.com/ciuse99" target="_blank" rel="noopener noreferrer" class="ui-btn-primary h-11 w-full no-underline hover:text-white"><i aria-hidden="true" class="fas fa-heart"></i>Support on Ko-fi<i aria-hidden="true" class="fas fa-arrow-up-right-from-square ml-1 text-[11px] opacity-70"></i></a>
      <p class="m-0 mt-3 flex flex-wrap items-center justify-center gap-x-1.5 text-xs leading-relaxed text-ink-3">Or use <a href="https://buymeacoffee.com/suggestarr" target="_blank" rel="noopener noreferrer" class="inline-flex min-h-8 items-center gap-1.5 rounded-ctl font-semibold text-ink-2 underline decoration-edge-strong underline-offset-4 hover:text-brand-ink"><i aria-hidden="true" class="fas fa-mug-hot text-xs"></i>Buy Me a Coffee</a></p>
    </div>

    <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank" rel="noopener noreferrer" class="group mt-4 flex min-h-14 items-center gap-3 rounded-ctl px-2 py-2 text-ink-2 transition-colors hover:bg-raised hover:text-ink">
      <i aria-hidden="true" class="fab fa-github shrink-0 text-xl text-ink-3"></i>
      <span class="min-w-0 flex-1">
        <span class="block text-[13px] font-semibold">Star SuggestArr on GitHub</span>
        <span class="mt-0.5 block text-xs text-ink-3">A free way to help others discover the project.</span>
      </span>
      <i aria-hidden="true" class="fas fa-arrow-up-right-from-square shrink-0 text-[11px] text-ink-4 group-hover:text-brand-ink"></i>
    </a>

    <div class="mt-5 border-t border-edge pt-3">
      <SupportReminderOptions :saving="saving" @select="save" />
    </div>
    <p v-if="error" role="alert" class="ui-alert-bad mt-4">{{ error }}</p>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import SupportReminderOptions from './SupportReminderOptions.vue';
import { saveRecapPreference } from '@/api/recapApi.js';

export default {
  name: 'SupportDialog',
  components: { AppDialog, SupportReminderOptions },
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
