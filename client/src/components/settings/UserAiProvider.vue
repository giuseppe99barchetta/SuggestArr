<template>
  <SectionCard icon="fas fa-robot" title="My AI provider" description="Use your own OpenAI-compatible provider for AI Search. Without one, the provider the administrator shared is used.">
    <template #actions>
      <span class="rounded-full px-2.5 py-1 text-xs font-semibold" :class="saved ? 'bg-brand-soft text-brand-ink' : 'bg-raised text-ink-3'">{{ saved ? 'Using my provider' : 'Using the shared provider' }}</span>
    </template>

    <form class="flex flex-col gap-3" @submit.prevent="save">
      <label class="ui-label">API key
        <input id="aiProviderKey" v-model.trim="form.key" type="password" class="ui-input" maxlength="512" autocomplete="off" :placeholder="saved && maskedKey ? `Saved (${maskedKey}). Leave empty to keep it` : 'Not needed for a local provider'" :disabled="busy" />
      </label>
      <label class="ui-label">Address (optional)
        <input id="aiProviderUrl" v-model.trim="form.url" type="url" class="ui-input" maxlength="512" placeholder="https://api.openai.com/v1 or http://localhost:11434/v1" :disabled="busy" />
        <span class="text-xs font-normal text-ink-4">Leave empty for OpenAI. Changing the address asks for the key again.</span>
      </label>
      <label class="ui-label">Model (optional)
        <input id="aiProviderModel" v-model.trim="form.model" type="text" class="ui-input" maxlength="128" placeholder="The shared model is used when empty" :disabled="busy" />
      </label>
      <div class="flex flex-wrap gap-2">
        <button type="submit" class="ui-btn-primary" :disabled="busy || !(form.key || form.url || (saved && keepsKey))">
          <i v-if="busy" aria-hidden="true" class="fas fa-spinner fa-spin"></i>Save
        </button>
        <button v-if="saved" type="button" class="ui-btn border-0 bg-transparent text-ink-3 hover:text-bad" :disabled="busy" @click="remove">Use the shared provider</button>
      </div>
      <p v-if="error" role="alert" class="ui-alert-bad">{{ error }}</p>
    </form>
  </SectionCard>
</template>

<script>
import { deleteMyAiProvider, getMyAiProvider, saveMyAiProvider } from '@/api/api';
import SectionCard from '@/components/ui/SectionCard.vue';

export default {
  name: 'UserAiProvider',
  components: { SectionCard },
  data: () => ({ saved: false, maskedKey: '', savedUrl: '', form: { key: '', url: '', model: '' }, busy: false, error: '' }),
  computed: {
    // With a saved key and an unchanged address, saving only edits the model.
    keepsKey() { return !this.form.key && this.form.url === this.savedUrl; },
  },
  async mounted() { await this.load(); },
  methods: {
    async load() {
      try {
        const { data } = await getMyAiProvider();
        this.apply(data);
      } catch (error) {
        if (error.response?.status === 404) this.apply(null);
        else this.error = error.response?.data?.error || 'Could not load your AI provider';
      }
    },
    apply(data) {
      this.saved = !!data;
      this.maskedKey = data?.openai_api_key || '';
      this.savedUrl = data?.openai_base_url || '';
      this.form = { key: '', url: this.savedUrl, model: data?.llm_model || '' };
    },
    async save() {
      this.busy = true;
      this.error = '';
      try {
        await saveMyAiProvider({ openai_api_key: this.form.key, openai_base_url: this.form.url, llm_model: this.form.model });
        await this.load();
        this.$toast.success('AI provider saved');
      } catch (error) {
        this.error = error.response?.data?.error || 'Could not save your AI provider';
      } finally {
        this.busy = false;
      }
    },
    async remove() {
      this.busy = true;
      this.error = '';
      try {
        await deleteMyAiProvider();
        this.apply(null);
        this.$toast.success('Using the shared provider');
      } catch (error) {
        this.error = error.response?.data?.error || 'Could not remove your AI provider';
      } finally {
        this.busy = false;
      }
    },
  },
};
</script>
