<template>
  <div class="flex flex-col gap-5">
    <PageHeader title="Webhooks" subtitle="Get notified on Discord, Telegram or ntfy, or send signed events to Home Assistant, n8n or any automation.">
      <button type="button" class="ui-btn-primary" @click="openCreate"><i aria-hidden="true" class="fas fa-plus"></i>Add destination</button>
    </PageHeader>

    <div class="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div class="flex min-w-0 flex-col gap-5">
        <SectionCard icon="fas fa-satellite-dish" title="Destinations" description="Each destination receives the events it subscribes to.">
          <template #actions>
            <button type="button" class="ui-btn h-9 px-3 text-[13px]" :disabled="loading" @click="load">
              <i aria-hidden="true" :class="loading ? 'fas fa-spinner fa-spin' : 'fas fa-sync'"></i>Refresh
            </button>
          </template>

          <ul v-if="webhooks.length" class="m-0 flex list-none flex-col gap-2.5 p-0">
            <li v-for="webhook in webhooks" :key="webhook.id" class="flex items-start gap-3 rounded-ctl border border-edge bg-panel-2 p-4">
              <div class="flex min-w-0 flex-1 flex-col gap-2">
                <div class="flex min-w-0 flex-col gap-0.5">
                  <span class="flex items-center gap-2 text-sm font-bold text-ink">{{ webhook.name }}<span class="rounded-md bg-raised px-1.5 py-0.5 text-[11px] font-semibold text-ink-3">{{ formatLabel(webhook.format) }}</span></span>
                  <code class="break-all font-mono text-xs text-ink-3">{{ webhook.url }}</code>
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <span v-for="event in webhook.events" :key="event" class="rounded-full bg-raised px-2 py-0.5 font-mono text-[11px] text-ink-2">{{ event }}</span>
                </div>
              </div>
              <button type="button" class="ui-btn-icon-danger" :aria-label="`Delete ${webhook.name}`" title="Delete destination" @click="remove(webhook)">
                <i aria-hidden="true" class="fas fa-trash-alt"></i>
              </button>
            </li>
          </ul>
          <div v-else class="flex flex-col items-center gap-3 rounded-ctl border border-dashed border-edge-strong px-6 py-10 text-center">
            <i aria-hidden="true" class="fas fa-plug text-2xl text-ink-4"></i>
            <div>
              <p class="m-0 text-sm font-semibold text-ink-2">No destinations yet</p>
              <p class="m-0 mt-1 text-[13px] text-ink-3">Add one to start delivering events.</p>
            </div>
            <button type="button" class="ui-btn" @click="openCreate"><i aria-hidden="true" class="fas fa-plus"></i>Add destination</button>
          </div>
        </SectionCard>

        <SectionCard icon="fas fa-history" title="Recent deliveries" description="Failed deliveries retry automatically; you can also requeue them by hand.">
          <div v-if="deliveries.length" class="-mx-5 overflow-x-auto">
            <table class="w-full border-collapse text-left text-[13px]">
              <thead>
                <tr class="text-[11px] font-bold uppercase tracking-wider text-ink-4">
                  <th class="px-5 py-2 font-bold">Event</th>
                  <th class="px-3 py-2 font-bold">Status</th>
                  <th class="px-3 py-2 font-bold">Retries</th>
                  <th class="px-3 py-2 font-bold">Last error</th>
                  <th class="px-5 py-2"><span class="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="delivery in deliveries" :key="delivery.id" class="border-t border-edge align-top">
                  <td class="px-5 py-3">
                    <span class="block font-mono text-xs text-ink">{{ delivery.event_type }}</span>
                    <span class="mt-0.5 block text-xs text-ink-4">{{ webhookName(delivery) }}<template v-if="delivery.created_at"> · {{ delivery.created_at }}</template></span>
                  </td>
                  <td class="px-3 py-3">
                    <span class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold" :class="statusTone(delivery.status)">
                      <span class="h-1.5 w-1.5 rounded-full bg-current"></span>{{ delivery.status }}
                    </span>
                  </td>
                  <td class="px-3 py-3 text-ink-2">{{ delivery.retry_count }}</td>
                  <td class="max-w-[280px] px-3 py-3 break-words text-ink-3">{{ delivery.last_error || '—' }}</td>
                  <td class="px-5 py-2 text-right">
                    <button v-if="delivery.status === 'failed'" type="button" class="ui-btn h-8 px-3 text-xs" @click="retry(delivery.id)">
                      <i aria-hidden="true" class="fas fa-redo"></i>Retry
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="m-0 text-[13px] text-ink-3">No deliveries yet. They appear here once a subscribed event fires.</p>
        </SectionCard>
      </div>

      <div class="flex min-w-0 flex-col gap-5">
        <SectionCard icon="fas fa-shield-alt" title="Allowed hostnames" description="Restrict delivery to trusted hosts.">
          <form class="flex flex-col gap-3" @submit.prevent="saveAllowlist">
            <label class="sr-only" for="webhook-allowlist">Allowed hostnames</label>
            <textarea id="webhook-allowlist" v-model="allowedHostsText" rows="4" class="ui-input h-auto resize-y py-2.5 font-mono text-[13px]" placeholder="hooks.example.com&#10;automation.example.org"></textarea>
            <p class="m-0 text-xs leading-relaxed text-ink-4">One hostname per line. Empty allows any destination that passes SSRF validation.</p>
            <button type="submit" class="ui-btn self-start" :disabled="savingAllowlist">
              <i aria-hidden="true" :class="savingAllowlist ? 'fas fa-spinner fa-spin' : 'fas fa-save'"></i>Save allowlist
            </button>
          </form>
        </SectionCard>

        <SectionCard icon="fas fa-info-circle" title="How it works">
          <ol class="m-0 flex list-none flex-col gap-3 p-0 text-[13px] leading-relaxed text-ink-3">
            <li v-for="(step, index) in guideSteps" :key="step.title" class="flex gap-3">
              <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-raised text-xs font-bold text-brand-ink">{{ index + 1 }}</span>
              <span><strong class="block text-ink-2">{{ step.title }}</strong>{{ step.text }}</span>
            </li>
          </ol>
          <details class="group mt-4 rounded-ctl border border-edge bg-panel-2">
            <summary class="flex cursor-pointer list-none items-center gap-2 px-3.5 py-2.5 text-[13px] font-semibold text-ink-2 [&::-webkit-details-marker]:hidden">
              <i aria-hidden="true" class="fas fa-chevron-right text-[10px] text-ink-4 transition-transform group-open:rotate-90"></i>Verifying signatures
            </summary>
            <p class="m-0 border-t border-edge px-3.5 py-3 text-xs leading-relaxed text-ink-3">
              Validate <code class="text-ink-2">X-SuggestArr-Signature</code> with HMAC-SHA256 over <code class="text-ink-2">&lt;timestamp&gt;.&lt;raw body&gt;</code>, using your secret and <code class="text-ink-2">X-SuggestArr-Timestamp</code>. Use <code class="text-ink-2">X-SuggestArr-Event-Id</code> to ignore duplicates.
            </p>
          </details>
        </SectionCard>
      </div>
    </div>

    <AppDialog v-if="showCreate" ref="createDialog" width="max-w-3xl" labelledby="webhook-create-title" @close="showCreate = false">
      <form class="flex flex-col gap-5 p-6" @submit.prevent="create">
        <header>
          <h2 id="webhook-create-title" class="m-0 text-lg font-bold text-ink">Add destination</h2>
          <p class="m-0 mt-1 text-[13px] text-ink-3">Send a readable message to a chat app, or a signed JSON payload to your own automation.</p>
        </header>

        <fieldset class="m-0 border-0 p-0">
          <legend class="mb-2 p-0 text-[13px] font-semibold text-ink-2">Send to</legend>
          <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <label v-for="option in formats" :key="option.value" class="flex cursor-pointer items-center gap-2 rounded-ctl border px-3 py-2.5 text-sm font-semibold has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-ink" :class="form.format === option.value ? 'border-brand-ink bg-brand-soft text-brand-ink' : 'border-edge-strong text-ink-2 hover:border-ink-4'">
              <input v-model="form.format" type="radio" name="webhook-format" :value="option.value" class="sr-only" />
              <i aria-hidden="true" :class="option.icon"></i>{{ option.label }}
            </label>
          </div>
        </fieldset>

        <div class="grid gap-4 sm:grid-cols-2">
          <label class="ui-label">Name<input v-model.trim="form.name" class="ui-input" maxlength="100" :placeholder="selectedFormat.label" required /></label>
          <label class="ui-label">{{ selectedFormat.urlLabel }}<input v-model.trim="form.url" type="url" class="ui-input" :placeholder="selectedFormat.placeholder" required />
            <span class="text-xs font-normal text-ink-4">{{ selectedFormat.hint }}</span>
          </label>
          <div v-if="form.format === 'json'" class="ui-label sm:col-span-2">
            <label for="webhook-secret">Signing secret</label>
            <div class="flex gap-2">
              <input id="webhook-secret" v-model="form.secret" :type="showSecret ? 'text' : 'password'" class="ui-input font-mono" minlength="16" autocomplete="off" required />
              <button type="button" class="ui-btn shrink-0" @click="generateSecret"><i aria-hidden="true" class="fas fa-random"></i>Generate</button>
            </div>
            <span class="text-xs font-normal text-ink-4">At least 16 characters. Copy it now: it is not shown again after saving.</span>
          </div>
        </div>

        <fieldset class="m-0 flex flex-col gap-3 border-0 p-0">
          <legend class="mb-2 p-0 text-[13px] font-semibold text-ink-2">Events</legend>
          <div class="grid gap-3 sm:grid-cols-3">
            <div v-for="group in eventGroups" :key="group.label" class="flex flex-col gap-1.5 rounded-ctl border border-edge bg-panel-2 p-3">
              <span class="text-[11px] font-bold uppercase tracking-wider text-ink-4">{{ group.label }}</span>
              <label v-for="event in group.events" :key="event" class="flex cursor-pointer items-center gap-2 font-mono text-xs text-ink-2">
                <input v-model="form.events" type="checkbox" :value="event" class="accent-brand" />{{ event.split('.')[1] }}
              </label>
            </div>
          </div>
        </fieldset>

        <label class="flex cursor-pointer items-start gap-3 rounded-ctl border border-caution/40 bg-caution/10 p-3.5">
          <input v-model="form.allow_private" type="checkbox" class="mt-1 accent-brand" />
          <span class="flex flex-col gap-0.5">
            <span class="text-sm font-semibold text-ink">Allow private network</span>
            <span class="text-xs text-ink-3">Only for trusted local services such as Home Assistant or n8n on your LAN.</span>
          </span>
        </label>

        <footer class="flex justify-end gap-2.5">
          <button type="button" class="ui-btn border-0 bg-transparent" @click="$refs.createDialog.close()">Cancel</button>
          <button type="submit" class="ui-btn-primary" :disabled="creating || !canCreate">
            <i aria-hidden="true" :class="creating ? 'fas fa-spinner fa-spin' : 'fas fa-plus'"></i>Add destination
          </button>
        </footer>
      </form>
    </AppDialog>
  </div>
