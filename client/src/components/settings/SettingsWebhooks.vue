<template>
  <section class="settings-group webhook-settings">
    <button
      class="webhook-settings__toggle"
      type="button"
      :aria-expanded="expanded.toString()"
      aria-controls="webhook-settings-content"
      @click="expanded = !expanded"
    >
      <span class="webhook-settings__heading">
        <span class="webhook-settings__icon"><i class="fas fa-link"></i></span>
        <span>
          <span class="webhook-settings__title">Outbound Webhooks</span>
          <span class="section-description">Signed event delivery for automations and external integrations.</span>
        </span>
      </span>
      <span class="webhook-settings__meta">
        <span v-if="webhooks.length" class="count-badge">{{ webhooks.length }} configured</span>
        <i class="fas fa-chevron-right webhook-settings__chevron" :class="{ expanded }"></i>
      </span>
    </button>
    <Transition name="webhook-collapse">
      <div id="webhook-settings-content" v-show="expanded" class="webhook-settings__collapse">
        <div class="webhook-settings__collapse-inner">
          <div class="webhook-settings__content">
            <section class="webhook-guide">
              <button
                class="webhook-guide__toggle"
                type="button"
                :aria-expanded="helpExpanded.toString()"
                aria-controls="webhook-guide-content"
                @click="helpExpanded = !helpExpanded"
              >
                <span class="webhook-guide__heading">
                  <i class="fas fa-info-circle"></i>
                  <span>
                    <strong>What are outbound webhooks?</strong>
                    <small>Learn when to use them and how to connect an automation.</small>
                  </span>
                </span>
                <i class="fas fa-chevron-right webhook-guide__chevron" :class="{ expanded: helpExpanded }"></i>
              </button>
              <Transition name="webhook-collapse">
                <div id="webhook-guide-content" v-show="helpExpanded" class="webhook-guide__collapse">
                  <div class="webhook-guide__collapse-inner">
                    <div class="webhook-guide__body">
                      <p>SuggestArr sends a signed HTTP POST when a selected event occurs. Use it to trigger n8n, Home Assistant, notification flows, or your own service without polling SuggestArr.</p>

                      <ol class="webhook-guide__steps">
                        <li><strong>Prepare the receiver</strong><span>Create an endpoint that accepts JSON POST requests and returns a 2xx response quickly.</span></li>
                        <li><strong>Add the destination</strong><span>Enter its URL, create a secret of at least 16 characters, and select only the events you need.</span></li>
                        <li><strong>Secure the connection</strong><span>Use the hostname allowlist when possible. Enable private-network access only for a trusted local receiver.</span></li>
                        <li><strong>Monitor delivery</strong><span>Check the status below. Failed deliveries retry automatically and can also be requeued manually.</span></li>
                      </ol>

                      <div class="webhook-guide__events">
                        <span><strong>Suggestions</strong><small>Created, awaiting approval, approved, rejected</small></span>
                        <span><strong>Requests</strong><small>Submitted or failed</small></span>
                        <span><strong>Automation</strong><small>Run failed, job completed or skipped</small></span>
                      </div>

                      <div class="webhook-guide__signature">
                        <i class="fas fa-shield-alt"></i>
                        <span><strong>Verify every request</strong><small>Validate <code>X-SuggestArr-Signature</code> with HMAC-SHA256 over <code>&lt;timestamp&gt;.&lt;raw body&gt;</code>, using your secret and <code>X-SuggestArr-Timestamp</code>. Use <code>X-SuggestArr-Event-Id</code> to ignore duplicates.</small></span>
                      </div>
                    </div>
                  </div>
                </div>
              </Transition>
            </section>

            <div class="webhook-settings__grid">
        <section class="webhook-panel">
          <div class="webhook-panel__header">
            <span class="webhook-panel__icon"><i class="fas fa-shield-alt"></i></span>
            <span><h4>Destination security</h4><small>Restrict delivery to trusted hostnames.</small></span>
          </div>
          <div class="form-group">
            <label for="webhook-allowlist">Allowed hostnames</label>
            <textarea id="webhook-allowlist" v-model="allowedHostsText" class="form-control" rows="5" placeholder="hooks.example.com&#10;automation.example.org"></textarea>
            <small class="form-help">One hostname per line. Leave empty to allow any destination that passes SSRF validation.</small>
          </div>
          <div class="panel-actions">
            <button class="btn btn-outline btn-sm" :disabled="savingAllowlist" @click="saveAllowlist">
              <i :class="savingAllowlist ? 'fas fa-spinner fa-spin' : 'fas fa-save'"></i>
              Save allowlist
            </button>
          </div>
        </section>

        <section class="webhook-panel webhook-panel--create">
          <div class="webhook-panel__header">
            <span class="webhook-panel__icon"><i class="fas fa-plus"></i></span>
            <span><h4>Add destination</h4><small>Create a signed webhook subscription.</small></span>
          </div>
        <div class="webhook-settings__form-grid">
          <div class="form-group">
            <label for="webhook-name">Name</label>
            <input id="webhook-name" v-model.trim="form.name" class="form-control" maxlength="100" placeholder="n8n">
          </div>
          <div class="form-group">
            <label for="webhook-url">Destination URL</label>
            <input id="webhook-url" v-model.trim="form.url" type="url" class="form-control" placeholder="https://hooks.example.com/suggestarr">
          </div>
          <div class="form-group">
            <label for="webhook-secret">Signing secret</label>
            <input id="webhook-secret" v-model="form.secret" type="password" class="form-control" minlength="16">
            <small class="form-help">At least 16 characters. It is shown only while creating the webhook.</small>
          </div>
        </div>
        <span class="field-label">Events</span>
        <div class="webhook-settings__events tabs-checkboxes">
          <label v-for="event in eventOptions" :key="event" class="event-option" :class="{ selected: form.events.includes(event) }">
            <input v-model="form.events" type="checkbox" :value="event">
            <span>{{ event }}</span>
          </label>
        </div>
        <div class="private-option">
          <BaseCheckbox
            v-model="form.allow_private"
            label="Allow private network"
            description="Enable only for trusted local services such as Home Assistant or n8n."
          />
        </div>
          <div class="panel-actions">
            <button class="btn btn-primary" :disabled="creating" @click="create">
              <i :class="creating ? 'fas fa-spinner fa-spin' : 'fas fa-plus'"></i>
              Add webhook
            </button>
          </div>
        </section>
      </div>

            <section class="webhook-panel webhook-panel--status">
        <div class="webhook-settings__section-header">
          <div class="webhook-panel__header">
            <span class="webhook-panel__icon"><i class="fas fa-satellite-dish"></i></span>
            <span><h4>Destinations & delivery status</h4><small>Review subscriptions and recent delivery attempts.</small></span>
          </div>
          <button class="btn btn-ghost btn-sm" :disabled="loading" @click="load"><i :class="loading ? 'fas fa-spinner fa-spin' : 'fas fa-sync'"></i> Refresh</button>
        </div>
        <div v-if="webhooks.length" class="webhook-list">
          <article v-for="webhook in webhooks" :key="webhook.id" class="webhook-card">
            <div class="webhook-card__header">
              <div><strong>{{ webhook.name }}</strong><code>{{ webhook.url }}</code></div>
              <button class="btn btn-danger btn-sm" @click="remove(webhook)"><i class="fas fa-trash-alt"></i> Delete</button>
            </div>
            <div class="event-tags"><span v-for="event in webhook.events" :key="event">{{ event }}</span></div>
          </article>
        </div>
        <div v-else class="empty-state"><i class="fas fa-plug"></i><span><strong>No destinations configured</strong><small>Add a destination above to start delivering events.</small></span></div>

        <div v-if="deliveries.length" class="table-wrap"><table class="data-table">
          <thead><tr><th>Event</th><th>Status</th><th>Retries</th><th>Last error</th><th></th></tr></thead>
          <tbody>
            <tr v-for="delivery in deliveries" :key="delivery.id">
              <td>{{ delivery.event_type }}</td>
              <td><span class="status-pill" :class="`status-pill--${delivery.status}`">{{ delivery.status }}</span></td>
              <td>{{ delivery.retry_count }}</td><td>{{ delivery.last_error || '—' }}</td>
              <td><button v-if="delivery.status === 'failed'" class="btn btn-outline btn-sm" @click="retry(delivery.id)"><i class="fas fa-redo"></i> Retry</button></td>
            </tr>
          </tbody>
        </table></div>
            </section>
          </div>
        </div>
      </div>
    </Transition>
  </section>
