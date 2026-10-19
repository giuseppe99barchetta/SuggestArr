<template>
  <div class="flex flex-col gap-8">
    <header class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="m-0 text-3xl font-extrabold tracking-tight text-ink">{{ greeting }}<template v-if="currentUser?.username">, {{ currentUser.username }}</template></h1>
        <p class="m-0 mt-1.5 text-[15px] text-ink-3">{{ summary }}</p>
      </div>
      <div class="flex flex-wrap gap-2.5">
        <router-link :to="tabLink('jobs')" class="inline-flex h-[42px] items-center gap-2 rounded-ctl border border-edge-strong bg-panel-2 px-4 text-sm font-semibold text-ink no-underline hover:text-white">
          <i aria-hidden="true" class="fas fa-clock"></i>Manage jobs
        </router-link>
        <router-link :to="tabLink('requests')" class="inline-flex h-[42px] items-center rounded-ctl bg-brand px-[18px] text-sm font-bold text-white no-underline hover:text-white">
          {{ pendingTotal ? 'Review suggestions' : 'View requests' }}
        </router-link>
      </div>
    </header>

    <div class="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
      <div v-for="tile in statTiles" :key="tile.label" class="flex flex-col gap-1.5 rounded-card border border-edge bg-panel px-4 py-4 sm:px-5 sm:py-[18px]">
        <span class="text-[13px] font-medium text-ink-3">{{ tile.label }}</span>
        <span class="text-[28px] font-extrabold tracking-tight text-ink">{{ tile.value }}</span>
        <span class="text-xs text-ink-4">{{ tile.hint }}</span>
      </div>
    </div>

    <section v-if="pendingRequests.length" class="flex flex-col gap-4">
      <div class="flex items-baseline justify-between gap-3">
        <h2 class="m-0 text-[19px] font-bold text-ink">Waiting for your approval</h2>
        <router-link :to="tabLink('requests')" class="text-sm font-semibold no-underline">See all {{ pendingTotal }} →</router-link>
      </div>
      <div class="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-4">
        <MediaCard
          v-for="request in pendingRequests.slice(0, 12)"
          :key="request._key"
          :title="request.title"
          :poster="request.poster_path || ''"
          :badge="request.media_type === 'movie' ? 'Movie' : 'TV'"
          @open="openDetails(request)"
        >
          <template #actions>
            <template v-if="confirmRejectId === request.id">
              <button type="button" class="h-9 flex-1 cursor-pointer rounded-[8px] border-0 bg-bad text-[13px] font-bold text-on-bad disabled:opacity-50" :disabled="actionLoadingId === request.id" @click="decidePending('reject', request.id)">Reject</button>
              <button type="button" class="h-9 w-9 cursor-pointer rounded-[8px] border-0 bg-transparent text-ink-4 hover:text-ink" aria-label="Cancel rejection" @click="confirmRejectId = null"><i aria-hidden="true" class="fas fa-undo"></i></button>
            </template>
            <template v-else-if="seenMenuId === request.id">
              <button v-for="option in seenOptions" :key="option.value" type="button" class="h-9 flex-1 cursor-pointer rounded-[8px] border border-edge-strong bg-panel-2 text-ink-2 hover:text-ink disabled:opacity-50" :disabled="actionLoadingId === request.id" :aria-label="option.label" :title="option.label" @click="markSeen(request, option)"><i aria-hidden="true" :class="option.icon"></i></button>
              <button type="button" class="h-9 w-9 cursor-pointer rounded-[8px] border-0 bg-transparent text-ink-4 hover:text-ink" aria-label="Cancel" @click="seenMenuId = null"><i aria-hidden="true" class="fas fa-undo"></i></button>
            </template>
            <template v-else>
              <button type="button" class="h-9 flex-1 cursor-pointer rounded-[8px] border-0 bg-brand text-[13px] font-bold text-white disabled:opacity-50" :disabled="actionLoadingId === request.id" aria-label="Approve request" @click="requestApprove(request)">Approve</button>
              <button type="button" class="h-9 w-9 cursor-pointer rounded-[8px] border border-edge-strong bg-transparent text-ink-2 hover:text-ink disabled:opacity-50" :disabled="actionLoadingId === request.id" aria-label="Already seen it" title="Already seen it" @click="seenMenuId = request.id"><i aria-hidden="true" class="fas fa-eye"></i></button>
              <button type="button" class="h-9 w-9 cursor-pointer rounded-[8px] border border-edge-strong bg-transparent text-ink-2 hover:text-bad disabled:opacity-50" :disabled="actionLoadingId === request.id" aria-label="Reject request" title="Reject" @click="confirmRejectId = request.id"><i aria-hidden="true" class="fas fa-times"></i></button>
            </template>
          </template>
          <span v-if="request.source_title" class="line-clamp-2 text-xs leading-snug text-ink-3">Because you watched {{ request.source_title }}</span>
          <span v-if="request.user_name || request.user_id" class="truncate text-xs text-ink-4" :title="`For ${request.user_name || request.user_id}`">For {{ request.user_name || request.user_id }}</span>
        </MediaCard>
      </div>
    </section>

    <section class="flex flex-col gap-4">
      <div class="flex items-baseline justify-between gap-3">
        <h2 class="m-0 text-[19px] font-bold text-ink">Recently requested</h2>
        <router-link v-if="recentRequests.length" :to="tabLink('requests')" class="text-sm font-semibold no-underline">See all {{ stats.total || '' }} →</router-link>
      </div>
      <div v-if="loading" class="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-4">
        <div v-for="i in 6" :key="i" class="aspect-[2/3] animate-pulse rounded-card bg-panel"></div>
      </div>
      <p v-else-if="!recentRequests.length" class="m-0 rounded-card border border-dashed border-edge-strong px-6 py-10 text-center text-sm text-ink-3">
        Nothing requested yet. Requests appear here once a job has run.
      </p>
      <div v-else class="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-4">
        <MediaCard
          v-for="request in recentRequests.slice(0, 6)"
          :key="request._key"
          :title="request.title"
          :poster="request.poster_path || ''"
          :badge="request.media_type === 'movie' ? 'Movie' : 'TV'"
          @open="openDetails(request)"
        >
          <span class="truncate text-xs text-ink-4" :title="request.user_name || request.user_id ? `for ${request.user_name || request.user_id}` : null">{{ formatDate(request.requested_at) }}<template v-if="request.user_name || request.user_id"> · for {{ request.user_name || request.user_id }}</template></span>
        </MediaCard>
      </div>
    </section>

    <div v-if="activity.length || upcomingJobs.length" class="grid grid-cols-[repeat(auto-fit,minmax(min(340px,100%),1fr))] gap-5">
      <section v-if="activity.length" class="flex flex-col rounded-card border border-edge bg-panel px-5 py-5 sm:px-6">
        <h2 class="m-0 mb-2.5 text-[17px] font-bold text-ink">Recent activity</h2>
        <div v-for="run in activity" :key="run.id" class="flex gap-3.5 border-t border-edge py-3">
          <span class="mt-[5px] h-2.5 w-2.5 shrink-0 rounded-full" :class="run.dot"></span>
          <div class="flex min-w-0 flex-1 flex-col gap-0.5">
            <span class="text-sm font-semibold text-ink">{{ run.title }}</span>
            <span class="text-[13px] text-ink-3">{{ run.detail }}</span>
          </div>
          <span class="whitespace-nowrap text-xs text-ink-4">{{ run.when }}</span>
        </div>
      </section>
      <section v-if="upcomingJobs.length" class="flex flex-col rounded-card border border-edge bg-panel px-5 py-5 sm:px-6">
        <div class="mb-2.5 flex items-baseline justify-between">
          <h2 class="m-0 text-[17px] font-bold text-ink">Upcoming jobs</h2>
          <router-link :to="tabLink('jobs')" class="text-[13px] font-semibold no-underline">Manage →</router-link>
        </div>
        <div v-for="job in upcomingJobs" :key="job.id" class="flex items-center gap-3.5 border-t border-edge py-3">
          <span class="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-ctl bg-raised text-ink-2"><i aria-hidden="true" :class="job.icon"></i></span>
          <div class="flex min-w-0 flex-1 flex-col gap-0.5">
            <span class="truncate text-sm font-semibold text-ink">{{ job.name }}</span>
            <span class="text-[13px] text-ink-3">{{ job.schedule }}</span>
          </div>
          <span class="whitespace-nowrap text-[13px] font-semibold" :class="job.enabled ? 'text-ink' : 'text-caution'">{{ job.next }}</span>
        </div>
      </section>
    </div>

    <AppDialog v-if="approveItem" width="max-w-xl" labelledby="approve-title" @close="approveItem = null">
      <div class="flex flex-col gap-4 p-6">
        <div>
          <h3 id="approve-title" class="m-0 text-lg font-bold text-ink"><i aria-hidden="true" class="fas fa-paper-plane mr-2"></i>Send to Seer</h3>
          <p class="m-0 mt-1 text-sm text-ink-3">Send {{ approveItem.title || 'this item' }} to Seer?</p>
        </div>
        <ApprovalProfileChoice ref="profileChoice" :servers="servers" :media-types="[approveItem.media_type]" />
        <div class="mt-2 flex justify-end gap-2">
          <button type="button" class="h-10 cursor-pointer rounded-ctl border border-edge-strong bg-panel-2 px-4 text-sm font-semibold text-ink" @click="approveItem = null">Cancel</button>
          <button type="button" class="h-10 cursor-pointer rounded-ctl border-0 bg-brand px-4 text-sm font-bold text-white disabled:opacity-50" :disabled="actionLoadingId === approveItem.id" @click="confirmApprove">Send</button>
        </div>
      </div>
    </AppDialog>

    <MediaDetailsModal v-if="selectedRequest" :item="selectedRequest" @close="selectedRequest = null" />
  </div>