</template>

<script>
import PageHeader from '@/components/ui/PageHeader.vue';
import SectionCard from '@/components/ui/SectionCard.vue';
import AppDialog from '@/components/ui/AppDialog.vue';
import { confirmDialog } from '@/utils/confirmDialog';
import {
  createWebhook, deleteWebhook, getWebhookDeliveries, getWebhookSettings,
  getWebhooks, retryWebhookDelivery, updateWebhookSettings,
} from '@/api/api';

const EVENT_GROUPS = [
  { label: 'Suggestions', events: ['suggestion.created', 'suggestion.awaiting_approval', 'suggestion.approved', 'suggestion.rejected'] },
  { label: 'Requests', events: ['request.submitted', 'request.failed', 'request.available'] },
  { label: 'Automation', events: ['run.failed', 'job.completed', 'job.skipped'] },
];

const GUIDE_STEPS = [
  { title: 'Prepare the receiver', text: 'An endpoint that accepts JSON POST and returns 2xx quickly.' },
  { title: 'Add the destination', text: 'Its URL, a secret of 16+ characters and only the events you need.' },
  { title: 'Lock it down', text: 'Use the hostname allowlist; allow private networks only for trusted local receivers.' },
  { title: 'Watch deliveries', text: 'Failures retry automatically and can be requeued from the list.' },
];

