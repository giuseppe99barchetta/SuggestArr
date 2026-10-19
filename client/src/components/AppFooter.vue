<template>
  <footer class="mt-12 flex flex-col items-center px-4 py-8 max-md:mt-8 max-md:py-6 max-[480px]:p-4">
    <div class="flex flex-wrap items-center justify-center gap-6 max-md:gap-4 max-[480px]:gap-3">
      <a
        v-for="link in links"
        :key="link.href"
        :href="link.href"
        target="_blank"
        rel="noopener noreferrer"
        :aria-label="link.label"
        :title="link.label"
        class="flex h-12 w-12 items-center justify-center rounded-ctl border border-edge bg-panel-2 text-xl text-ink-4 transition hover:-translate-y-0.5 hover:border-edge-strong hover:bg-raised hover:text-ink max-md:h-11 max-md:w-11 max-md:text-lg max-[480px]:h-10 max-[480px]:w-10 max-[480px]:text-base"
      >
        <i aria-hidden="true" :class="link.icon"></i>
      </a>
      <button
        type="button"
        class="group flex h-12 cursor-pointer items-center gap-2 rounded-ctl border border-edge bg-panel-2 px-4 text-sm font-semibold text-ink-3 transition hover:-translate-y-0.5 hover:border-brand-ink/40 hover:bg-raised hover:text-ink max-md:h-11 max-[480px]:h-10 max-[480px]:px-3"
        @click="showSupport = true"
      >
        <i aria-hidden="true" class="fas fa-heart text-brand-ink/70 transition-colors group-hover:text-brand-ink"></i>Support SuggestArr
      </button>
    </div>
    <SupportDialog v-if="showSupport" :can-manage-reminders="isAdmin" @close="showSupport = false" @preferences-changed="preferencesChanged" />
  </footer>
</template>

<script>
import SupportDialog from '@/components/recap/SupportDialog.vue';

export default {
  name: 'AppFooter',
  components: { SupportDialog },
  props: { isAdmin: { type: Boolean, default: false } },
  data() {
    return {
      showSupport: false,
      links: [
        { href: 'https://github.com/giuseppe99barchetta/SuggestArr', label: 'GitHub', icon: 'fab fa-github' },
        { href: 'https://hub.docker.com/repository/docker/ciuse99/suggestarr/', label: 'Docker Hub', icon: 'fab fa-docker' },
        { href: 'https://discord.gg/JXwFd3PnXY', label: 'Discord', icon: 'fab fa-discord' },
      ],
    };
  },
  methods: {
    preferencesChanged() { window.dispatchEvent(new Event('suggestarr-recap-preferences')); },
  },
};
</script>
