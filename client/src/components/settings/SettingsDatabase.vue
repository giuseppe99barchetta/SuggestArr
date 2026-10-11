<template>
  <div class="flex flex-col gap-5">
    <PageHeader v-if="!wizardMode" title="Database" subtitle="Where SuggestArr keeps requests, jobs and history. SQLite needs no setup; PostgreSQL or MySQL suit larger or shared installs." />

    <section class="rounded-card border border-edge bg-panel p-5">
      <h2 class="m-0 mb-1 text-[17px] font-bold text-ink">Database engine</h2>
      <p class="m-0 mb-4 text-[13px] text-ink-3">Switching engines does not move existing data.</p>
      <div role="radiogroup" aria-label="Database engine" class="grid gap-3 sm:grid-cols-3">
        <button
          v-for="engine in engines"
          :key="engine.value"
          type="button"
          role="radio"
          :aria-checked="localConfig.DB_TYPE === engine.value ? 'true' : 'false'"
          :disabled="isLoading"
          class="flex cursor-pointer flex-col gap-1.5 rounded-ctl border p-4 text-left disabled:cursor-not-allowed"
          :class="localConfig.DB_TYPE === engine.value ? 'border-brand-ink bg-brand-soft/50' : 'border-edge-strong bg-canvas hover:border-ink-4'"
          @click="selectEngine(engine.value)"
        >
          <span class="flex items-center gap-2 text-sm font-bold text-ink">
            <span class="flex h-4 w-4 items-center justify-center rounded-full border-2" :class="localConfig.DB_TYPE === engine.value ? 'border-brand-ink' : 'border-edge-strong'"><span v-if="localConfig.DB_TYPE === engine.value" class="h-1.5 w-1.5 rounded-full bg-brand-ink"></span></span>
            {{ engine.label }}
          </span>
          <span class="text-xs leading-snug text-ink-3">{{ engine.description }}</span>
        </button>
      </div>
    </section>

    <section v-if="localConfig.DB_TYPE === 'sqlite'" class="flex items-start gap-3 rounded-card border border-edge bg-panel p-5">
      <i aria-hidden="true" class="fas fa-check-circle mt-0.5 text-good"></i>
      <p class="m-0 text-sm leading-relaxed text-ink-2">Nothing to configure. Data is stored in <code>config/config_files/requests.db</code>; back up that file to keep a copy.</p>
    </section>

    <section v-else class="rounded-card border border-edge bg-panel p-5">
      <h2 class="m-0 mb-1 text-[17px] font-bold text-ink">{{ engineLabel }} connection</h2>
      <p class="m-0 mb-4 text-[13px] text-ink-3">Create the database first; SuggestArr creates its tables on start.</p>
      <div class="grid gap-4 sm:grid-cols-[2fr_1fr]">
        <label class="flex flex-col gap-1.5 text-[13px] font-semibold text-ink-2">
          Host
          <input v-model="localConfig.DB_HOST" type="text" placeholder="localhost" :class="inputClass" :disabled="isLoading" />
        </label>
        <label class="flex flex-col gap-1.5 text-[13px] font-semibold text-ink-2">
          Port
          <input v-model.number="localConfig.DB_PORT" type="number" :placeholder="defaultPort" :class="inputClass" :disabled="isLoading" />
        </label>
        <label class="flex flex-col gap-1.5 text-[13px] font-semibold text-ink-2">
          Database name
          <input v-model="localConfig.DB_NAME" type="text" placeholder="suggestarr" :class="inputClass" :disabled="isLoading" />
        </label>
        <label class="flex flex-col gap-1.5 text-[13px] font-semibold text-ink-2">
          Username
          <input v-model="localConfig.DB_USER" type="text" :placeholder="localConfig.DB_TYPE === 'postgres' ? 'postgres' : 'root'" :class="inputClass" :disabled="isLoading" autocomplete="off" />
        </label>
        <label class="flex flex-col gap-1.5 text-[13px] font-semibold text-ink-2 sm:col-span-2">
          Password
          <span class="flex gap-2">
            <input v-model="localConfig.DB_PASSWORD" :type="showPassword ? 'text' : 'password'" placeholder="Database password" :class="inputClass" class="flex-1" :disabled="isLoading" autocomplete="new-password" />
            <button type="button" class="h-[42px] w-[42px] shrink-0 cursor-pointer rounded-ctl border border-edge-strong bg-panel-2 text-ink-3 hover:text-ink" :aria-label="showPassword ? 'Hide password' : 'Show password'" :disabled="isLoading" @click="showPassword = !showPassword">
              <i aria-hidden="true" :class="showPassword ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </span>
        </label>
      </div>
      <button
        type="button"
        class="mt-5 inline-flex h-10 cursor-pointer items-center gap-2 rounded-ctl border border-edge-strong bg-panel-2 px-4 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="isLoading || !isConnectionComplete || isTestingDatabase"
        @click="testDatabaseConnection"
      >
        <i aria-hidden="true" :class="isTestingDatabase ? 'fas fa-spinner fa-spin' : 'fas fa-plug'"></i>{{ isTestingDatabase ? 'Testing…' : 'Test connection' }}
      </button>
    </section>

    <section v-if="hasDbTypeChanged && localConfig.DB_TYPE !== 'sqlite'" role="note" class="rounded-card border border-caution/40 bg-caution/10 p-5">
      <h2 class="m-0 mb-2 text-[15px] font-bold text-ink"><i aria-hidden="true" class="fas fa-exclamation-triangle mr-2 text-caution"></i>Your data does not move by itself</h2>
      <ol class="m-0 flex flex-col gap-1 pl-5 text-sm leading-relaxed text-ink-2">
        <li>Export your current configuration (Advanced → Application &amp; Maintenance).</li>
        <li>Back up your SQLite database file.</li>
        <li>Create the new database in your chosen engine.</li>
        <li>Import your configuration.</li>
        <li>Test the new connection.</li>
      </ol>
    </section>

    <div v-if="!wizardMode" class="flex flex-wrap items-center gap-3 rounded-card border px-[18px] py-3.5" :class="hasChanges ? 'sticky bottom-4 z-10 border-brand-soft bg-[#18162b] max-lg:bottom-24' : 'border-edge bg-panel'">
      <span class="flex-[1_1_200px] text-sm" :class="hasChanges ? 'text-brand-ink' : 'text-ink-3'">{{ hasChanges ? 'You have unsaved changes.' : 'All changes saved.' }}</span>
      <button type="button" class="h-10 cursor-pointer rounded-ctl border-0 bg-transparent px-4 text-sm font-semibold text-ink-3 hover:text-ink disabled:opacity-50" :disabled="isLoading" @click="resetToDefaults">Reset to defaults</button>
      <button type="button" class="h-10 cursor-pointer rounded-ctl border-0 bg-brand px-[18px] text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50" :disabled="isLoading || !hasChanges" @click="saveSettings">{{ isLoading ? 'Saving…' : 'Save changes' }}</button>
    </div>
  </div>
