<template>
  <div class="settings-group">
    <h3><i class="fas fa-key"></i> API Keys</h3>
    <p class="card-desc">Keys are for external integrations. The full value is shown only once.</p>
    <form @submit.prevent="create">
      <div class="form-group">
        <label for="apiKeyName">Key name</label>
        <input id="apiKeyName" v-model="name" class="form-control" maxlength="100" placeholder="Home Assistant" :disabled="creating">
      </div>
      <div class="form-group">
        <label for="apiKeyExpiry">Expiry (optional)</label>
        <ApiKeyExpiryPicker id="apiKeyExpiry" v-model="expiresAt" :disabled="creating" />
      </div>
      <button type="submit" class="btn btn-outline btn-sm api-keys-create" :disabled="creating || !name.trim() || keys.length >= activeLimit">
        <i :class="creating ? 'fas fa-spinner fa-spin' : 'fas fa-plus'"></i> Create key
      </button>
    </form>
    <p v-if="keys.length >= activeLimit" class="error-banner">Active-key limit reached.</p>
    <div v-if="!keys.length" class="list-empty">No API keys yet.</div>
    <div v-else class="api-keys-table-wrap">
      <table class="api-keys-table">
        <thead><tr><th>Name</th><th>Created</th><th class="api-keys-table__action">Action</th></tr></thead>
        <tbody>
          <tr v-for="key in keys" :key="key.id">
            <td><span class="api-keys-table__name"><i class="fas fa-key"></i>{{ key.name }}</span></td>
            <td>{{ formatDate(key.created_at) }}</td>
            <td class="api-keys-table__action"><button class="btn btn-danger btn-sm icon-btn" title="Revoke key" @click="revoke(key)" :disabled="revoking === key.id"><i :class="revoking === key.id ? 'fas fa-spinner fa-spin' : 'fas fa-trash'"></i><span class="sr-only">Revoke {{ key.name }}</span></button></td>
          </tr>
        </tbody>
      </table>
    </div>
    <Teleport to="body">
      <div v-if="oneTimeKey" class="modal-overlay" @click.self="closeKey">
        <section class="modal modal--sm" role="dialog" aria-modal="true" aria-labelledby="api-key-modal-title">
          <header class="modal-header"><div class="modal-title-wrap"><h3 id="api-key-modal-title" class="modal-title">Save this API key now</h3><p class="modal-subtitle">This value cannot be shown again.</p></div><button class="modal-close" aria-label="Close" @click="closeKey"><i class="fas fa-times"></i></button></header>
          <div class="modal-body"><input class="form-control" :value="oneTimeKey" readonly aria-label="New API key"></div>
          <footer class="modal-footer"><button class="btn btn-primary" @click="copy"><i class="fas fa-copy"></i> Copy key</button><button class="btn btn-outline" @click="closeKey">Done</button></footer>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<script>
import { createApiKey, getApiKeys, revokeApiKey } from '@/api/api';
import ApiKeyExpiryPicker from '@/components/common/ApiKeyExpiryPicker.vue';

export default {
  name: 'ApiKeysPanel',
  components: { ApiKeyExpiryPicker },
  data: () => ({ keys: [], activeLimit: 10, name: '', expiresAt: '', creating: false, revoking: null, oneTimeKey: '' }),
  async mounted() { await this.load(); },
  methods: {
    async load() { try { const response = await getApiKeys(); this.keys = response.data.keys || []; this.activeLimit = response.data.active_limit || 10; } catch { this.$toast.error('Failed to load API keys'); } },
    async create() { this.creating = true; try { const response = await createApiKey({ name: this.name.trim(), expires_at: this.expiresAt ? `${this.expiresAt}T23:59:59` : null }); this.oneTimeKey = response.data.key; this.name = ''; this.expiresAt = ''; await this.load(); } catch (error) { this.$toast.error(error.response?.data?.error || 'Failed to create API key'); } finally { this.creating = false; } },
    async revoke(key) { if (!window.confirm(`Revoke ${key.name}? This cannot be undone.`)) return; this.revoking = key.id; try { await revokeApiKey(key.id); await this.load(); this.$toast.success('API key revoked'); } catch { this.$toast.error('Failed to revoke API key'); } finally { this.revoking = null; } },
    async copy() { try { await navigator.clipboard.writeText(this.oneTimeKey); this.$toast.success('API key copied'); } catch { this.$toast.error('Copy failed'); } },
    closeKey() { this.oneTimeKey = ''; },
    formatDate(value) { return value ? new Date(value).toLocaleDateString() : '—'; },
  },
};
</script>

<style scoped>
.api-keys-table-wrap { overflow-x: auto; margin-top: var(--spacing-lg); border: 1px solid var(--color-border-light); border-radius: var(--radius-md); }
.api-keys-table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.api-keys-table th { padding: var(--spacing-sm) var(--spacing-md); color: var(--color-text-muted); font-weight: var(--font-weight-semibold); text-align: left; background: var(--surface-glass-subtle); }
.api-keys-table td { padding: var(--spacing-md); color: var(--color-text-secondary); border-top: 1px solid var(--color-border-light); }
.api-keys-table tbody tr { transition: background var(--transition-fast); }
.api-keys-table tbody tr:hover { background: var(--surface-glass-subtle); }
.api-keys-table__name { display: inline-flex; align-items: center; gap: var(--spacing-sm); color: var(--color-text-primary); font-weight: var(--font-weight-medium); }
.api-keys-table__name i { color: var(--color-text-muted); }
.api-keys-table__action { width: 1%; text-align: right; white-space: nowrap; }
.api-keys-create { width: 100%; }
.card-desc { margin: 0 0 var(--spacing-lg); color: var(--color-text-muted); font-size: var(--font-size-sm); line-height: var(--line-height-normal); }
@media (max-width: 700px) { .api-keys-table th, .api-keys-table td { padding: var(--spacing-sm); } }
</style>