</template>

<script>
import {
  createWebhook, deleteWebhook, getWebhookDeliveries, getWebhookSettings,
  getWebhooks, retryWebhookDelivery, updateWebhookSettings,
} from '@/api/api';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';

const EVENTS = [
  'suggestion.created', 'suggestion.awaiting_approval', 'suggestion.approved',
  'suggestion.rejected', 'request.submitted', 'request.failed', 'run.failed',
  'job.completed', 'job.skipped',
];

export default {
  name: 'SettingsWebhooks',
  components: { BaseCheckbox },
  data() {
    return {
      expanded: false, helpExpanded: false, loading: false, creating: false, savingAllowlist: false, webhooks: [], deliveries: [],
      allowedHostsText: '', eventOptions: EVENTS,
      form: { name: '', url: '', secret: '', events: [], allow_private: false },
    };
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
        await createWebhook(this.form);
        this.form = { name: '', url: '', secret: '', events: [], allow_private: false };
        this.$toast.success('Webhook added.');
        await this.load();
      } catch (error) { this.$toast.error(error.response?.data?.error?.message || 'Unable to add webhook.'); }
      finally { this.creating = false; }
    },
    async remove(webhook) {
      if (!window.confirm(`Delete webhook “${webhook.name}”?`)) return;
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

<style scoped>
.webhook-settings {
  grid-column: 1 / -1;
  overflow: hidden;
}

.webhook-settings__toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: var(--spacing-sm);
  color: var(--color-text-primary);
  background: transparent;
  border: 0;
  border-radius: var(--radius-md);
  text-align: left;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.webhook-settings__toggle:hover,
.webhook-settings__toggle:focus-visible {
  background: var(--surface-glass-subtle);
}

.webhook-settings__toggle:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.webhook-settings__heading,
.webhook-settings__meta,
.webhook-panel__header,
.webhook-card__header,
.private-option,
.empty-state {
  display: flex;
  align-items: center;
}

.webhook-settings__heading,
.webhook-settings__meta,
.webhook-panel__header,
.empty-state {
  gap: var(--spacing-md);
}

.webhook-settings__icon,
.webhook-panel__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: var(--input-height-md);
  height: var(--input-height-md);
  color: var(--color-primary-light);
  background: var(--surface-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.webhook-settings__title {
  display: block;
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
}

.section-description {
  display: block;
  margin-top: var(--spacing-xs);
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.count-badge,
.status-pill,
.event-tags span {
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
}

.count-badge {
  padding: var(--spacing-xs) var(--spacing-sm);
  color: var(--color-text-secondary);
  background: var(--surface-interactive);
}

.webhook-settings__chevron {
  color: var(--color-text-muted);
  transition: transform var(--transition-fast);
}

.webhook-settings__chevron.expanded {
  transform: rotate(90deg);
}

.webhook-settings__collapse,
.webhook-guide__collapse {
  display: grid;
  grid-template-rows: 1fr;
  opacity: 1;
}

.webhook-settings__collapse-inner,
.webhook-guide__collapse-inner {
  min-height: 0;
  overflow: hidden;
}

.webhook-collapse-enter-active,
.webhook-collapse-leave-active {
  transition:
    grid-template-rows var(--transition-slow),
    opacity var(--transition-base);
}

.webhook-collapse-enter-from,
.webhook-collapse-leave-to {
  grid-template-rows: 0fr;
  opacity: 0;
}

.webhook-settings__content {
  display: grid;
  gap: var(--spacing-lg);
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-lg);
  border-top: 1px solid var(--color-border-light);
}

.webhook-guide {
  overflow: hidden;
  background: var(--surface-glass-subtle);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.webhook-guide__toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: var(--spacing-md);
  color: var(--color-text-primary);
  background: transparent;
  border: 0;
  text-align: left;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.webhook-guide__toggle:hover,
.webhook-guide__toggle:focus-visible {
  background: var(--surface-interactive);
}

.webhook-guide__toggle:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.webhook-guide__heading {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.webhook-guide__heading > i {
  color: var(--color-info-light);
  font-size: var(--font-size-lg);
}

.webhook-guide__heading strong,
.webhook-guide__heading small {
  display: block;
}

.webhook-guide__heading small {
  margin-top: var(--spacing-xs);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-normal);
}

.webhook-guide__chevron {
  color: var(--color-text-muted);
  transition: transform var(--transition-fast);
}

.webhook-guide__chevron.expanded {
  transform: rotate(90deg);
}

.webhook-guide__body {
  display: grid;
  gap: var(--spacing-lg);
  padding: 0 var(--spacing-lg) var(--spacing-lg);
  color: var(--color-text-secondary);
  border-top: 1px solid var(--color-border-light);
}

.webhook-guide__body > p {
  margin: var(--spacing-lg) 0 0;
  color: var(--color-text-secondary);
}

.webhook-guide__steps {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--spacing-md);
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: webhook-step;
}

.webhook-guide__steps li {
  display: grid;
  grid-template-columns: var(--input-height-sm) minmax(0, 1fr);
  gap: var(--spacing-sm);
  align-items: start;
  counter-increment: webhook-step;
}

.webhook-guide__steps li::before {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--input-height-sm);
  height: var(--input-height-sm);
  color: var(--color-primary-light);
  background: var(--surface-interactive);
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  content: counter(webhook-step);
}

.webhook-guide__steps strong,
.webhook-guide__steps span {
  grid-column: 2;
}

.webhook-guide__steps span {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.webhook-guide__events {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--spacing-sm);
}

.webhook-guide__events > span {
  padding: var(--spacing-md);
  background: var(--surface-raised);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
}

.webhook-guide__events strong,
.webhook-guide__events small {
  display: block;
}

.webhook-guide__events small {
  margin-top: var(--spacing-xs);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.webhook-guide__signature {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  color: var(--color-text-secondary);
  background: var(--color-info-alpha-10);
  border: 1px solid var(--color-info);
  border-radius: var(--radius-sm);
}

.webhook-guide__signature > i {
  margin-top: var(--spacing-xs);
  color: var(--color-info-light);
}

.webhook-guide__signature strong,
.webhook-guide__signature small {
  display: block;
}

.webhook-guide__signature small {
  margin-top: var(--spacing-xs);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-relaxed);
}

.webhook-guide__signature code {
  color: var(--color-text-secondary);
  font-family: var(--font-family-mono);
  overflow-wrap: anywhere;
}

.webhook-settings__grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
  gap: var(--spacing-lg);
}

