<template>
  <AppDialog title="Support SuggestArr" subtitle="Help the next discovery happen." icon="fas fa-heart" width="max-w-lg" @close="$emit('close')">
    <p class="m-0 text-sm leading-relaxed text-ink-2">I build SuggestArr in my spare time. If it helps you find your next watch, buying me a coffee is a lovely way to keep it growing.</p>

    <div class="mt-5 grid gap-2.5 sm:grid-cols-2">
      <a
        v-for="provider in providers"
        :key="provider.href"
        :href="provider.href"
        :aria-label="provider.label"
        target="_blank"
        rel="noopener noreferrer"
        class="group flex min-h-16 items-center gap-3 rounded-card border p-3.5 no-underline transition-colors"
        :class="provider.primary ? 'border-brand-ink/30 bg-brand-soft/30 hover:border-brand-ink/60 hover:bg-brand-soft/50' : 'border-edge bg-panel-2 hover:border-edge-strong hover:bg-raised'"
      >
        <span aria-hidden="true" class="grid h-10 w-10 shrink-0 place-items-center rounded-ctl" :class="provider.primary ? 'bg-brand text-white' : 'bg-raised text-ink-2'"><i :class="provider.icon"></i></span>
        <span class="min-w-0 flex-1">
          <span class="block text-sm font-semibold text-ink">{{ provider.name }}</span>
          <span class="mt-0.5 block text-xs text-ink-3">{{ provider.caption }}</span>
        </span>
        <i aria-hidden="true" class="fas fa-arrow-up-right-from-square shrink-0 text-[11px] text-ink-4 group-hover:text-brand-ink"></i>
      </a>
    </div>

    <p class="m-0 mb-1.5 mt-6 text-[11px] font-semibold uppercase tracking-widest text-ink-4">Other ways to help</p>
    <div class="divide-y divide-edge overflow-hidden rounded-card border border-edge">
      <a
        v-for="way in otherWays"
        :key="way.href"
        :href="way.href"
        target="_blank"
        rel="noopener noreferrer"
        class="group flex min-h-14 items-center gap-3 px-3.5 py-2.5 text-ink-2 no-underline transition-colors hover:bg-raised hover:text-ink"
      >
        <i aria-hidden="true" class="w-5 shrink-0 text-center text-lg text-ink-3" :class="way.icon"></i>
        <span class="min-w-0 flex-1">
          <span class="block text-[13px] font-semibold">{{ way.title }}</span>
          <span class="mt-0.5 block text-xs text-ink-3">{{ way.caption }}</span>
        </span>
        <i aria-hidden="true" class="fas fa-arrow-up-right-from-square shrink-0 text-[11px] text-ink-4 group-hover:text-brand-ink"></i>
      </a>
    </div>

    <div v-if="canManageReminders" class="mt-5 border-t border-edge pt-3">
      <SupportReminderOptions :saving="saving" @select="save" />
    </div>
    <p v-if="error" role="alert" class="ui-alert-bad mt-4">{{ error }}</p>
  </AppDialog>
</template>

<script>
import AppDialog from '@/components/ui/AppDialog.vue';
import SupportReminderOptions from './SupportReminderOptions.vue';
import { saveRecapPreference } from '@/api/recapApi.js';

/**
 * Single entry point for supporting the project: donation providers, free ways to help
 * and, for admins, the support reminder preferences.
 */
export default {
  name: 'SupportDialog',
  components: { AppDialog, SupportReminderOptions },
  props: {
    // Reminder preferences are admin-only on the API, so other users only see the links.
    canManageReminders: { type: Boolean, default: true },
  },
  emits: ['close', 'preferences-changed'],
  data: () => ({
    saving: false,
    error: '',
    providers: [
      { href: 'https://ko-fi.com/ciuse99', label: 'Support on Ko-fi', name: 'Ko-fi', caption: 'One-time or monthly', icon: 'fas fa-heart', primary: true },
      { href: 'https://buymeacoffee.com/suggestarr', label: 'Buy Me a Coffee', name: 'Buy Me a Coffee', caption: 'A quick one-time coffee', icon: 'fas fa-mug-hot' },
    ],
    otherWays: [
      { href: 'https://github.com/giuseppe99barchetta/SuggestArr', title: 'Star SuggestArr on GitHub', caption: 'A free way to help others discover the project.', icon: 'fab fa-github' },
      { href: 'https://discord.gg/JXwFd3PnXY', title: 'Join the Discord', caption: 'Share feedback, ideas and bug reports.', icon: 'fab fa-discord' },
    ],
  }),
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
