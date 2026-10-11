<template>
  <SectionCard icon="fas fa-key" title="API keys" description="For external integrations such as Home Assistant. The full key is shown only once.">
    <form class="flex flex-col gap-3" @submit.prevent="create">
      <div class="grid gap-3 sm:grid-cols-[1fr_auto]">
        <label class="ui-label">Key name<input id="apiKeyName" v-model="name" class="ui-input" maxlength="100" placeholder="Home Assistant" :disabled="creating"></label>
        <label class="ui-label">Expires (optional)<input id="apiKeyExpiry" v-model="expiresAt" type="date" class="ui-input" :min="today" :disabled="creating"></label>
      </div>
      <button type="submit" class="ui-btn self-start" :disabled="creating || !name.trim() || keys.length >= activeLimit">
        <i aria-hidden="true" :class="creating ? 'fas fa-spinner fa-spin' : 'fas fa-plus'"></i>Create key
      </button>
      <p v-if="keys.length >= activeLimit" role="alert" class="ui-alert-bad">You have reached the limit of {{ activeLimit }} active keys. Revoke one to create another.</p>
    </form>
    <p v-if="!keys.length" class="m-0 mt-4 text-[13px] text-ink-4">No API keys yet.</p>
    <ul v-else class="m-0 mt-4 flex list-none flex-col gap-2 p-0">
      <li v-for="key in keys" :key="key.id" class="flex items-center gap-3 rounded-ctl border border-edge bg-panel-2 px-3 py-2">
        <i aria-hidden="true" class="fas fa-key text-ink-4"></i>
        <span class="flex min-w-0 flex-1 flex-col">
          <span class="truncate text-sm font-semibold text-ink">{{ key.name }}</span>
          <span class="text-xs text-ink-4">Created {{ formatDate(key.created_at) }}</span>
        </span>
        <button type="button" class="ui-btn-icon-danger" :aria-label="`Revoke ${key.name}`" title="Revoke key" :disabled="revoking === key.id" @click="keyToRevoke = key">
          <i aria-hidden="true" :class="revoking === key.id ? 'fas fa-spinner fa-spin' : 'fas fa-trash'"></i>
        </button>
      </li>
    </ul>

    <AppDialog v-if="oneTimeKey" labelledby="api-key-modal-title" @close="closeKey">
      <div class="flex flex-col gap-4 p-6">
        <div>
          <h3 id="api-key-modal-title" class="m-0 text-lg font-bold text-ink">Save this API key now</h3>
          <p class="m-0 mt-1 text-sm text-ink-3">This value cannot be shown again.</p>
        </div>
        <input class="ui-input font-mono" :value="oneTimeKey" readonly aria-label="New API key" @focus="$event.target.select()">
        <div class="flex justify-end gap-2">
          <button type="button" class="ui-btn" @click="closeKey">Done</button>
          <button type="button" class="ui-btn-primary" @click="copy"><i aria-hidden="true" class="fas fa-copy"></i>Copy key</button>
        </div>
      </div>
    </AppDialog>
    <AppDialog v-if="keyToRevoke" labelledby="revoke-api-key-modal-title" @close="keyToRevoke = null">
      <div class="flex flex-col gap-4 p-6">
        <div>
          <h3 id="revoke-api-key-modal-title" class="m-0 text-lg font-bold text-bad">Revoke API key?</h3>
          <p class="m-0 mt-1 text-sm text-ink-3">Integrations using <strong class="text-ink">{{ keyToRevoke.name }}</strong> stop working. This cannot be undone.</p>
        </div>
        <div class="flex justify-end gap-2">
          <button type="button" class="ui-btn" :disabled="revoking === keyToRevoke.id" @click="keyToRevoke = null">Cancel</button>
          <button type="button" class="ui-btn-primary bg-bad text-[#2a0c0b]" :disabled="revoking === keyToRevoke.id" @click="revoke">
            <i aria-hidden="true" :class="revoking === keyToRevoke.id ? 'fas fa-spinner fa-spin' : 'fas fa-trash'"></i>Revoke key
          </button>
        </div>
      </div>
    </AppDialog>
  </SectionCard>
</template>
<script>
import { createApiKey, getApiKeys, revokeApiKey } from '@/api/api';
import AppDialog from '@/components/ui/AppDialog.vue';
import SectionCard from '@/components/ui/SectionCard.vue';
import { copyText } from '@/utils/clipboard.js';

export default {
  name: 'ApiKeysPanel',
  components: { AppDialog, SectionCard },
  data: () => ({ today: new Date().toLocaleDateString('sv'), keys: [], activeLimit: 10, name: '', expiresAt: '', creating: false, revoking: null, oneTimeKey: '', keyToRevoke: null }),
  async mounted() { await this.load(); },
  methods: {
    async load() { try { const response = await getApiKeys(); this.keys = response.data.keys || []; this.activeLimit = response.data.active_limit || 10; } catch { this.$toast.error('Failed to load API keys'); } },
    async create() { this.creating = true; try { const response = await createApiKey({ name: this.name.trim(), expires_at: this.expiresAt ? `${this.expiresAt}T23:59:59` : null }); this.oneTimeKey = response.data.key; this.name = ''; this.expiresAt = ''; await this.load(); } catch (error) { this.$toast.error(error.response?.data?.error || 'Failed to create API key'); } finally { this.creating = false; } },
    async revoke() { const key = this.keyToRevoke; if (!key) return; this.revoking = key.id; try { await revokeApiKey(key.id); await this.load(); this.keyToRevoke = null; this.$toast.success('API key revoked'); } catch { this.$toast.error('Failed to revoke API key'); } finally { this.revoking = null; } },
    async copy() { if (await copyText(this.oneTimeKey)) this.$toast.success('API key copied'); else this.$toast.error('Copy failed'); },
    closeKey() { this.oneTimeKey = ''; },
    formatDate(value) { return value ? new Date(value).toLocaleDateString() : '—'; },
  },
};
</script>