.webhook-panel {
  padding: var(--spacing-lg);
  background: var(--surface-glass-subtle);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.webhook-panel__header {
  margin-bottom: var(--spacing-lg);
}

.webhook-panel__header h4 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
}

.webhook-panel__header small {
  display: block;
  margin-top: var(--spacing-xs);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.form-group {
  display: grid;
  gap: var(--spacing-sm);
  margin: 0;
}

.form-group label,
.field-label {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}

.form-control {
  width: 100%;
}

textarea.form-control {
  resize: vertical;
  font-family: var(--font-family-mono);
}

.webhook-settings__form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.webhook-settings__events {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: var(--spacing-sm);
  margin-top: var(--spacing-sm);
}

.event-option {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  color: var(--color-text-muted);
  background: var(--surface-glass-subtle);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: var(--transition-base);
}

.event-option:hover,
.event-option.selected {
  color: var(--color-text-primary);
  background: var(--surface-interactive);
  border-color: var(--color-border-medium);
}

.event-option input {
  accent-color: var(--color-primary);
}

.private-option {
  margin-top: var(--spacing-lg);
  padding: var(--spacing-md);
  background: var(--color-warning-alpha-10);
  border: 1px solid var(--color-warning);
  border-radius: var(--radius-sm);
}

.private-option :deep(.base-checkbox) {
  width: 100%;
}

.panel-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--spacing-lg);
}

