<template>
  <div class="[&_code]:break-all [&_code]:px-[0.35rem] [&_code]:py-[0.1rem] [&_code]:text-xs">
    <PageHeader :title="sectionMeta.title" :subtitle="sectionMeta.subtitle" />

    <div class="mb-6">
      <div v-if="section === 'ai'" class="flex flex-col gap-5">
        <SectionCard icon="fas fa-wand-magic-sparkles" title="AI recommendations" description="Let the AI pick suggestions from watch history.">
          <div class="flex flex-col gap-4">
            <BaseCheckbox
              v-model="localConfig.ENABLE_ADVANCED_ALGORITHM"
              :disabled="isLoading"
              label="Use AI suggestion algorithm"
              description="Use an AI-powered algorithm for hyper-personalized content suggestions based on watch history."
            />

            <div v-if="localConfig.ENABLE_ADVANCED_ALGORITHM && !hasAiProvider" role="alert" class="flex items-start gap-3 rounded-card border border-caution/40 bg-caution/10 px-4 py-3.5">
              <i aria-hidden="true" class="fas fa-exclamation-triangle mt-0.5 text-caution"></i>
              <p class="m-0 text-sm text-ink-2"><strong class="text-ink">No AI provider configured.</strong> The AI algorithm needs an API key or a base URL (for local providers) in the provider card, otherwise it cannot run.</p>
            </div>
          </div>
        </SectionCard>

        <!-- Also used by AI Search, so always visible -->
        <SectionCard icon="fas fa-robot" title="AI provider" description="Any OpenAI-compatible API, in the cloud or on your machine.">
          <template #actions>
            <button type="button" class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border-0 bg-transparent text-brand-ink hover:bg-brand-soft" title="Learn how to configure AI providers" aria-label="Learn how to configure AI providers" @click="showAiInfoModal = true">
              <i aria-hidden="true" class="fas fa-circle-info"></i>
            </button>
          </template>

          <div class="flex flex-col gap-4">
            <div class="grid gap-4 md:grid-cols-2">
            <label class="ui-label" for="openaiApiKey">
              <span>API key <span class="ml-1.5 rounded-full bg-raised px-2 py-0.5 text-[11px] font-normal text-ink-4">Optional</span></span>
              <input id="openaiApiKey" v-model="localConfig.OPENAI_API_KEY" type="password" placeholder="sk-..." class="ui-input" :disabled="isLoading" />
              <span class="text-xs font-normal text-ink-4">Required for OpenAI and hosted providers. For local providers like Ollama or LM Studio, use any placeholder (for example <code>sk-local</code>).</span>
            </label>

            <label class="ui-label" for="llmModel">
              Model
              <input id="llmModel" v-model="localConfig.LLM_MODEL" type="text" placeholder="gpt-4o-mini" class="ui-input" :disabled="isLoading" />
              <span class="text-xs font-normal text-ink-4">For Ollama use the local model tag (for example <code>llama3.1</code>). For LM Studio use the loaded model identifier.</span>
            </label>
            </div>

            <label class="ui-label" for="openaiBaseUrl">
              <span>Base URL <span class="ml-1.5 rounded-full bg-raised px-2 py-0.5 text-[11px] font-normal text-ink-4">Optional</span></span>
              <input id="openaiBaseUrl" v-model="localConfig.OPENAI_BASE_URL" type="text" placeholder="https://api.openai.com/v1" class="ui-input" :disabled="isLoading" />
              <span class="text-xs font-normal text-ink-4">Leave blank for OpenAI. Use <code>http://localhost:11434/v1</code> for Ollama, <code>http://localhost:1234/v1</code> for LM Studio, or your LiteLLM/OpenRouter endpoint.</span>
            </label>

            <div class="rounded-ctl border border-edge bg-panel-2">
              <button
                type="button"
                class="flex w-full cursor-pointer items-center gap-3 border-0 bg-transparent p-3.5 text-left text-ink"
                :aria-expanded="aiAdvancedExpanded.toString()"
                aria-controls="ai-advanced-settings"
                @click="aiAdvancedExpanded = !aiAdvancedExpanded"
              >
                <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-ctl bg-brand-soft text-brand-ink"><i aria-hidden="true" class="fas fa-sliders-h"></i></span>
                <span class="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span class="text-sm font-semibold">Advanced AI settings</span>
                  <span class="text-xs text-ink-4">Temperature, reasoning effort, and web search</span>
                </span>
                <i aria-hidden="true" class="fas fa-chevron-right text-ink-4 transition-transform" :class="{ 'rotate-90': aiAdvancedExpanded }"></i>
              </button>

              <div v-show="aiAdvancedExpanded" id="ai-advanced-settings" class="grid gap-4 px-3.5 pb-3.5 md:grid-cols-2">
                <label class="ui-label" for="llmTemperature">
                  Temperature
                  <input id="llmTemperature" v-model.trim="localConfig.LLM_TEMPERATURE" type="text" inputmode="decimal" placeholder="legacy" class="ui-input" :disabled="isLoading" />
                  <span class="text-xs font-normal text-ink-4">Use <code>legacy</code> to keep current behavior (0.7 for recommendations, 0.8 for AI Search). Clear and save to omit the parameter, or enter a value from 0 to 2.</span>
                </label>

                <div class="flex flex-col gap-1.5">
                  <BaseDropdown v-model="localConfig.LLM_REASONING_EFFORT" :options="reasoningEffortOptions" label="Reasoning effort" :disabled="isLoading" id="llmReasoningEffort" />
                  <span class="text-xs text-ink-4">Sent only to direct OpenAI GPT-5 and o-series models. Other OpenAI-compatible provider/model combinations omit it.</span>
                </div>

                <label class="ui-label md:col-span-2" for="searxngBaseUrl">
                  <span>SearXNG base URL <span class="ml-1.5 rounded-full bg-raised px-2 py-0.5 text-[11px] font-normal text-ink-4">Optional</span></span>
                  <input id="searxngBaseUrl" v-model.trim="localConfig.SEARXNG_BASE_URL" type="url" placeholder="http://searxng:8080" class="ui-input" :disabled="isLoading" />
                  <span class="text-xs font-normal text-ink-4">Optional self-hosted SearXNG instance. Its top three JSON search results add current context to AI Search and AI recommendations; leave blank to disable it.</span>
                </label>
              </div>
            </div>

            <div class="flex flex-wrap items-center gap-3">
              <button type="button" class="ui-btn" :disabled="isLoading || isTestingLlm" @click="testLlmConnection">
                <i aria-hidden="true" :class="isTestingLlm ? 'fas fa-spinner fa-spin' : 'fas fa-plug'"></i>
                {{ isTestingLlm ? 'Testing…' : 'Test connection' }}
              </button>
              <span v-if="llmStatus && !isTestingLlm" class="text-[13px] font-semibold" :class="llmStatus === 'ok' ? 'text-good' : 'text-bad'" role="status">
                <i aria-hidden="true" :class="llmStatus === 'ok' ? 'fas fa-check-circle' : 'fas fa-times-circle'"></i>
                {{ llmStatus === 'ok' ? 'Connected' : 'Connection failed' }}
              </span>
            </div>
          </div>
        </SectionCard>
      </div>

      <AppDialog v-if="showAiInfoModal" width="max-w-2xl" title="Set up an AI provider" subtitle="Any OpenAI-compatible API works, in the cloud or on your machine." icon="fas fa-robot" @close="showAiInfoModal = false">
        <div class="flex flex-col gap-5">
          <p class="m-0 text-sm leading-relaxed text-ink-2">
            SuggestArr uses any <strong>OpenAI-compatible API</strong> to generate personalized recommendations based on your watch history. You can use a cloud provider or a local LLM running on your machine.
          </p>

          <div class="flex flex-wrap gap-2" role="tablist" aria-label="AI Providers">
            <button
              class="cursor-pointer rounded-ctl border px-[0.7rem] py-[0.4rem] text-[0.85rem] font-semibold transition"
              :class="activeAiGuideTab === 'openai' ? 'border-brand bg-brand-soft text-ink' : 'border-edge-strong bg-panel-2 text-ink-3 hover:border-ink-4 hover:text-ink'"
              role="tab"
              :aria-selected="activeAiGuideTab === 'openai'"
              @click="activeAiGuideTab = 'openai'"
            >
              OpenAI
            </button>
            <button
              class="cursor-pointer rounded-ctl border px-[0.7rem] py-[0.4rem] text-[0.85rem] font-semibold transition"
              :class="activeAiGuideTab === 'ollama' ? 'border-brand bg-brand-soft text-ink' : 'border-edge-strong bg-panel-2 text-ink-3 hover:border-ink-4 hover:text-ink'"
              role="tab"
              :aria-selected="activeAiGuideTab === 'ollama'"
              @click="activeAiGuideTab = 'ollama'"
            >
              Ollama
            </button>
            <button
              class="cursor-pointer rounded-ctl border px-[0.7rem] py-[0.4rem] text-[0.85rem] font-semibold transition"
              :class="activeAiGuideTab === 'lmstudio' ? 'border-brand bg-brand-soft text-ink' : 'border-edge-strong bg-panel-2 text-ink-3 hover:border-ink-4 hover:text-ink'"
              role="tab"
              :aria-selected="activeAiGuideTab === 'lmstudio'"
              @click="activeAiGuideTab = 'lmstudio'"
            >
              LM Studio
            </button>
            <button
              class="cursor-pointer rounded-ctl border px-[0.7rem] py-[0.4rem] text-[0.85rem] font-semibold transition"
              :class="activeAiGuideTab === 'gemini' ? 'border-brand bg-brand-soft text-ink' : 'border-edge-strong bg-panel-2 text-ink-3 hover:border-ink-4 hover:text-ink'"
              role="tab"
              :aria-selected="activeAiGuideTab === 'gemini'"
              @click="activeAiGuideTab = 'gemini'"
            >
              Gemini
            </button>
            <button
              class="cursor-pointer rounded-ctl border px-[0.7rem] py-[0.4rem] text-[0.85rem] font-semibold transition"
              :class="activeAiGuideTab === 'litellm' ? 'border-brand bg-brand-soft text-ink' : 'border-edge-strong bg-panel-2 text-ink-3 hover:border-ink-4 hover:text-ink'"
              role="tab"
              :aria-selected="activeAiGuideTab === 'litellm'"
              @click="activeAiGuideTab = 'litellm'"
            >
              LiteLLM
            </button>
          </div>

          <div role="tabpanel" v-if="activeAiGuideTab === 'openai'">
            <div class="rounded-ctl border border-edge bg-panel-2 px-4 py-3.5">
              <div class="mb-2.5 flex items-center gap-2 text-[0.95rem] font-semibold text-ink [&_i]:text-brand-ink"><i class="fas fa-cloud"></i> OpenAI</div>
              <ol class="mb-3 flex list-decimal flex-col gap-2.5 pl-[1.15rem] text-[0.9rem] leading-snug text-ink-2">
                <li>Create an API key in your OpenAI account.</li>
                <li>Use a model that supports chat completions, such as <code>gpt-4o-mini</code>.</li>
                <li>Leave Base URL empty to use the default OpenAI endpoint.</li>
              </ol>
              <pre class="m-0 overflow-x-auto rounded-lg border border-edge bg-canvas p-3 text-[0.8rem] leading-[1.4] text-ink-2" aria-label="OpenAI config example"><code>OPENAI_API_KEY=sk-proj-...