</template>

<script>
import PageHeader from '@/components/ui/PageHeader.vue';

const ENGINES = [
  { value: 'sqlite', label: 'SQLite', description: 'Default. A single file next to the config, no server needed.', port: '' },
  { value: 'postgres', label: 'PostgreSQL', description: 'A separate database server. Good for large or shared installs.', port: '5432' },
  { value: 'mysql', label: 'MySQL / MariaDB', description: 'A separate database server, if you already run one.', port: '3306' },
];

export default {
  name: 'SettingsDatabase',
  components: { PageHeader },
  // The dashboard shell passes props this page does not declare.
  inheritAttrs: false,
  props: {
    config: {
      type: Object,
      required: true,
    },
    isLoading: {
      type: Boolean,
      default: false,
    },
    testingConnections: {
      type: Object,
      default: () => ({
        database: false,
      }),
    },
    // Wizard mode: hides save button and enables config-changed / validation-changed emits
    wizardMode: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['save-section', 'test-connection', 'validation-changed', 'config-changed'],
  data() {
    return {
      localConfig: {},
      originalConfig: {},
      showPassword: false,
      engines: ENGINES,
      inputClass: 'h-[42px] w-full rounded-ctl border border-edge-strong bg-canvas px-3 text-sm font-normal text-ink outline-none focus:border-brand-ink disabled:opacity-60',
    };
  },
  computed: {
    hasChanges() {
      return JSON.stringify(this.localConfig) !== JSON.stringify(this.originalConfig);
    },
    hasDbTypeChanged() {
      return this.localConfig.DB_TYPE !== this.originalConfig.DB_TYPE;
    },
    isConnectionComplete() {
      return Boolean(
        this.localConfig.DB_HOST &&
        this.localConfig.DB_PORT &&
        this.localConfig.DB_NAME &&
        this.localConfig.DB_USER &&
        this.localConfig.DB_PASSWORD
      );
    },
    currentEngine() {
      return ENGINES.find(engine => engine.value === this.localConfig.DB_TYPE) || ENGINES[0];
    },
    engineLabel() {
      return this.currentEngine.label;
    },
    defaultPort() {
      return this.currentEngine.port;
    },
    isTestingDatabase() {
      return this.testingConnections?.database || false;
    },
  },
  watch: {
    config: {
      immediate: true,
      handler(newConfig) {
        this.localConfig = { ...newConfig };
        this.originalConfig = { ...newConfig };
        // SQLite is always valid; emit immediately in wizard mode
        if (this.wizardMode && newConfig.DB_TYPE === 'sqlite') {
          this.$emit('validation-changed', true);
        }
      },
    },
  },
  beforeUnmount() {
    if (this.wizardMode) {
      this.$emit('config-changed', { ...this.localConfig });
    }
  },
  methods: {
    selectEngine(value) {
      if (this.localConfig.DB_TYPE === value) return;
      this.localConfig.DB_TYPE = value;
      this.onDbTypeChange();
    },

    onDbTypeChange() {
      // Clear database-specific fields when switching types
      if (this.localConfig.DB_TYPE === 'sqlite') {
        this.localConfig.DB_HOST = null;
        this.localConfig.DB_PORT = null;
        this.localConfig.DB_NAME = null;
        this.localConfig.DB_USER = null;
        this.localConfig.DB_PASSWORD = null;
        // SQLite is always valid
        if (this.wizardMode) this.$emit('validation-changed', true);
      } else {
        if (this.localConfig.DB_TYPE === 'postgres') {
          this.localConfig.DB_PORT = this.localConfig.DB_PORT || 5432;
        } else if (this.localConfig.DB_TYPE === 'mysql') {
          this.localConfig.DB_PORT = this.localConfig.DB_PORT || 3306;
        }
        // Non-SQLite requires a successful test
        if (this.wizardMode) this.$emit('validation-changed', false);
      }
    },

    async testDatabaseConnection() {
      try {
        if (this.wizardMode) {
          // Self-contained test in wizard mode
          const axios = (await import('axios')).default;
          const res = await axios.post('/api/config/test-db-connection', {
            DB_TYPE: this.localConfig.DB_TYPE,
            DB_HOST: this.localConfig.DB_HOST,
            DB_PORT: this.localConfig.DB_PORT,
            DB_NAME: this.localConfig.DB_NAME,
            DB_USER: this.localConfig.DB_USER,
            DB_PASSWORD: this.localConfig.DB_PASSWORD,
          });
          if (res.status === 200) {
            if (this.$toast) this.$toast.success('Database connection successful!', { position: 'top-right', duration: 3000 });
            this.$emit('validation-changed', true);
          }
        } else {
          await this.$emit('test-connection', 'database', {
            DB_TYPE: this.localConfig.DB_TYPE,
            DB_HOST: this.localConfig.DB_HOST,
            DB_PORT: this.localConfig.DB_PORT,
            DB_NAME: this.localConfig.DB_NAME,
            DB_USER: this.localConfig.DB_USER,
            DB_PASSWORD: this.localConfig.DB_PASSWORD,
          });
        }
      } catch (error) {
        console.error('Error testing database connection:', error);
        if (this.wizardMode) {
          if (this.$toast) this.$toast.error('Database connection failed. Check your settings.', { position: 'top-right', duration: 5000 });
          this.$emit('validation-changed', false);
        }
      }
    },

    async saveSettings() {
      try {
        const dataToSave = {
          DB_TYPE: this.localConfig.DB_TYPE,
        };

        // Only include database-specific fields if not SQLite
        if (this.localConfig.DB_TYPE !== 'sqlite') {
          Object.assign(dataToSave, {
            DB_HOST: this.localConfig.DB_HOST,
            DB_PORT: this.localConfig.DB_PORT,
            DB_NAME: this.localConfig.DB_NAME,
            DB_USER: this.localConfig.DB_USER,
            DB_PASSWORD: this.localConfig.DB_PASSWORD,
          });
        }

        await this.$emit('save-section', {
          section: 'database',
          data: dataToSave,
        });

        this.originalConfig = { ...this.localConfig };
      } catch (error) {
        console.error('Error saving database settings:', error);
      }
    },

    async resetToDefaults() {
      const defaults = {
        DB_TYPE: 'sqlite',
        DB_HOST: null,
        DB_PORT: null,
        DB_USER: null,
        DB_PASSWORD: null,
        DB_NAME: null,
      };

      if (confirm('Are you sure you want to reset all database settings to their defaults?')) {
        this.localConfig = { ...this.localConfig, ...defaults };
        await this.saveSettings();
      }
    },
  },
};
</script>

