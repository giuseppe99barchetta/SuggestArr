import { createApp, h, ref } from 'vue';
import YearRecapStories from '@/components/recap/YearRecapStories.vue';
import JourneyPanel from '@/components/recap/JourneyPanel.vue';
import '@/assets/main.css';
import axios from 'axios';

export function setApiBase(base) { axios.defaults.baseURL = base; }

export function mountYearPreview({ admin = true, journey = false, mode = 'demo' } = {}) {
  const open = ref(true);
  const app = createApp({ render: () => journey
    ? h(JourneyPanel, { currentUser: { id: 1, role: admin ? 'admin' : 'user' } })
    : open.value ? h(YearRecapStories, { isAdmin: admin, initialMode: mode, onClose: () => { open.value = false; } }) : h('p', 'Preview closed') });
  app.component('router-link', { props: ['to'], render() { return h('a', { href: '/profile' }, this.$slots.default?.()); } });
  app.config.globalProperties.$toast = { success() {}, error() {} };
  app.mount('#preview');
}