const STATUS_TONES = {
  delivered: 'bg-good/15 text-good',
  failed: 'bg-bad/15 text-bad',
  queued: 'bg-caution/15 text-caution',
};

const FORMATS = [
  { value: 'discord', label: 'Discord', icon: 'fab fa-discord', urlLabel: 'Discord webhook URL', placeholder: 'https://discord.com/api/webhooks/…', hint: 'Channel settings → Integrations → Webhooks → Copy URL.' },
  { value: 'telegram', label: 'Telegram', icon: 'fab fa-telegram-plane', urlLabel: 'Bot sendMessage URL', placeholder: 'https://api.telegram.org/bot<token>/sendMessage?chat_id=123', hint: 'Your bot token from @BotFather, plus the chat_id to post in.' },
  { value: 'ntfy', label: 'ntfy', icon: 'fas fa-bell', urlLabel: 'Topic URL', placeholder: 'https://ntfy.sh/my-suggestarr', hint: 'The server and topic your phone subscribes to.' },
  { value: 'json', label: 'Webhook', icon: 'fas fa-code', urlLabel: 'Destination URL', placeholder: 'https://hooks.example.com/suggestarr', hint: 'Receives a signed JSON POST; it must answer 2xx quickly.' },
];

const emptyForm = () => ({ format: 'discord', name: '', url: '', secret: '', events: [], allow_private: false });