OPENAI_BASE_URL=
LLM_MODEL=gpt-4o-mini</code></pre>
            </div>
          </div>

          <div role="tabpanel" v-else-if="activeAiGuideTab === 'ollama'">
            <div class="rounded-ctl border border-brand/40 bg-panel-2 px-4 py-3.5">
              <div class="mb-2.5 flex items-center gap-2 text-[0.95rem] font-semibold text-ink [&_i]:text-brand-ink"><i class="fas fa-server"></i> Ollama <span class="rounded-lg bg-brand-soft px-2 py-0.5 text-[0.7rem] font-semibold uppercase tracking-wider text-brand-ink">Local</span></div>
              <ol class="mb-3 flex list-decimal flex-col gap-2.5 pl-[1.15rem] text-[0.9rem] leading-snug text-ink-2">
                <li>Install and run Ollama on your machine.</li>
                <li>Pull a model (example: <code>ollama pull llama3.1</code>).</li>
                <li>Set Base URL to <code>http://localhost:11434/v1</code> and model to your local model name.</li>
              </ol>
              <pre class="m-0 overflow-x-auto rounded-lg border border-edge bg-canvas p-3 text-[0.8rem] leading-[1.4] text-ink-2" aria-label="Ollama config example"><code>OPENAI_API_KEY=sk-local
