<template>
  <span class="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full ring-1 ring-inset ring-edge" :class="avatar.palette" :title="description" role="img" :aria-label="description">
    <img v-if="avatarUrl" :src="avatarUrl" alt="" class="h-full w-full object-cover" @error="imageFailed" />
    <svg v-else aria-hidden="true" viewBox="0 0 48 48" class="h-full w-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="24" cy="24" r="20" fill="currentColor" stroke="none" opacity="0.06" />
      <g v-if="avatar.subject === 'film'">
        <rect x="12" y="13" width="24" height="24" rx="3" />
        <path d="M18 13v24m12-24v24M18 25h12m-17-6h5m-5 12h5m12-12h5m-5 12h5" />
      </g>
      <g v-else-if="avatar.subject === 'tv'">
        <rect x="10" y="17" width="28" height="21" rx="4" />
        <path d="m18 10 6 7 6-7m-10 31h8" />
        <path d="m21 23 8 5-8 5z" fill="currentColor" stroke="none" />
      </g>
      <g v-else-if="avatar.subject === 'ticket'" transform="rotate(-20 24 24)">
        <path d="M11 16h26v6a4 4 0 0 0 0 8v6H11v-6a4 4 0 0 0 0-8z" />
        <path d="M29 17v3m0 5v2m0 5v3" />
        <path d="m20 21 1.5 3 3.5.5-2.5 2.5.5 3.5-3-1.5-3 1.5.5-3.5-2.5-2.5 3.5-.5z" fill="currentColor" stroke="none" />
      </g>
      <g v-else-if="avatar.subject === 'clapperboard'">
        <path d="M11 22h26v14a2 2 0 0 1-2 2H13a2 2 0 0 1-2-2zm0 0-2-7 25-7 2 7zM16 13l5 6m4-9 5 6" />
        <path d="m21 27 8 4-8 4z" fill="currentColor" stroke="none" />
      </g>
      <g v-else>
        <circle cx="24" cy="24" r="13" />
        <path d="M24 37h13" />
        <g fill="currentColor" stroke="none">
          <circle cx="24" cy="17" r="3" /><circle cx="17" cy="24" r="3" />
          <circle cx="31" cy="24" r="3" /><circle cx="24" cy="31" r="3" />
          <circle cx="24" cy="24" r="1.5" />
        </g>
      </g>
      <path d="m38 8 1 3 3 1-3 1-1 3-1-3-3-1 3-1z" fill="currentColor" stroke="none" opacity="0.7" />
    </svg>
  </span>
</template>

<script>
import { computed, toRef } from 'vue';
import { useUserAvatar } from '@/composables/useUserAvatar';
import { cinemaAvatar } from '@/utils/userAvatar';

const PROVIDERS = { seer: 'Seer', jellyfin: 'Jellyfin', emby: 'Emby', plex: 'Plex' };

export default {
  name: 'UserAvatar',
  props: { user: { type: Object, default: null } },
  setup(props) {
    const { avatarUrl, avatarSource, imageFailed } = useUserAvatar(toRef(props, 'user'));
    return {
      avatarUrl,
      imageFailed,
      avatar: computed(() => cinemaAvatar(props.user)),
      description: computed(() => avatarUrl.value
        ? `${props.user?.username || 'Your'} avatar from ${PROVIDERS[avatarSource.value] || 'linked account'}`
        : `${props.user?.username || 'Your'} cinema avatar`),
    };
  },
};
</script>
