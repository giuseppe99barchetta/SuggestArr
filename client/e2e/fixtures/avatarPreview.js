import { createApp, h, ref } from 'vue';
import axios from 'axios';
import UserAvatar from '@/components/ui/UserAvatar.vue';
import UserProfile from '@/components/settings/UserProfile.vue';
import '@/assets/main.css';

export function mountAvatarPreview({ subpath = false } = {}) {
  axios.defaults.baseURL = subpath ? '/suggestarr' : '';
  axios.defaults.headers.common.Authorization = 'Bearer test-only';
  const user = ref({ id: 3, username: 'Cinema fan', role: 'user' });
  const app = createApp({ render: () => h('main', { class: 'mx-auto max-w-5xl p-4' }, [
    h('div', { class: 'mb-4 flex items-center gap-3' }, [
      h(UserAvatar, { user: user.value, class: 'h-8 w-8 text-[32px]' }),
      h('button', { onClick: () => { user.value = { id: 4, username: 'TV fan', role: 'user' }; } }, 'Switch account'),
    ]),
    h(UserProfile, { currentUser: user.value, config: { SELECTED_SERVICE: 'jellyfin' } }),
  ]) });
  app.config.globalProperties.$toast = { error() {}, success() {} };
  app.mount('#preview');
}
