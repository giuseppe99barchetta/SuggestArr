<template>
  <div class="flex flex-col gap-6">
    <PageHeader title="Ratings" subtitle="Rate the titles you watched, or keep some out of your suggestions. High ratings steer suggestions, low ratings are never used as a starting point." />
    <WatchedMediaHistory :current-user="currentUser" />
  </div>
</template>
<script>
import PageHeader from '@/components/ui/PageHeader.vue';
import WatchedMediaHistory from './WatchedMediaHistory.vue';

export default {
  name: 'RatingsPage',
  components: { PageHeader, WatchedMediaHistory },
  // The dashboard passes every page the same props; only currentUser is used here.
  inheritAttrs: false,
  props: { currentUser: { type: Object, default: null } },
};
</script>