OPENAI_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1</code></pre>
              <pre class="m-0 overflow-x-auto rounded-lg border border-edge bg-canvas p-3 text-[0.8rem] leading-[1.4] text-ink-2 mt-2.5 max-h-[140px] overflow-y-auto" aria-label="Ollama docker example"><code>docker run --rm -it \
  -p 11434:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama</code></pre>
            </div>
          </div>

          <div role="tabpanel" v-else-if="activeAiGuideTab === 'lmstudio'">
            <div class="rounded-ctl border border-brand/40 bg-panel-2 px-4 py-3.5">
              <div class="mb-2.5 flex items-center gap-2 text-[0.95rem] font-semibold text-ink [&_i]:text-brand-ink"><i class="fas fa-laptop-code"></i> LM Studio <span class="rounded-lg bg-brand-soft px-2 py-0.5 text-[0.7rem] font-semibold uppercase tracking-wider text-brand-ink">Local</span></div>
              <ol class="mb-3 flex list-decimal flex-col gap-2.5 pl-[1.15rem] text-[0.9rem] leading-snug text-ink-2">
                <li>Run LM Studio.</li>
                <li>Start the OpenAI-compatible server from LM Studio.</li>
                <li>Use Base URL <code>http://localhost:1234/v1</code>.</li>
                <li>Use any dummy API key, for example <code>sk-local</code>.</li>
              </ol>
              <pre class="m-0 overflow-x-auto rounded-lg border border-edge bg-canvas p-3 text-[0.8rem] leading-[1.4] text-ink-2" aria-label="LM Studio config example"><code>OPENAI_API_KEY=sk-local
OPENAI_BASE_URL=http://localhost:1234/v1
LLM_MODEL=your-loaded-model</code></pre>
              <small class="mt-2 block text-[0.8rem] text-ink-3">
                SuggestArr automatically falls back if a provider rejects
                <code>response_format={"type":"json_object"}</code>, so LM Studio works without requiring a LiteLLM proxy.
              </small>
            </div>
          </div>

          <div role="tabpanel" v-else-if="activeAiGuideTab === 'gemini'">
            <div class="rounded-ctl border border-edge bg-panel-2 px-4 py-3.5">
              <div class="mb-2.5 flex items-center gap-2 text-[0.95rem] font-semibold text-ink [&_i]:text-brand-ink"><i class="fas fa-gem"></i> Google Gemini</div>
              <p class="mb-3 text-sm text-ink-2">
                Use Google's Gemini API through its OpenAI-compatible endpoint.
              </p>
              <ol class="mb-3 flex list-decimal flex-col gap-2.5 pl-[1.15rem] text-[0.9rem] leading-snug text-ink-2">
                <li>Create an API key in Google AI Studio.</li>
                <li>Paste the API key into SuggestArr.</li>
                <li>Use the Gemini OpenAI-compatible base URL shown below.</li>
              </ol>
              <pre class="m-0 overflow-x-auto rounded-lg border border-edge bg-canvas p-3 text-[0.8rem] leading-[1.4] text-ink-2" aria-label="Gemini config example"><code>OPENAI_API_KEY=AIza...
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.0-flash</code></pre>
              <small class="mt-2 block text-[0.8rem] text-ink-3">Generate keys at <a href="https://aistudio.google.com/" target="_blank" rel="noopener">Google AI Studio</a>.</small>
            </div>
          </div>

          <div role="tabpanel" v-else>
            <div class="rounded-ctl border border-edge bg-panel-2 px-4 py-3.5">
              <div class="mb-2.5 flex items-center gap-2 text-[0.95rem] font-semibold text-ink [&_i]:text-brand-ink"><i class="fas fa-exchange-alt"></i> LiteLLM Proxy <span class="rounded-lg bg-caution/15 px-2 py-0.5 text-[0.7rem] font-semibold uppercase tracking-wider text-caution">Advanced</span></div>
              <ol class="mb-3 flex list-decimal flex-col gap-2.5 pl-[1.15rem] text-[0.9rem] leading-snug text-ink-2">
                <li>Run LiteLLM proxy with your provider mappings.</li>
                <li>Set SuggestArr Base URL to the proxy endpoint.</li>
                <li>Use the model alias configured in LiteLLM.</li>
              </ol>
              <pre class="m-0 overflow-x-auto rounded-lg border border-edge bg-canvas p-3 text-[0.8rem] leading-[1.4] text-ink-2" aria-label="LiteLLM config example"><code>OPENAI_API_KEY=sk-your-proxy-key
