<template>
  <footer class="mt-12 flex flex-col items-center px-4 py-8 max-md:mt-8 max-md:py-6 max-[480px]:p-4">
    <div class="flex flex-wrap justify-center gap-6 max-md:gap-4 max-[480px]:gap-3">
      <a
        v-for="link in links"
        :key="link.href"
        :href="link.href"
        target="_blank"
        rel="noopener noreferrer"
        :aria-label="link.label"
        :title="link.title"
        class="flex h-12 w-12 items-center justify-center rounded-ctl border border-edge bg-panel-2 text-xl text-ink-4 transition hover:-translate-y-0.5 hover:border-edge-strong hover:bg-raised hover:text-ink max-md:h-11 max-md:w-11 max-md:text-lg max-[480px]:h-10 max-[480px]:w-10 max-[480px]:text-base"
      >
        <i aria-hidden="true" :class="link.icon"></i>
      </a>
    </div>
  </footer>
</template>

<script>
export default {
  name: 'AppFooter',
  data() {
    return {
      links: [
        { href: 'https://github.com/giuseppe99barchetta/SuggestArr', label: 'GitHub', icon: 'fab fa-github' },
        { href: 'https://hub.docker.com/repository/docker/ciuse99/suggestarr/', label: 'Docker', icon: 'fab fa-docker' },
        { href: 'https://discord.gg/JXwFd3PnXY', label: 'Discord', icon: 'fab fa-discord' },
        { href: 'https://ko-fi.com/ciuse99', label: 'Support SuggestArr on Ko-fi', title: 'Support SuggestArr on Ko-fi', icon: 'fas fa-heart' },
        { href: 'https://buymeacoffee.com/suggestarr', label: 'Support SuggestArr on Buy Me a Coffee', title: 'Support SuggestArr on Buy Me a Coffee', icon: 'fas fa-mug-hot' },
      ],
    };
  },
};
</script>