.webhook-panel--status {
  background: var(--surface-glass-subtle);
}

.webhook-settings__section-header,
.webhook-card__header {
  display: flex;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.webhook-settings__section-header {
  align-items: center;
}

.webhook-settings__section-header .webhook-panel__header {
  margin-bottom: 0;
}

.webhook-list {
  display: grid;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-lg);
}

.webhook-card {
  padding: var(--spacing-md);
  background: var(--surface-raised);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
}

.webhook-card__header {
  align-items: flex-start;
}

.webhook-card__header strong,
.webhook-card__header code {
  display: block;
}

.webhook-card__header strong {
  color: var(--color-text-primary);
}

.webhook-card__header code {
  margin-top: var(--spacing-xs);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.event-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  margin-top: var(--spacing-md);
}

.event-tags span {
  padding: var(--spacing-2xs) var(--spacing-sm);
  color: var(--color-text-muted);
  background: var(--surface-interactive);
  font-family: var(--font-family-mono);
}

.empty-state {
  justify-content: center;
  margin-top: var(--spacing-lg);
  padding: var(--spacing-xl);
  color: var(--color-text-muted);
  background: var(--surface-glass-subtle);
  border: 1px dashed var(--color-border-medium);
  border-radius: var(--radius-md);
}

.empty-state > i {
  font-size: var(--font-size-xl);
}