OPENAI_BASE_URL=http://localhost:4000/v1
LLM_MODEL=gpt-4o-mini</code></pre>
              <pre class="m-0 overflow-x-auto rounded-lg border border-edge bg-canvas p-3 text-[0.8rem] leading-[1.4] text-ink-2 mt-2.5 max-h-[140px] overflow-y-auto" aria-label="LiteLLM docker example"><code>docker run --rm -it \
  -p 4000:4000 \
  -v ./litellm_config.yaml:/app/config.yaml \
  ghcr.io/berriai/litellm:main-latest \
  --config /app/config.yaml</code></pre>
            </div>
          </div>

          <p class="m-0 flex gap-3 rounded-ctl border border-edge bg-panel-2 p-3 text-[13px] leading-relaxed text-ink-3">
            <i aria-hidden="true" class="fas fa-lightbulb mt-0.5 text-caution"></i>
            <span>The system sends your watch history to the LLM and receives a ranked list of recommendations with reasoning. No personal data is stored by the provider beyond your API usage.</span>
          </p>
        </div>
        <template #footer>
          <button type="button" class="ui-btn" @click="showAiInfoModal = false">Close</button>
        </template>
      </AppDialog>

      <div v-if="section === 'system'" class="grid items-start gap-5 lg:grid-cols-2">
        <SectionCard icon="fas fa-bug" title="Debug &amp; appearance" description="Logging verbosity and visual effects.">
          <div class="flex flex-col gap-4">
            <div class="flex flex-col gap-1.5">
              <BaseDropdown v-model="localConfig.LOG_LEVEL" :options="logLevelOptions" label="Log level" :disabled="isLoading" id="logLevel" />
              <span class="text-xs text-ink-4">Set the verbosity of application logs.</span>
            </div>

            <BaseCheckbox v-model="localConfig.ENABLE_DEBUG_MODE" :disabled="isLoading" label="Enable debug mode" description="Enable detailed logging and debugging information" />
            <BaseCheckbox v-model="localConfig.ENABLE_PERFORMANCE_MONITORING" :disabled="isLoading" label="Enable performance monitoring" description="Track performance metrics for optimization" />
            <BaseCheckbox
              :model-value="!localConfig.ENABLE_VISUAL_EFFECTS"
              :disabled="isLoading"
              label="Disable visual effects (blur)"
              description="Turns off the blurred poster backgrounds on the setup and sign-in screens. Helps on slow devices."
              @update:model-value="localConfig.ENABLE_VISUAL_EFFECTS = !$event"
            />
            <BaseCheckbox v-model="localConfig.ENABLE_STATIC_BACKGROUND" :disabled="isLoading" label="Enable static colored background" description="Use a solid color instead of rotating posters behind the setup wizard." />

            <div v-if="localConfig.ENABLE_STATIC_BACKGROUND" class="ui-label">
              <label for="staticBackgroundColor">Static background color (hex)</label>
              <div class="flex items-center gap-2">
                <input id="staticBackgroundColor" v-model="localConfig.STATIC_BACKGROUND_COLOR" type="color" class="ui-input h-[42px] w-14 shrink-0 cursor-pointer p-1" :disabled="isLoading" />
                <input v-model="localConfig.STATIC_BACKGROUND_COLOR" type="text" placeholder="#2E3440" class="ui-input" pattern="^#[0-9A-Fa-f]{6}$" title="Must be a valid hex color code (e.g. #FF0000)" aria-label="Background color hex code" :disabled="isLoading" />
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard icon="fas fa-memory" title="Cache" description="How long TMDb data is kept and how much space it may use.">
          <div class="flex flex-col gap-4">
            <label class="ui-label" for="cacheTtl">
              Cache TTL (hours)
              <input id="cacheTtl" v-model.number="localConfig.CACHE_TTL" type="number" min="1" max="168" placeholder="24" class="ui-input" :disabled="isLoading" />
              <span class="text-xs font-normal text-ink-4">How long to cache API responses and data (1-168 hours).</span>
            </label>

            <label class="ui-label" for="maxCacheSize">
              Max cache size (MB)
              <input id="maxCacheSize" v-model.number="localConfig.MAX_CACHE_SIZE" type="number" min="10" max="1024" placeholder="100" class="ui-input" :disabled="isLoading" />
              <span class="text-xs font-normal text-ink-4">Maximum cache size in megabytes (10-1024 MB).</span>
            </label>

            <BaseCheckbox v-model="localConfig.ENABLE_API_CACHING" :disabled="isLoading" label="Enable TMDb response caching" description="Cache repeated TMDb metadata requests to reduce external API calls" />

            <div class="flex flex-col items-start gap-1.5">
              <button type="button" class="ui-btn" :disabled="isLoading" @click="clearCache"><i aria-hidden="true" class="fas fa-trash"></i>Clear cache</button>
              <span class="text-xs text-ink-4">Clear cached TMDb metadata and force fresh API calls.</span>
            </div>
          </div>
        </SectionCard>

        <SectionCard icon="fas fa-shield-alt" title="Access &amp; routing" description="Choose how users access SuggestArr and where it is served from.">
          <div class="flex flex-col gap-4">
            <BaseDropdown v-model="localConfig.AUTH_MODE" :options="authModeOptions" label="Authentication mode" :disabled="isLoading" id="authMode" />
            <p class="m-0 text-[13px] leading-relaxed text-ink-3">Require login for everyone, let trusted local networks bypass login, or disable authentication.</p>

            <div v-if="localConfig.AUTH_MODE === 'disabled' || localConfig.AUTH_MODE === 'local_bypass'" role="alert" class="flex items-start gap-3 rounded-card border border-caution/40 bg-caution/10 px-4 py-3.5">
              <i aria-hidden="true" class="fas fa-exclamation-triangle mt-0.5 text-caution"></i>
              <p class="m-0 text-sm text-ink-2">
                <strong class="text-ink">Warning:</strong>
                {{ localConfig.AUTH_MODE === 'disabled' ? 'Authentication will be completely disabled. Only use this in trusted environments.' : 'Requests from trusted local networks will bypass authentication.' }}
              </p>
            </div>

            <label v-if="localConfig.AUTH_MODE === 'local_bypass'" class="ui-label" for="authTrustedCidrs">
              Trusted CIDRs
              <input id="authTrustedCidrs" v-model="localConfig.AUTH_TRUSTED_CIDRS" type="text" placeholder="127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16" class="ui-input" :disabled="isLoading" />
              <span class="text-xs font-normal text-ink-4">Comma-separated CIDR ranges that can bypass auth when mode is <code>local_bypass</code>.</span>
            </label>

            <label v-if="localConfig.AUTH_MODE === 'local_bypass' || localConfig.AUTH_MODE === 'disabled'" class="ui-label" for="authBypassUsername">
              Bypass username
              <input id="authBypassUsername" v-model="localConfig.AUTH_BYPASS_USERNAME" type="text" placeholder="local_admin" class="ui-input" :disabled="isLoading" />
              <span class="text-xs font-normal text-ink-4">Username used as internal request context when auth is bypassed.</span>
            </label>

            <label class="ui-label" for="subpath">
              Subpath
              <input id="subpath" v-model="localConfig.SUBPATH" type="text" placeholder="/suggestarr" class="ui-input" :disabled="isLoading" />
              <span class="text-xs font-normal text-ink-4">For running SuggestArr under a subdirectory (e.g. "/suggestarr"). Leave empty for root.</span>
            </label>
          </div>
        </SectionCard>

        <SectionCard icon="fas fa-file-export" title="Configuration management" description="Back up, restore, or reset the complete SuggestArr configuration.">
          <div class="flex flex-col gap-2.5">
            <div v-for="action in configActions" :key="action.event" class="flex flex-wrap items-center gap-3 rounded-ctl border p-3.5" :class="action.danger ? 'border-bad/40 bg-bad/10' : 'border-edge bg-panel-2'">
              <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-ctl bg-raised" :class="action.danger ? 'text-bad' : 'text-brand-ink'"><i aria-hidden="true" :class="action.icon"></i></span>
              <span class="flex min-w-[180px] flex-1 flex-col gap-0.5">
                <span class="text-sm font-semibold text-ink">{{ action.title }}</span>
                <span class="text-xs leading-snug text-ink-4">{{ action.hint }}</span>
              </span>
              <button type="button" :class="action.danger ? 'ui-btn-danger' : 'ui-btn'" :disabled="isLoading" @click="$emit(action.event)">{{ action.label }}</button>
            </div>
          </div>
          <p class="m-0 mt-4 flex items-start gap-2 rounded-ctl bg-panel-2 p-3 text-xs leading-relaxed text-ink-4">
            <i aria-hidden="true" class="fas fa-lock mt-0.5 text-caution"></i>
            <span>Configuration backups may contain service credentials. Store exported files securely.</span>
          </p>
        </SectionCard>
      </div>

      <!-- Request Workflow -->
      <div v-if="section === 'workflow'" class="grid items-start gap-5 lg:grid-cols-2">
        <SectionCard icon="fas fa-check-double" title="Approval flow" description="Control when suggestions can leave SuggestArr and reach Seer.">
          <div class="flex flex-col gap-2.5">
            <button
              v-for="toggle in approvalToggles"
              :key="toggle.key"
              type="button"
              role="switch"
              :aria-checked="localConfig[toggle.key] ? 'true' : 'false'"
              :disabled="isLoading || (toggle.needsApproval && !localConfig.REQUIRE_REQUEST_APPROVAL)"
              class="flex cursor-pointer items-center gap-3 rounded-ctl border border-edge bg-panel-2 p-3.5 text-left hover:border-edge-strong disabled:cursor-not-allowed disabled:opacity-50"
              @click="localConfig[toggle.key] = !localConfig[toggle.key]"
            >
              <span class="flex min-w-0 flex-1 flex-col gap-0.5">
                <span class="text-sm font-semibold text-ink">{{ toggle.title }}</span>
                <span class="text-xs leading-snug text-ink-4">{{ toggle.hint }}</span>
              </span>
              <span class="relative inline-block h-[22px] w-10 shrink-0 rounded-full transition-colors" :class="localConfig[toggle.key] ? 'bg-brand' : 'bg-edge-strong'"><span class="absolute top-[3px] h-4 w-4 rounded-full bg-white transition-all" :class="localConfig[toggle.key] ? 'left-[21px]' : 'left-[3px]'"></span></span>
            </button>

            <label class="flex items-center gap-3 rounded-ctl border border-edge bg-panel-2 p-3.5" :class="{ 'opacity-50': !localConfig.REQUIRE_REQUEST_APPROVAL }">
              <span class="flex min-w-0 flex-1 flex-col gap-0.5">
                <span class="text-sm font-semibold text-ink">Auto-reject after</span>
                <span class="text-xs leading-snug text-ink-4">Days a suggestion may wait for review. 0 keeps it until someone decides.</span>
              </span>
              <span class="flex shrink-0 items-center gap-2 text-[13px] text-ink-3">
                <input id="autoRejectApprovalDays" v-model.number="localConfig.AUTO_REJECT_APPROVAL_DAYS" type="number" min="0" max="365" class="ui-input h-9 w-20 px-2.5" :disabled="isLoading || !localConfig.REQUIRE_REQUEST_APPROVAL" />days
              </span>
            </label>
            <p v-if="!localConfig.REQUIRE_REQUEST_APPROVAL" class="m-0 text-xs text-ink-4">Suggestions go straight to Seer, so the queue options are off.</p>
          </div>
        </SectionCard>

        <SectionCard icon="fas fa-eye" title="Who sees what" description="Which requests each user can see, and the language titles appear in.">
          <fieldset class="m-0 flex flex-col gap-2 border-0 p-0">
            <legend class="mb-2 p-0 text-[13px] font-semibold text-ink-2">Request visibility</legend>
            <label
              v-for="option in requestVisibilityOptions"
              :key="option.value"
              class="flex cursor-pointer items-start gap-3 rounded-ctl border p-3.5"
              :class="localConfig.REQUEST_VISIBILITY === option.value ? 'border-brand-ink bg-brand-soft/50' : 'border-edge bg-panel-2 hover:border-edge-strong'"
            >
              <input v-model="localConfig.REQUEST_VISIBILITY" type="radio" name="requestVisibility" :value="option.value" class="mt-1 accent-brand" :disabled="isLoading" />
              <span class="flex flex-col gap-0.5">
                <span class="text-sm font-semibold text-ink">{{ option.label }}</span>
                <span class="text-xs leading-snug text-ink-4">{{ option.hint }}</span>
              </span>
            </label>
            <p class="m-0 mt-1 text-xs leading-relaxed text-ink-4">A suggestion belongs to whoever is linked to the media account it was made for. Suggestions without an owner stay with the admins.</p>
          </fieldset>

          <label class="ui-label mt-5 border-t border-edge pt-5">
            Default title language
            <select id="tmdbLanguage" v-model="localConfig.TMDB_LANGUAGE" class="ui-input" :disabled="isLoading">
              <option v-for="option in titleLanguageOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
            <span class="text-xs font-normal text-ink-4">For everyone who has not picked a language on their profile.</span>
          </label>
        </SectionCard>
      </div>


    </div>



    <div class="mt-5 flex flex-wrap items-center gap-3 rounded-card border px-[18px] py-3.5" :class="hasChanges ? 'sticky bottom-4 z-10 border-brand-soft bg-[#18162b] max-lg:bottom-24' : 'border-edge bg-panel'">
      <span class="flex-[1_1_200px] text-sm" :class="hasChanges ? 'text-brand-ink' : 'text-ink-3'">{{ hasChanges ? 'You have unsaved changes.' : 'All changes saved.' }}</span>
      <button v-if="section === 'system'" type="button" class="ui-btn border-0 bg-transparent text-ink-3 hover:text-bad" :disabled="isLoading" title="Resets AI, diagnostics, cache and access settings" @click="resetToDefaults">Reset all advanced settings</button>
      <button type="button" class="ui-btn-primary" :disabled="isLoading || !hasChanges" @click="saveSettings">{{ isLoading ? 'Saving…' : 'Save changes' }}</button>
    </div>
  </div>