</template>

<script>
import axios from 'axios';
import { formatDate, timeFromNow } from '@/utils/dateUtils.js';
import { formatJobSchedule, getJobTypeIcon } from '@/utils/jobTypeVisuals.js';
import AppDialog from '@/components/ui/AppDialog.vue';
import MediaCard from '@/components/ui/MediaCard.vue';
import MediaDetailsModal from '@/components/MediaDetailsModal.vue';
import ApprovalProfileChoice from '@/components/ApprovalProfileChoice.vue';
import { approvalNeedsDialog, loadSeerServers } from '@/utils/requestProfiles.js';
import { SEEN_OPTIONS, saveSeenFeedback } from '@/utils/suggestionFeedback.js';
import { approvalEnabled } from '@/utils/requestApproval.js';

/**
 * Dashboard home: request stats, the approval queue, recent requests and job activity.
 */
export default {
  name: 'HomePage',
  components: { AppDialog, MediaCard, MediaDetailsModal, ApprovalProfileChoice },
  // The dashboard shell passes settings props to every tab; only currentUser is used here.
  inheritAttrs: false,
  props: {
    currentUser: { type: Object, default: null },
  },
  data() {
    return {
      stats: { total: 0, today: 0, this_week: 0, this_month: 0 },
      recentRequests: [],
      pendingRequests: [],
      pendingTotal: 0,
      jobs: [],
      history: [],
      confirmRejectId: null,
      seenMenuId: null,
      seenOptions: SEEN_OPTIONS,
      approveItem: null,
      servers: null,
      actionLoadingId: null,
      approvalEnabled: false,
      selectedRequest: null,
      loading: false,
    };
  },
  computed: {
    greeting() {
      const hour = new Date().getHours();
      if (hour < 12) return 'Good morning';
      if (hour < 18) return 'Good afternoon';
      return 'Good evening';
    },
    nextJob() {
      return this.upcomingJobs.find(job => job.enabled && job.nextRun);
    },
    summary() {
      const parts = [];
      if (this.pendingTotal) parts.push(`${this.pendingTotal} ${this.pendingTotal === 1 ? 'suggestion is' : 'suggestions are'} waiting for you.`);
      else parts.push('Nothing is waiting for your approval.');
      if (this.nextJob) parts.push(`Next run ${this.nextJob.next}.`);
      return parts.join(' ');
    },
    statTiles() {
      const tiles = [
        { label: 'Requested today', value: this.stats.today || 0, hint: 'Sent to Seer since midnight' },
        { label: 'This week', value: this.stats.this_week || 0, hint: 'Requests in the last 7 days' },
        { label: 'This month', value: this.stats.this_month || 0, hint: 'Requests this month' },
        { label: 'All time', value: this.stats.total || 0, hint: 'Every request SuggestArr made' },
      ];
      if (this.approvalEnabled) {
        tiles.splice(0, 1, { label: 'Awaiting approval', value: this.pendingTotal, hint: this.pendingTotal ? 'Review them below' : 'All caught up' });
      }
      return tiles;
    },
    upcomingJobs() {
      return this.jobs
        .map(job => ({
          id: job.id,
          name: job.name,
          enabled: job.enabled,
          icon: getJobTypeIcon(job.job_type),
          schedule: formatJobSchedule(job),
          nextRun: job.enabled ? job.next_run : null,
          next: job.enabled ? (timeFromNow(job.next_run) || 'Not scheduled') : 'Paused',
        }))
        .sort((a, b) => (a.nextRun ? new Date(a.nextRun) : Infinity) - (b.nextRun ? new Date(b.nextRun) : Infinity))
        .slice(0, 4);
    },
    activity() {
      return this.history.slice(0, 5).map(run => {
        const failed = run.status === 'failed';
        const running = run.status === 'running';
        return {
          id: run.id,
          title: `${run.job_name || 'Job'} ${failed ? 'failed' : running ? 'is running' : 'finished'}`,
          detail: failed
            ? (run.error_message || 'See the logs for details.')
            : `${run.results_count ?? 0} found · ${run.requested_count ?? 0} requested`,
          when: timeFromNow(run.finished_at || run.started_at),
          dot: failed ? 'bg-bad' : running ? 'bg-notice' : 'bg-good',
        };
      });
    },
  },
  async mounted() {
    this.loadStats();
    this.loadRecentRequests();
    this.loadApprovalState();
    this.loadHistory();
    this.servers = await loadSeerServers(axios);
  },
  methods: {
    formatDate,

    tabLink(tab) {
      return { name: 'DashboardTab', params: { tab } };
    },

    async loadStats() {
      try {
        const response = await axios.get('/api/automation/requests/stats');
        this.stats = response.data;
      } catch (error) {
        console.error('Error loading request stats:', error);
      }
    },

    async loadHistory() {
      try {
        const response = await axios.get('/api/jobs/history', { params: { limit: 5 } });
        this.history = response.data.history || [];
      } catch {
        // Job history is admin-only; other users simply don't see the activity card.
        this.history = [];
      }
    },

    async loadRecentRequests() {
      this.loading = true;
      try {
        const response = await axios.get('/api/automation/requests', {
          params: {
            page: 1,
            sort_by: 'date-desc'
          }
        });

        const allRequests = response.data.data.flatMap(source =>
          source.requests.map(req => ({
            ...req,
            source_title: source.source_title
          }))
        );

        allRequests.sort((a, b) => new Date(b.requested_at) - new Date(a.requested_at));

        this.recentRequests = allRequests.slice(0, 20).map(request => ({ ...request, _key: `sent-${request.request_id}` }));
      } catch (error) {
        console.error('Error loading recent requests:', error);
      } finally {
        this.loading = false;
      }
    },

    async loadPendingRequests() {
      try {
        const { data } = await axios.get('/api/automation/requests/workflow', { params: { status: 'awaiting_approval', page: 1, per_page: 20 } });
        this.pendingRequests = (data.items || []).map(item => ({ ...item, _pending: true, _key: `pending-${item.id}`, requested_at: item.created_at, source_title: item.name, poster_path: item.poster_path ? `https://image.tmdb.org/t/p/w500${item.poster_path}` : null }));
        this.pendingTotal = data.total || 0;
      } catch (error) {
        console.error('Error loading pending requests:', error);
      }
    },

    async loadApprovalState() {
      try {
        const { data } = await axios.get('/api/jobs');
        this.jobs = data.jobs || [];
        await this.loadPendingRequests();
        this.approvalEnabled = this.pendingTotal > 0 || approvalEnabled(data);
      } catch (error) {
        console.error('Error loading approval jobs:', error);
      }
    },

    // The same choice as on the Requests page: approving asks first, unless
    // the server list has loaded and is empty.
    requestApprove(request) {
      if (approvalNeedsDialog(this.servers)) { this.approveItem = request; return; }
      this.decidePending('approve', request.id);
    },

    async confirmApprove() {
      const profile = this.$refs.profileChoice?.payload() || null;
      const ok = await this.decidePending('approve', this.approveItem.id, profile);
      if (ok) this.approveItem = null;
    },

    // Record that the user has already watched a suggestion, then take it out of the
    // queue. The feedback is what stops it coming back; the reject only clears the card.
    // The title and year travel with the rating so the next recommendation prompt can
    // name what the user liked or disliked instead of only suppressing an id.
    async markSeen(request, option) {
      this.actionLoadingId = request.id;
      try {
        await saveSeenFeedback(axios, request.id, option, request);
      } catch (error) {
        this.$toast.open({ message: error.response?.data?.message || 'Could not save feedback', type: 'error' });
        this.actionLoadingId = null;
        return;
      } finally {
        this.seenMenuId = null;
      }
      await this.decidePending('reject', request.id);
    },

    async decidePending(action, id, profile = null) {
      this.actionLoadingId = id;
      try {
        await axios.post(`/api/automation/requests/workflow/${action}`, { ids: [id], ...(profile ? { profile } : {}) });
        this.confirmRejectId = null;
        await this.loadPendingRequests();
        this.$toast.open({ message: action === 'approve' ? 'Request queued for Seer' : 'Request rejected', type: 'success' });
        return true;
      } catch (error) {
        // A rejected profile comes back as 400 with a reason — show it instead
        // of leaving the dialog as if nothing had happened.
        this.$toast.open({ message: error.response?.data?.message || 'Could not update request', type: 'error' });
        return false;
      } finally {
        this.actionLoadingId = null;
      }
    },

    openDetails(request) {
      this.selectedRequest = request;
    }
  }
};
</script>