.empty-state strong,
.empty-state small {
  display: block;
}

.empty-state strong {
  color: var(--color-text-secondary);
}

.empty-state small {
  margin-top: var(--spacing-xs);
}

.table-wrap {
  margin-top: var(--spacing-lg);
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}

.data-table th,
.data-table td {
  padding: var(--spacing-sm) var(--spacing-md);
  color: var(--color-text-secondary);
  text-align: left;
  border-bottom: 1px solid var(--color-border-light);
}

.data-table th {
  color: var(--color-text-muted);
  font-weight: var(--font-weight-semibold);
}

.status-pill {
  display: inline-flex;
  padding: var(--spacing-2xs) var(--spacing-sm);
  color: var(--color-text-muted);
  background: var(--surface-interactive);
}

.status-pill--delivered {
  color: var(--color-success-light);
  background: var(--color-success-alpha-10);
}

.status-pill--failed {
  color: var(--color-error-light);
  background: var(--color-error-alpha-10);
}

.status-pill--queued {
  color: var(--color-warning-light);
  background: var(--color-warning-alpha-10);
}

@media (max-width: 900px) {
  .webhook-settings__grid,
  .webhook-settings__form-grid,
  .webhook-guide__steps {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .webhook-settings__meta .count-badge {
    display: none;
  }

  .webhook-panel {
    padding: var(--spacing-md);
  }

  .webhook-guide__events {
    grid-template-columns: 1fr;
  }

  .webhook-settings__section-header,
  .webhook-card__header {
    align-items: stretch;
    flex-direction: column;
  }

  .data-table th,
  .data-table td {
    padding: var(--spacing-sm);
  }
}
</style>