export default {
  name: 'SettingsWebhooks',
  components: { PageHeader, SectionCard, AppDialog },
  // The dashboard shell passes props this page does not declare.
  inheritAttrs: false,
  data() {
    return {
      loading: false, creating: false, savingAllowlist: false, showCreate: false, showSecret: false,
      webhooks: [], deliveries: [], allowedHostsText: '',
      eventGroups: EVENT_GROUPS, guideSteps: GUIDE_STEPS, formats: FORMATS,
      form: emptyForm(),
    };
  },
  computed: {
    selectedFormat() {
      return FORMATS.find(option => option.value === this.form.format) || FORMATS[3];
    },
    canCreate() {
      const signed = this.form.format !== 'json' || this.form.secret.length >= 16;
      return Boolean(this.form.name && this.form.url && signed && this.form.events.length);
    },
  },
  methods: {
    async load() {
      this.loading = true;
      try {
        const [webhooks, settings, deliveries] = await Promise.all([getWebhooks(), getWebhookSettings(), getWebhookDeliveries()]);
        this.webhooks = webhooks.data.data;
        this.deliveries = deliveries.data.data;
        this.allowedHostsText = (settings.data.data.allowed_hosts || []).join('\n');
      } catch (error) { this.$toast.error(error.response?.data?.error?.message || 'Unable to load webhooks.'); }
      finally { this.loading = false; }
    },
    webhookName(delivery) {
      return this.webhooks.find(hook => hook.id === delivery.webhook_id)?.name || 'Deleted destination';
    },
    formatLabel(format) {
      return (FORMATS.find(option => option.value === (format || 'json')) || FORMATS[3]).label;
    },
    statusTone(status) {
      return STATUS_TONES[status] || 'bg-raised text-ink-3';
    },
    openCreate() {
      this.form = emptyForm();
      this.showSecret = false;
      this.showCreate = true;
    },
    generateSecret() {
      this.form.secret = Array.from(crypto.getRandomValues(new Uint8Array(24)), b => b.toString(16).padStart(2, '0')).join('');
      this.showSecret = true;
    },
    async saveAllowlist() {
      this.savingAllowlist = true;
      try {
        const hosts = this.allowedHostsText.split(/\r?\n/).map(host => host.trim()).filter(Boolean);
        const response = await updateWebhookSettings(hosts);
        this.allowedHostsText = response.data.data.allowed_hosts.join('\n');
        this.$toast.success('Webhook allowlist saved.');
      } catch (error) { this.$toast.error(error.response?.data?.error?.message || 'Unable to save allowlist.'); }
      finally { this.savingAllowlist = false; }
    },
    async create() {
      this.creating = true;
      try {
        // Chat services get a secret generated server-side; only signed JSON sends one.
        await createWebhook(this.form.format === 'json' ? this.form : { ...this.form, secret: undefined });
        this.$refs.createDialog.close();
        this.$toast.success('Webhook added.');
        await this.load();
      } catch (error) { this.$toast.error(error.response?.data?.error?.message || 'Unable to add webhook.'); }
      finally { this.creating = false; }
    },
    async remove(webhook) {
      if (!(await confirmDialog({ title: `Delete webhook “${webhook.name}”?`, confirmLabel: 'Delete', danger: true }))) return;
      try { await deleteWebhook(webhook.id); this.$toast.success('Webhook deleted.'); await this.load(); }
      catch (error) { this.$toast.error(error.response?.data?.error?.message || 'Unable to delete webhook.'); }
    },
    async retry(id) {
      try { await retryWebhookDelivery(id); this.$toast.success('Delivery queued for retry.'); await this.load(); }
      catch (error) { this.$toast.error(error.response?.data?.error?.message || 'Unable to retry delivery.'); }
    },
  },
  mounted() { this.load(); },
};
</script>