</template>

<script>
import PageHeader from '@/components/ui/PageHeader.vue';
import SectionCard from '@/components/ui/SectionCard.vue';
import AppDialog from '@/components/ui/AppDialog.vue';
import axios from 'axios';
import BaseDropdown from '@/components/common/BaseDropdown.vue';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import { languageOptions } from '@/utils/titleLanguage.js';

export default {
  name: 'SettingsAdvanced',
  components: { AppDialog, PageHeader, SectionCard,
    BaseDropdown,
    BaseCheckbox,
  },
  props: {
    // Which part of the former Advanced page to show: 'ai', 'workflow' or 'system'.
    section: {
      type: String,
      default: 'ai',
    },
    config: {
      type: Object,
      required: true,
    },
    isLoading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['save-section', 'export-config', 'import-config', 'reset-config'],
  // The dashboard shell passes props this page does not declare.
  inheritAttrs: false,
  data() {
    return {
      localConfig: {},
      originalConfig: {},
      availableUsers: [],
      isLoadingUsers: false,
      showAiInfoModal: false,
      aiAdvancedExpanded: false,
      activeAiGuideTab: 'openai',
      isTestingLlm: false,
      llmStatus: null, // null | 'ok' | 'error', result of the last connection test
      removeLeaveGuard: null,
      logLevelOptions: [
        { value: 'ERROR', label: 'Error' },
        { value: 'WARNING', label: 'Warning' },
        { value: 'INFO', label: 'Info' },
        { value: 'DEBUG', label: 'Debug' }
      ],
      reasoningEffortOptions: [
        { value: '', label: 'Provider/model default' },
        { value: 'low', label: 'Low' },
        { value: 'medium', label: 'Medium' },
        { value: 'high', label: 'High' },
      ],
      authModeOptions: [
        { value: 'enabled', label: 'Require Login' },
        { value: 'local_bypass', label: 'Allow Local Network Without Login' },
        { value: 'disabled', label: 'Disable Authentication' },
      ],
      requestVisibilityOptions: [
        { value: 'all', label: 'Everyone sees everything', hint: 'Every user sees every request.' },
        { value: 'own', label: 'Users see their own', hint: 'Users see requests for their linked accounts; admins still see all.' },
        { value: 'own_all', label: 'Everyone sees their own', hint: 'Admins are limited to their linked accounts too.' },
      ],
      approvalToggles: [
        { key: 'REQUIRE_REQUEST_APPROVAL', title: 'Require approval before delivery', hint: 'Hold new suggestions in SuggestArr until an admin approves them.' },
        { key: 'PAUSE_JOBS_WITH_PENDING_APPROVALS', title: 'Pause jobs while approvals are pending', hint: 'Stop automation from adding more until the current queue is reviewed.', needsApproval: true },
      ],
      configActions: [
        { event: 'export-config', icon: 'fas fa-download', title: 'Export a backup', hint: 'Download the current SuggestArr configuration for safekeeping or migration.', label: 'Export' },
        { event: 'import-config', icon: 'fas fa-upload', title: 'Restore a backup', hint: 'Import a previously exported configuration into this instance.', label: 'Import' },
        { event: 'reset-config', icon: 'fas fa-undo', title: 'Reset SuggestArr', hint: 'Discard the current configuration and return application settings to their defaults.', label: 'Reset', danger: true },
      ],
      tmdbLanguages: [],
    };
  },
  computed: {
    sectionMeta() {
      return {
        ai: { title: 'AI provider', subtitle: 'The language model behind AI Search and AI recommendations.' },
        workflow: { title: 'Approvals', subtitle: 'Whether suggestions wait for your approval, who sees which requests, and how long pending ones stay.' },
        system: { title: 'System', subtitle: 'Logging, cache, sign-in, reverse-proxy path and configuration backups.' },
      }[this.section] || { title: 'Advanced', subtitle: '' };
    },
    // Without a profile choice there is no "default of the default": English
    // is what TMDb answers with anyway.
    titleLanguageOptions() {
      const options = languageOptions(this.tmdbLanguages).slice(1);
      return options.length ? options : [{ value: 'en', label: 'English' }];
    },
    hasChanges() {
      return JSON.stringify(this.localConfig) !== JSON.stringify(this.originalConfig);
    },
    // Local providers (Ollama, LM Studio) only need a base URL; hosted ones need a key.
    hasAiProvider() {
      return Boolean((this.localConfig.OPENAI_API_KEY || '').trim() || (this.localConfig.OPENAI_BASE_URL || '').trim());
    },
  },
  watch: {
    config: {
      immediate: true,
      handler(newConfig) {
        this.localConfig = { ...newConfig };
        if (this.localConfig.LLM_TEMPERATURE === 'unset') {
          this.localConfig.LLM_TEMPERATURE = '';
        }
        // Ensure SELECTED_USERS is always a parsed array
        if (typeof this.localConfig.SELECTED_USERS === 'string') {
          try {
            this.localConfig.SELECTED_USERS = JSON.parse(this.localConfig.SELECTED_USERS);
          } catch {
            this.localConfig.SELECTED_USERS = [];
          }
        } else if (!Array.isArray(this.localConfig.SELECTED_USERS)) {
          this.localConfig.SELECTED_USERS = [];
        }

        // Set default values for new advanced settings
        const advancedDefaults = {
          LOG_LEVEL: 'INFO',
          ENABLE_DEBUG_MODE: false,
          ENABLE_PERFORMANCE_MONITORING: false,
          CACHE_TTL: 24,
          MAX_CACHE_SIZE: 100,
          ENABLE_API_CACHING: true,
          REQUIRE_REQUEST_APPROVAL: false,
          REQUEST_VISIBILITY: 'all',
          TMDB_LANGUAGE: 'en',
          PAUSE_JOBS_WITH_PENDING_APPROVALS: false,
          AUTO_REJECT_APPROVAL_DAYS: 0,
          ENABLE_ADVANCED_ALGORITHM: false,
          OPENAI_API_KEY: '',
          OPENAI_BASE_URL: '',
          LLM_MODEL: 'gpt-4o-mini',
          LLM_TEMPERATURE: 'legacy',
          LLM_REASONING_EFFORT: '',
          SEARXNG_BASE_URL: '',
          ENABLE_SOCIAL_FEATURES: false,
          ENABLE_VISUAL_EFFECTS: true,
          ENABLE_STATIC_BACKGROUND: false,
          STATIC_BACKGROUND_COLOR: '#2E3440',
          AUTH_MODE: 'enabled',
          AUTH_TRUSTED_CIDRS: '127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16',
          AUTH_BYPASS_USERNAME: 'local_admin',
        };

        Object.keys(advancedDefaults).forEach(key => {
          if (this.localConfig[key] === undefined) {
            this.localConfig[key] = advancedDefaults[key];
          }
        });

        if (!this.authModeOptions.some(option => option.value === this.localConfig.AUTH_MODE)) {
          this.localConfig.AUTH_MODE = 'enabled';
        }

        // Snapshot after defaults and normalisation, so an untouched page is not "dirty".
        this.originalConfig = { ...this.localConfig };
      },
    },
  },
  mounted() {
    this.loadUsers();
    this.loadTmdbLanguages();
    // Tabs are switched by changing the route param, so guard route changes plus tab close.
    this.removeLeaveGuard = this.$router.beforeEach(() => {
      if (this.hasChanges && !window.confirm('You have unsaved changes. Leave without saving?')) return false;
    });
    window.addEventListener('beforeunload', this.warnBeforeUnload);
  },
  beforeUnmount() {
    if (this.removeLeaveGuard) this.removeLeaveGuard();
    window.removeEventListener('beforeunload', this.warnBeforeUnload);
  },
  methods: {
    warnBeforeUnload(event) {
      if (this.hasChanges) event.preventDefault();
    },
    async loadTmdbLanguages() {
      try {
        const { data } = await axios.get('/api/tmdb/languages', { timeout: 10000 });
        this.tmdbLanguages = data?.languages || [];
      } catch {
        this.tmdbLanguages = [];
      }
    },

    isUserSelected(userId) {
      if (!Array.isArray(this.localConfig.SELECTED_USERS)) {
        return false;
      }
      // Handle both formats: array of objects or array of IDs (legacy)
      return this.localConfig.SELECTED_USERS.some(user => {
        if (typeof user === 'string') {
          return user === userId;
        } else if (typeof user === 'object' && user.id) {
          return user.id === userId;
        }
        return false;
      });
    },

    toggleUserSelection(userId) {
      if (!Array.isArray(this.localConfig.SELECTED_USERS)) {
        this.localConfig.SELECTED_USERS = [];
      }

      // Normalize to array of objects format
      const normalized = this.localConfig.SELECTED_USERS.map(user => {
        if (typeof user === 'string') {
          // Convert legacy format to new format
          const fullUser = this.availableUsers.find(u => u.id === user);
          return fullUser ? { id: fullUser.id, name: fullUser.name } : { id: user, name: user };
        } else if (typeof user === 'object' && user.id) {
          return { id: user.id, name: user.name };
        }
        return null;
      }).filter(u => u !== null);

      // Find index by comparing IDs
      const index = normalized.findIndex(u => u.id === userId);

      if (index > -1) {
        // Remove user from selection
        normalized.splice(index, 1);
      } else {
        // Add user to selection - find full user object
        const userToAdd = this.availableUsers.find(u => u.id === userId);
        if (userToAdd) {
          normalized.push({ id: userToAdd.id, name: userToAdd.name });
        } else {
          // Fallback if user not found in availableUsers
          normalized.push({ id: userId, name: userId });
        }
      }

      this.localConfig.SELECTED_USERS = normalized;
    },

    async loadUsers() {
      this.isLoadingUsers = true;
      try {
        const service = this.localConfig.SELECTED_SERVICE;
        if (!service) {
          this.availableUsers = [];
          return;
        }

        let endpoint;
        if (service === 'plex') {
          endpoint = '/api/plex/users';
        } else if (service === 'jellyfin') {
          endpoint = '/api/jellyfin/users';
        } else if (service === 'seer') {
          endpoint = '/api/seer/users';
        }

        if (endpoint) {
          let response;

          // Send Plex credentials in request body, not query params
          if (service === 'plex') {
            response = await axios.post(endpoint, {
              PLEX_TOKEN: this.localConfig.PLEX_TOKEN,
              PLEX_API_URL: this.localConfig.PLEX_API_URL || '',
            });
          } else {
            response = await axios.get(endpoint);
          }

          this.availableUsers = response.data.users || response.data || [];
        }
      } catch (error) {
        console.error('Error loading users:', error);
        this.availableUsers = [];
      } finally {
        this.isLoadingUsers = false;
      }
    },

    async refreshUsers() {
      await this.loadUsers();
    },

    async clearCache() {
      if (confirm('Are you sure you want to clear cached TMDb data? This may temporarily slow down metadata requests.')) {
        try {
          await axios.post('/api/tmdb/cache/clear');
          this.$toast.success('Cache cleared successfully!');
        } catch (error) {
          this.$toast.error('Failed to clear cache');
          console.error('Error clearing cache:', error);
        }
      }
    },

    async saveSettings() {
      const cidrText = String(this.localConfig.AUTH_TRUSTED_CIDRS || '').trim();
      const temperatureText = String(this.localConfig.LLM_TEMPERATURE ?? '').trim();
      const temperature = temperatureText.toLowerCase() === 'legacy' ? 'legacy' : temperatureText;
      const authMode = this.authModeOptions.some(option => option.value === this.localConfig.AUTH_MODE)
        ? this.localConfig.AUTH_MODE
        : 'enabled';

      if (temperature && temperature !== 'legacy' && (Number.isNaN(Number(temperature)) || Number(temperature) < 0 || Number(temperature) > 2)) {
        this.$toast.error('Temperature must be legacy, blank, or a number from 0 to 2.');
        return;
      }

      if (authMode === 'local_bypass' && !cidrText) {
        this.$toast.error('Trusted CIDRs are required when Authentication Mode is local_bypass.');
        return;
      }

      if (cidrText) {
        const invalidCidrs = cidrText
          .split(',')
          .map(item => item.trim())
          .filter(item => item && !item.includes('/'));
        if (invalidCidrs.length > 0) {
          this.$toast.error('Trusted CIDRs must be a comma-separated CIDR list (for example 192.168.0.0/16).');
          return;
        }
      }

      try {
        await this.$emit('save-section', {
          section: 'advanced',
          data: {
            SELECTED_USERS: this.localConfig.SELECTED_USERS || [],
            LOG_LEVEL: this.localConfig.LOG_LEVEL || 'INFO',
            ENABLE_DEBUG_MODE: this.localConfig.ENABLE_DEBUG_MODE || false,
            ENABLE_PERFORMANCE_MONITORING: this.localConfig.ENABLE_PERFORMANCE_MONITORING || false,
            CACHE_TTL: this.localConfig.CACHE_TTL || 24,
            MAX_CACHE_SIZE: this.localConfig.MAX_CACHE_SIZE || 100,
            ENABLE_API_CACHING: this.localConfig.ENABLE_API_CACHING !== false,
            REQUIRE_REQUEST_APPROVAL: this.localConfig.REQUIRE_REQUEST_APPROVAL !== false,
            REQUEST_VISIBILITY: ['own', 'own_all'].includes(this.localConfig.REQUEST_VISIBILITY) ? this.localConfig.REQUEST_VISIBILITY : 'all',
            TMDB_LANGUAGE: /^[a-z]{2}(-[A-Z]{2})?$/.test(this.localConfig.TMDB_LANGUAGE || '') ? this.localConfig.TMDB_LANGUAGE : 'en',
            PAUSE_JOBS_WITH_PENDING_APPROVALS: this.localConfig.PAUSE_JOBS_WITH_PENDING_APPROVALS === true,
            AUTO_REJECT_APPROVAL_DAYS: Math.max(0, Number(this.localConfig.AUTO_REJECT_APPROVAL_DAYS) || 0),
            ENABLE_ADVANCED_ALGORITHM: this.localConfig.ENABLE_ADVANCED_ALGORITHM || false,
            OPENAI_API_KEY: this.localConfig.OPENAI_API_KEY || '',
            OPENAI_BASE_URL: this.localConfig.OPENAI_BASE_URL || '',
            LLM_MODEL: this.localConfig.LLM_MODEL || 'gpt-4o-mini',
            LLM_TEMPERATURE: temperature || 'unset',
            LLM_REASONING_EFFORT: this.localConfig.LLM_REASONING_EFFORT || '',
            SEARXNG_BASE_URL: this.localConfig.SEARXNG_BASE_URL || '',
            ENABLE_SOCIAL_FEATURES: this.localConfig.ENABLE_SOCIAL_FEATURES || false,
            ENABLE_VISUAL_EFFECTS: this.localConfig.ENABLE_VISUAL_EFFECTS !== false,
            ENABLE_STATIC_BACKGROUND: this.localConfig.ENABLE_STATIC_BACKGROUND || false,
            STATIC_BACKGROUND_COLOR: this.localConfig.STATIC_BACKGROUND_COLOR || '#2E3440',
            AUTH_MODE: authMode,
            AUTH_TRUSTED_CIDRS: cidrText || '127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16',
            AUTH_BYPASS_USERNAME: (this.localConfig.AUTH_BYPASS_USERNAME || '').trim() || 'local_admin',
            SUBPATH: this.localConfig.SUBPATH || null,
          },
        });

        this.originalConfig = { ...this.localConfig };

        if (this.section === 'ai' && this.hasAiProvider) this.testLlmConnection();
      } catch (error) {
        console.error('Error saving advanced settings:', error);
      }
    },

    async testLlmConnection() {
      this.isTestingLlm = true;
      try {
        const response = await axios.post('/api/jobs/llm-test', {
          OPENAI_API_KEY: this.localConfig.OPENAI_API_KEY || '',
          OPENAI_BASE_URL: this.localConfig.OPENAI_BASE_URL || '',
          LLM_MODEL: this.localConfig.LLM_MODEL || 'gpt-4o-mini',
        });
        if (response.data.status === 'success') {
          this.llmStatus = 'ok';
          this.$toast.success('AI connection successful!');
        } else {
          this.llmStatus = 'error';
          this.$toast.error(response.data.message || 'Connection failed');
        }
      } catch (error) {
        this.llmStatus = 'error';
        const msg = error.response?.data?.message || 'Connection failed';
        this.$toast.error(msg);
      } finally {
        this.isTestingLlm = false;
      }
    },

    async resetToDefaults() {
      const defaults = {
        SELECTED_USERS: [],
        LOG_LEVEL: 'INFO',
        ENABLE_DEBUG_MODE: false,
        ENABLE_PERFORMANCE_MONITORING: false,
        CACHE_TTL: 24,
        MAX_CACHE_SIZE: 100,
        ENABLE_API_CACHING: true,
        ENABLE_ADVANCED_ALGORITHM: false,
        OPENAI_API_KEY: '',
        OPENAI_BASE_URL: '',
        LLM_MODEL: 'gpt-4o-mini',
        LLM_TEMPERATURE: 'legacy',
        LLM_REASONING_EFFORT: '',
        SEARXNG_BASE_URL: '',
        ENABLE_SOCIAL_FEATURES: false,
        ENABLE_VISUAL_EFFECTS: true,
        ENABLE_STATIC_BACKGROUND: false,
        STATIC_BACKGROUND_COLOR: '#2E3440',
        AUTH_MODE: 'enabled',
        AUTH_TRUSTED_CIDRS: '127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16',
        AUTH_BYPASS_USERNAME: 'local_admin',
        SUBPATH: null,
      };

      if (confirm('Are you sure you want to reset all advanced settings to their defaults?')) {
        this.localConfig = { ...this.localConfig, ...defaults };
        await this.saveSettings();
      }
    },
  },
};
</script>
