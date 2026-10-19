// Vite transforms these imports exactly as it does application imports, sharing
// the same Vue and axios instances (including the configured subpath).
import { createApp, h } from 'vue';
import axios from 'axios';
import Journey from '@/components/recap/JourneyPanel.vue';
import Preferences from '@/components/recap/RecapPreferences.vue';
import Footer from '@/components/AppFooter.vue';
import '@/assets/main.css';

export function mountPreview({ role, profile, subpath }) {
  axios.defaults.baseURL = subpath ? '/suggestarr' : '';
  const user = { id: 1, role };
  const app = createApp({ render: () => h('main', {}, [
    profile ? h(Preferences) : h(Journey, { currentUser: user }),
    h(Footer, { isAdmin: user.role === 'admin' }),
  ]) });
  app.component('router-link', { props: ['to'], render() { return h('a', { href: '/profile' }, this.$slots.default?.()); } });
  app.config.globalProperties.$toast = { error() {}, success() {} };
  app.mount('#preview');
}
