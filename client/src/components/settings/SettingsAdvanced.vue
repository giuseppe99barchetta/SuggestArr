<template>
  <div class="settings-advanced">
    <div class="section-header">
      <h2>Advanced Settings</h2>
      <p>Configure advanced options and experimental features</p>
    </div>

    <div class="settings-grid">
      <SettingsPanel
        panel-id="experimental-ai"
        title="Experimental & AI"
        description="Beta features, personalized suggestions, and AI provider configuration."
        icon="fas fa-flask"
        tone="warning"
      >
      <!-- Experimental Features -->
      <section class="advanced-subsection experimental">
        <h3>
          <i class="fas fa-flask"></i>
          Experimental Features
        </h3>
      
        <div class="warning-box">
          <i class="fas fa-exclamation-triangle"></i>
          <div>
            <strong>Warning:</strong>
            <p>
              These features are experimental and may cause unexpected behavior. Use with caution.
            </p>
          </div>
        </div>
      
        <div class="form-group">
          <BaseCheckbox
            v-model="localConfig.ENABLE_BETA_FEATURES"
            :disabled="isLoading"
            label="Enable beta features"
            description="Enable experimental features that are still in development"
          />
        </div>
      
        <div class="form-group feature-wrapper" :class="{ 'feature-disabled': !localConfig.ENABLE_BETA_FEATURES }">
          <BaseCheckbox
            v-model="localConfig.ENABLE_ADVANCED_ALGORITHM"
            :disabled="isLoading || !localConfig.ENABLE_BETA_FEATURES"
            label="Use advanced suggestion algorithm"
            description="Use an AI-powered algorithm for hyper-personalized content suggestions based on watch history."
          />
        </div>
      </section>

      <!-- AI Provider Configuration (visible only when advanced algorithm is enabled) -->
      <transition name="ai-card">
        <section
          v-if="localConfig.ENABLE_ADVANCED_ALGORITHM && localConfig.ENABLE_BETA_FEATURES"
          class="advanced-subsection ai-group"
        >
          <h3>
            <i class="fas fa-robot"></i>
            AI Provider Configuration
            <button class="info-btn" @click="showAiInfoModal = true" title="Learn how to configure AI providers">
              <i class="fas fa-circle-info"></i>
            </button>
          </h3>

          <div class="form-group">
            <label for="openaiApiKey">
              API Key
              <span class="optional-tag">Optional</span>
            </label>
            <input
              id="openaiApiKey"
              v-model="localConfig.OPENAI_API_KEY"
              type="password"
              placeholder="sk-..."
              class="form-control"
              :disabled="isLoading"
            />
            <small class="form-help">
              Required for OpenAI and hosted providers. For local providers like Ollama or LM Studio, you can use any placeholder value (for example <code>sk-local</code>).
            </small>
          </div>

          <div class="form-group">
            <label for="llmModel">Model</label>
            <input
              id="llmModel"
              v-model="localConfig.LLM_MODEL"
              type="text"
              placeholder="gpt-4o-mini"
              class="form-control"
              :disabled="isLoading"
            />
            <small class="form-help">
              The model name to use. For Ollama use the local model tag (for example <code>llama3.1</code>). For LM Studio use the loaded model identifier.
            </small>
          </div>

          <div class="form-group">
            <label for="openaiBaseUrl">
              Base URL
              <span class="optional-tag">Optional</span>
            </label>
            <input
              id="openaiBaseUrl"
              v-model="localConfig.OPENAI_BASE_URL"
              type="text"
              placeholder="https://api.openai.com/v1"
              class="form-control"
              :disabled="isLoading"
            />
            <small class="form-help">
              Leave blank for OpenAI. Set to <code>http://localhost:11434/v1</code> for Ollama, <code>http://localhost:1234/v1</code> for LM Studio, or your LiteLLM/OpenRouter endpoint.
            </small>
          </div>

          <div class="ai-advanced-section">
            <button
              type="button"
              class="ai-advanced-toggle"
              :aria-expanded="aiAdvancedExpanded.toString()"
              aria-controls="ai-advanced-settings"
              @click="aiAdvancedExpanded = !aiAdvancedExpanded"
            >
              <span class="ai-advanced-icon"><i class="fas fa-sliders-h"></i></span>
              <span class="ai-advanced-copy">
                <span class="ai-advanced-title">Advanced AI settings</span>
                <span class="ai-advanced-summary">Temperature, reasoning effort, and web search</span>
              </span>
              <i class="fas fa-chevron-right ai-advanced-chevron" :class="{ expanded: aiAdvancedExpanded }"></i>
            </button>

            <transition name="ai-advanced-slide">
              <div id="ai-advanced-settings" class="ai-advanced-content" v-show="aiAdvancedExpanded">
                <div class="form-group">
                  <label for="llmTemperature">Temperature</label>
                  <input
                    id="llmTemperature"
                    v-model.trim="localConfig.LLM_TEMPERATURE"
                    type="text"
                    inputmode="decimal"
                    placeholder="legacy"
                    class="form-control"
                    :disabled="isLoading"
                  />
                  <small class="form-help">
                    Use <code>legacy</code> to keep current behavior (0.7 for recommendations, 0.8 for AI Search). Clear and save to omit the parameter, or enter a value from 0 to 2.
                  </small>
                </div>

                <div class="form-group">
                  <BaseDropdown
                    v-model="localConfig.LLM_REASONING_EFFORT"
                    :options="reasoningEffortOptions"
                    label="Reasoning effort"
                    :disabled="isLoading"
                    id="llmReasoningEffort"
                  />
                  <small class="form-help">
                    Sent only to direct OpenAI GPT-5 and o-series models. Other OpenAI-compatible provider/model combinations omit it.
                  </small>
                </div>

                <div class="form-group">
                  <label for="searxngBaseUrl">
                    SearXNG Base URL
                    <span class="optional-tag">Optional</span>
                  </label>
                  <input
                    id="searxngBaseUrl"
                    v-model.trim="localConfig.SEARXNG_BASE_URL"
                    type="url"
                    placeholder="http://searxng:8080"
                    class="form-control"
                    :disabled="isLoading"
                  />
                  <small class="form-help">
                    Optional self-hosted SearXNG instance. Its top three JSON search results add current context to AI Search and AI recommendations; leave blank to disable it.
                  </small>
                </div>
              </div>
            </transition>
          </div>

          <div class="form-group">
            <button
              @click="testLlmConnection"
              class="btn btn-outline btn-sm"
              :disabled="isLoading || isTestingLlm"
            >
              <i :class="isTestingLlm ? 'fas fa-spinner fa-spin' : 'fas fa-plug'"></i>
              {{ isTestingLlm ? 'Testing...' : 'Test Connection' }}
            </button>
          </div>
        </section>
      </transition>
      </SettingsPanel>

      <!-- AI Info Modal -->
      <teleport to="body">
        <transition name="modal-fade">
          <div v-if="showAiInfoModal" class="modal-overlay" @click.self="showAiInfoModal = false">
            <div class="modal-box">
              <div class="modal-header">
                <h3><i class="fas fa-robot"></i> AI Provider Setup Guide</h3>
                <button class="modal-close" @click="showAiInfoModal = false">
                  <i class="fas fa-times"></i>
                </button>
              </div>
              <div class="modal-body">
                <p class="modal-intro">
                  SuggestArr uses any <strong>OpenAI-compatible API</strong> to generate personalized recommendations based on your watch history. You can use a cloud provider or a local LLM running on your machine.
                </p>

                <div class="provider-tabs" role="tablist" aria-label="AI Providers">
                  <button
                    class="provider-tab"
                    :class="{ active: activeAiGuideTab === 'openai' }"
                    role="tab"
                    :aria-selected="activeAiGuideTab === 'openai'"
                    @click="activeAiGuideTab = 'openai'"
                  >
                    OpenAI
                  </button>
                  <button
                    class="provider-tab"
                    :class="{ active: activeAiGuideTab === 'ollama' }"
                    role="tab"
                    :aria-selected="activeAiGuideTab === 'ollama'"
                    @click="activeAiGuideTab = 'ollama'"
                  >
                    Ollama
                  </button>
                  <button
                    class="provider-tab"
                    :class="{ active: activeAiGuideTab === 'lmstudio' }"
                    role="tab"
                    :aria-selected="activeAiGuideTab === 'lmstudio'"
                    @click="activeAiGuideTab = 'lmstudio'"
                  >
                    LM Studio
                  </button>
                  <button
                    class="provider-tab"
                    :class="{ active: activeAiGuideTab === 'gemini' }"
                    role="tab"
                    :aria-selected="activeAiGuideTab === 'gemini'"
                    @click="activeAiGuideTab = 'gemini'"
                  >
                    Gemini
                  </button>
                  <button
                    class="provider-tab"
                    :class="{ active: activeAiGuideTab === 'litellm' }"
                    role="tab"
                    :aria-selected="activeAiGuideTab === 'litellm'"
                    @click="activeAiGuideTab = 'litellm'"
                  >
                    LiteLLM
                  </button>
                </div>

                <div class="provider-panel" role="tabpanel" v-if="activeAiGuideTab === 'openai'">
                  <div class="provider-card">
                    <div class="provider-name"><i class="fas fa-cloud"></i> OpenAI</div>
                    <ol class="provider-steps">
                      <li>Create an API key in your OpenAI account.</li>
                      <li>Use a model that supports chat completions, such as <code>gpt-4o-mini</code>.</li>
                      <li>Leave Base URL empty to use the default OpenAI endpoint.</li>
                    </ol>
                    <pre class="provider-code" aria-label="OpenAI config example"><code>OPENAI_API_KEY=sk-proj-...
OPENAI_BASE_URL=
LLM_MODEL=gpt-4o-mini</code></pre>
                  </div>
                </div>

                <div class="provider-panel" role="tabpanel" v-else-if="activeAiGuideTab === 'ollama'">
                  <div class="provider-card provider-card--local">
                    <div class="provider-name"><i class="fas fa-server"></i> Ollama <span class="badge-local">Local</span></div>
                    <ol class="provider-steps">
                      <li>Install and run Ollama on your machine.</li>
                      <li>Pull a model (example: <code>ollama pull llama3.1</code>).</li>
                      <li>Set Base URL to <code>http://localhost:11434/v1</code> and model to your local model name.</li>
                    </ol>
                    <pre class="provider-code" aria-label="Ollama config example"><code>OPENAI_API_KEY=sk-local
OPENAI_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1</code></pre>
                    <pre class="provider-code provider-code--scroll" aria-label="Ollama docker example"><code>docker run --rm -it \
  -p 11434:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama</code></pre>
                  </div>
                </div>

                <div class="provider-panel" role="tabpanel" v-else-if="activeAiGuideTab === 'lmstudio'">
                  <div class="provider-card provider-card--local">
                    <div class="provider-name"><i class="fas fa-laptop-code"></i> LM Studio <span class="badge-local">Local</span></div>
                    <ol class="provider-steps">
                      <li>Run LM Studio.</li>
                      <li>Start the OpenAI-compatible server from LM Studio.</li>
                      <li>Use Base URL <code>http://localhost:1234/v1</code>.</li>
                      <li>Use any dummy API key, for example <code>sk-local</code>.</li>
                    </ol>
                    <pre class="provider-code" aria-label="LM Studio config example"><code>OPENAI_API_KEY=sk-local
OPENAI_BASE_URL=http://localhost:1234/v1
LLM_MODEL=your-loaded-model</code></pre>
                    <small class="provider-note">
                      SuggestArr automatically falls back if a provider rejects
                      <code>response_format={"type":"json_object"}</code>, so LM Studio works without requiring a LiteLLM proxy.
                    </small>
                  </div>
                </div>

                <div class="provider-panel" role="tabpanel" v-else-if="activeAiGuideTab === 'gemini'">
                  <div class="provider-card">
                    <div class="provider-name"><i class="fas fa-gem"></i> Google Gemini</div>
                    <p class="provider-description">
                      Use Google's Gemini API through its OpenAI-compatible endpoint.
                    </p>
                    <ol class="provider-steps">
                      <li>Create an API key in Google AI Studio.</li>
                      <li>Paste the API key into SuggestArr.</li>
                      <li>Use the Gemini OpenAI-compatible base URL shown below.</li>
                    </ol>
                    <pre class="provider-code" aria-label="Gemini config example"><code>OPENAI_API_KEY=AIza...
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.0-flash</code></pre>
                    <small class="provider-note">Generate keys at <a href="https://aistudio.google.com/" target="_blank" rel="noopener">Google AI Studio</a>.</small>
                  </div>
                </div>

                <div class="provider-panel" role="tabpanel" v-else>
                  <div class="provider-card">
                    <div class="provider-name"><i class="fas fa-exchange-alt"></i> LiteLLM Proxy <span class="badge-advanced">Advanced</span></div>
                    <ol class="provider-steps">
                      <li>Run LiteLLM proxy with your provider mappings.</li>
                      <li>Set SuggestArr Base URL to the proxy endpoint.</li>
                      <li>Use the model alias configured in LiteLLM.</li>
                    </ol>
                    <pre class="provider-code" aria-label="LiteLLM config example"><code>OPENAI_API_KEY=sk-your-proxy-key
OPENAI_BASE_URL=http://localhost:4000/v1
LLM_MODEL=gpt-4o-mini</code></pre>
                    <pre class="provider-code provider-code--scroll" aria-label="LiteLLM docker example"><code>docker run --rm -it \
  -p 4000:4000 \
  -v ./litellm_config.yaml:/app/config.yaml \
  ghcr.io/berriai/litellm:main-latest \
  --config /app/config.yaml</code></pre>
                  </div>
                </div>

                <div class="modal-tip">
                  <i class="fas fa-lightbulb"></i>
                  <span>The system sends your watch history to the LLM and receives a ranked list of recommendations with reasoning. No personal data is stored by the provider beyond your API usage.</span>
                </div>
              </div>
              <div class="modal-footer">
                <button class="btn btn-outline btn-sm" @click="showAiInfoModal = false">
                  Close
                </button>
              </div>
            </div>
          </div>
        </transition>
      </teleport>

      <SettingsPanel
        panel-id="diagnostics-performance"
        title="Diagnostics & Performance"
        description="Logging, visual performance, monitoring, and TMDb cache controls."
        icon="fas fa-tachometer-alt"
      >
      <div class="advanced-subsection-grid">
      <!-- Debug Settings -->
      <section class="advanced-subsection">
        <h3>
          <i class="fas fa-bug"></i>
          Debug & Appearance
        </h3>

        <div class="form-group">
          <BaseDropdown
            v-model="localConfig.LOG_LEVEL"
            :options="logLevelOptions"
            label="Log Level"
            :disabled="isLoading"
            id="logLevel"
          />
          <small class="form-help">Set the verbosity of application logs</small>
        </div>

        <div class="form-group">
          <BaseCheckbox
            v-model="localConfig.ENABLE_DEBUG_MODE"
            :disabled="isLoading"
            label="Enable debug mode"
            description="Enable detailed logging and debugging information"
          />
        </div>

        <div class="form-group">
          <BaseCheckbox
            v-model="localConfig.ENABLE_PERFORMANCE_MONITORING"
            :disabled="isLoading"
            label="Enable performance monitoring"
            description="Track performance metrics for optimization"
          />
        </div>

        <div class="form-group">
          <BaseCheckbox
            :model-value="!localConfig.ENABLE_VISUAL_EFFECTS"
            @update:model-value="localConfig.ENABLE_VISUAL_EFFECTS = !$event"
            :disabled="isLoading"
            label="Disable visual effects (blur)"
            description="Check this box to improve UI performance and frame rates by turning off heavy CSS background blurs."
          />
        </div>

        <div class="form-group">
          <BaseCheckbox
            v-model="localConfig.ENABLE_STATIC_BACKGROUND"
            :disabled="isLoading"
            label="Enable static colored background"
            description="Override the app's default rotating background pictures with a static color."
          />
        </div>

        <div class="form-group" v-if="localConfig.ENABLE_STATIC_BACKGROUND">
          <label for="staticBackgroundColor">Static Background Color (Hex)</label>
          <div class="color-input-row">
            <input
              id="staticBackgroundColor"
              v-model="localConfig.STATIC_BACKGROUND_COLOR"
              type="color"
              class="form-control color-swatch-input"
              :disabled="isLoading"
            />
            <input
              v-model="localConfig.STATIC_BACKGROUND_COLOR"
              type="text"
              placeholder="#2E3440"
              class="form-control"
              pattern="^#[0-9A-Fa-f]{6}$"
              title="Must be a valid hex color code (e.g. #FF0000)"
              :disabled="isLoading"
            />
          </div>
        </div>
      </section>

      <!-- Cache Settings -->
      <section class="advanced-subsection">
        <h3>
          <i class="fas fa-memory"></i>
          Cache Settings
        </h3>

        <div class="form-group">
          <label for="cacheTtl">Cache TTL (hours)</label>
          <input
            id="cacheTtl"
            v-model.number="localConfig.CACHE_TTL"
            type="number"
            min="1"
            max="168"
            placeholder="24"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">
            How long to cache API responses and data (1-168 hours)
          </small>
        </div>

        <div class="form-group">
          <label for="maxCacheSize">Max Cache Size (MB)</label>
          <input
            id="maxCacheSize"
            v-model.number="localConfig.MAX_CACHE_SIZE"
            type="number"
            min="10"
            max="1024"
            placeholder="100"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">
            Maximum cache size in megabytes (10-1024 MB)
          </small>
        </div>

        <div class="form-group">
          <BaseCheckbox
            v-model="localConfig.ENABLE_API_CACHING"
            :disabled="isLoading"
            label="Enable TMDb response caching"
            description="Cache repeated TMDb metadata requests to reduce external API calls"
          />
        </div>

        <div class="form-group">
          <button
            @click="clearCache"
            class="btn btn-outline btn-sm"
            :disabled="isLoading"
          >
            <i class="fas fa-trash"></i>
            Clear Cache
          </button>
          <small class="form-help">
            Clear cached TMDb metadata and force fresh API calls
          </small>
        </div>
      </section>
      </div>
      </SettingsPanel>

      <!-- Request Workflow -->
      <SettingsPanel
        panel-id="request-workflow"
        title="Request Workflow"
        description="Approvals, request visibility, job pauses, and pending-suggestion retention."
        icon="fas fa-user-check"
      >
      <div class="request-workflow-settings">
        <section class="workflow-card workflow-card--approval">
          <div class="workflow-card__header">
            <span class="workflow-card__icon"><i class="fas fa-check-double"></i></span>
            <span>
              <strong>Approval flow</strong>
              <small>Control when suggestions can leave SuggestArr and reach Seer.</small>
            </span>
          </div>

          <div class="workflow-card__body">
            <div class="workflow-option">
              <BaseCheckbox
                v-model="localConfig.REQUIRE_REQUEST_APPROVAL"
                :disabled="isLoading"
                label="Require approval before delivery"
                description="Hold new suggestions in SuggestArr until an administrator approves them."
              />
            </div>

            <div class="workflow-option">
              <BaseCheckbox
                v-model="localConfig.PAUSE_JOBS_WITH_PENDING_APPROVALS"
                :disabled="isLoading"
                label="Pause jobs while approvals are pending"
                description="Prevent automation from adding more suggestions until the current queue is reviewed."
              />
            </div>
          </div>
        </section>

        <section class="workflow-card">
          <div class="workflow-card__header">
            <span class="workflow-card__icon"><i class="fas fa-users"></i></span>
            <span>
              <strong>Review policy</strong>
              <small>Choose who can see requests and how long pending items remain open.</small>
            </span>
          </div>

          <div class="workflow-card__body workflow-card__body--fields">
            <div class="workflow-setting">
              <label class="workflow-setting__label" for="requestVisibility">Regular-user visibility</label>
              <BaseDropdown
                v-model="localConfig.REQUEST_VISIBILITY"
                :options="requestVisibilityOptions"
                :disabled="isLoading"
                id="requestVisibility"
              />
              <p class="workflow-setting__help">
                Admins always see everything. Other users can be limited to requests from their linked media account.
              </p>
            </div>

            <div class="workflow-setting">
              <span class="workflow-setting__label-row">
                <label class="workflow-setting__label" for="autoRejectApprovalDays">Pending retention</label>
                <span class="workflow-setting__range">0–365 days</span>
              </span>
              <input
                id="autoRejectApprovalDays"
                v-model.number="localConfig.AUTO_REJECT_APPROVAL_DAYS"
                type="number"
                min="0"
                max="365"
                class="form-control"
                :disabled="isLoading"
              />
              <p class="workflow-setting__help">
                Automatically reject older pending suggestions. Use 0 to keep them until manual review.
              </p>
            </div>
          </div>
        </section>
      </div>
      </SettingsPanel>

      <SettingsPanel
        panel-id="application-maintenance"
        title="Application & Maintenance"
        description="Authentication, reverse-proxy routing, backups, imports, and reset controls."
        icon="fas fa-gear"
      >
      <div class="advanced-subsection-grid advanced-subsection-grid--application">
      <section class="advanced-subsection">
        <h3>
          <i class="fas fa-shield-alt"></i>
          Access & Routing
        </h3>

        <BaseDropdown
          v-model="localConfig.AUTH_MODE"
          :options="authModeOptions"
          label="Authentication Mode"
          :disabled="isLoading"
          id="authMode"
        />

        <p class="section-description">
          Choose how users access SuggestArr. You can require login for everyone, allow trusted local networks to bypass login, or disable authentication.
        </p>

        <div v-if="localConfig.AUTH_MODE === 'disabled'" class="warning-box warning-box--auth">
          <i class="fas fa-exclamation-triangle"></i>
          <div>
            <strong>Warning:</strong>
            <p>
              Authentication will be completely disabled. This should only be used in trusted environments.
            </p>
          </div>
        </div>

        <div v-else-if="localConfig.AUTH_MODE === 'local_bypass'" class="warning-box warning-box--auth">
          <i class="fas fa-exclamation-triangle"></i>
          <div>
            <strong>Warning:</strong>
            <p>
              Requests from trusted local networks will bypass authentication.
            </p>
          </div>
        </div>

        <div v-if="localConfig.AUTH_MODE === 'local_bypass'" class="form-group">
          <label for="authTrustedCidrs">Trusted CIDRs</label>
          <input
            id="authTrustedCidrs"
            v-model="localConfig.AUTH_TRUSTED_CIDRS"
            type="text"
            placeholder="127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">
            Comma-separated CIDR ranges that can bypass auth when mode is <code>local_bypass</code>.
          </small>
        </div>

        <div v-if="localConfig.AUTH_MODE === 'local_bypass' || localConfig.AUTH_MODE === 'disabled'" class="form-group">
          <label for="authBypassUsername">Bypass Username</label>
          <input
            id="authBypassUsername"
            v-model="localConfig.AUTH_BYPASS_USERNAME"
            type="text"
            placeholder="local_admin"
            class="form-control"
            :disabled="isLoading"
          />
          <small class="form-help">
            Username used as internal request context when auth is bypassed.
          </small>
        </div>

        <div class="form-group">
          <label for="subpath">Subpath</label>
          <input id="subpath" v-model="localConfig.SUBPATH" type="text" placeholder="/suggestarr" class="form-control"
            :disabled="isLoading" />
          <small class="form-help">
            Subpath for running SuggestArr under a subdirectory (e.g., "/suggestarr"). Leave empty for root.
          </small>
        </div>
      </section>

      <section class="advanced-subsection configuration-management">
        <h3>
          <i class="fas fa-file-export"></i>
          Configuration Management
        </h3>
        <p class="section-description">
          Back up, restore, or reset the complete SuggestArr configuration.
        </p>
        <div class="configuration-actions">
          <article class="configuration-action">
            <span class="configuration-action__icon"><i class="fas fa-download"></i></span>
            <span class="configuration-action__copy">
              <strong>Export a backup</strong>
              <small>Download the current SuggestArr configuration for safekeeping or migration.</small>
            </span>
            <button class="btn btn-outline btn-sm" :disabled="isLoading" @click="$emit('export-config')">
              Export
            </button>
          </article>

          <article class="configuration-action">
            <span class="configuration-action__icon"><i class="fas fa-upload"></i></span>
            <span class="configuration-action__copy">
              <strong>Restore a backup</strong>
              <small>Import a previously exported configuration into this instance.</small>
            </span>
            <button class="btn btn-outline btn-sm" :disabled="isLoading" @click="$emit('import-config')">
              Import
            </button>
          </article>

          <article class="configuration-action configuration-action--danger">
            <span class="configuration-action__icon"><i class="fas fa-undo"></i></span>
            <span class="configuration-action__copy">
              <strong>Reset SuggestArr</strong>
              <small>Discard the current configuration and return application settings to their defaults.</small>
            </span>
            <button class="btn btn-danger btn-sm" :disabled="isLoading" @click="$emit('reset-config')">
              Reset
            </button>
          </article>
        </div>

        <div class="configuration-note">
          <i class="fas fa-lock"></i>
          <span>Configuration backups may contain service credentials. Store exported files securely.</span>
        </div>
      </section>
      </div>
      </SettingsPanel>

      <SettingsWebhooks />
      <SettingsCleanup embedded />
    </div>



    <!-- Save Button -->
    <div class="settings-actions">
      <button
        @click="saveSettings"
        class="btn btn-primary"
        :disabled="isLoading || !hasChanges"
      >
        <i class="fas fa-save"></i>
        {{ isLoading ? 'Saving...' : 'Save Changes' }}
      </button>

      <button
        @click="resetToDefaults"
        class="btn btn-outline"
        :disabled="isLoading"
      >
        <i class="fas fa-undo"></i>
        Reset to Defaults
      </button>
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import BaseDropdown from '@/components/common/BaseDropdown.vue';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import SettingsCleanup from './SettingsCleanup.vue';
import SettingsPanel from './SettingsPanel.vue';
import SettingsWebhooks from './SettingsWebhooks.vue';

export default {
  name: 'SettingsAdvanced',
  components: {
    BaseDropdown,
    BaseCheckbox,
    SettingsCleanup,
    SettingsPanel,
    SettingsWebhooks,
  },
  props: {
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
        { value: 'all', label: 'All requests' },
        { value: 'own', label: 'Own linked account only' },
      ]
    };
  },
  computed: {
    hasChanges() {
      return JSON.stringify(this.localConfig) !== JSON.stringify(this.originalConfig);
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
        this.originalConfig = { ...this.localConfig };

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
          PAUSE_JOBS_WITH_PENDING_APPROVALS: false,
          AUTO_REJECT_APPROVAL_DAYS: 0,
          ENABLE_BETA_FEATURES: false,
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
      },
    },
  },
  mounted() {
    this.loadUsers();
  },
  methods: {
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
            REQUEST_VISIBILITY: this.localConfig.REQUEST_VISIBILITY === 'own' ? 'own' : 'all',
            PAUSE_JOBS_WITH_PENDING_APPROVALS: this.localConfig.PAUSE_JOBS_WITH_PENDING_APPROVALS === true,
            AUTO_REJECT_APPROVAL_DAYS: Math.max(0, Number(this.localConfig.AUTO_REJECT_APPROVAL_DAYS) || 0),
            ENABLE_BETA_FEATURES: this.localConfig.ENABLE_BETA_FEATURES || false,
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
          this.$toast.success('AI connection successful!');
        } else {
          this.$toast.error(response.data.message || 'Connection failed');
        }
      } catch (error) {
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
        ENABLE_BETA_FEATURES: false,
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

<style scoped>
.settings-advanced {
  color: var(--color-text-primary);
  padding: var(--spacing-lg);
}

.section-header {
  margin-bottom: 2rem;
}

.section-header h2 {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
  color: var(--color-text-primary);
}

.section-header p {
  color: var(--color-text-muted);
  font-size: 1rem;
}

.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

.advanced-subsection-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--spacing-lg);
}

.advanced-subsection {
  min-width: 0;
  padding: var(--spacing-lg);
  background: var(--surface-glass-subtle);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.advanced-subsection + .advanced-subsection {
  margin-top: var(--spacing-lg);
}

.advanced-subsection-grid .advanced-subsection + .advanced-subsection {
  margin-top: 0;
}

.advanced-subsection.experimental {
  background: var(--color-warning-alpha-10);
  border-color: var(--color-warning);
}

.settings-group {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--border-radius-md);
  padding: 1.5rem;
}

.settings-group h3 {
  font-size: 1.2rem;
  margin-bottom: 1rem;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label:not(.base-checkbox) {
  display: block;
  margin-bottom: var(--spacing-xs);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  line-height: var(--line-height-normal);
}

.form-control {
  box-sizing: border-box;
  width: 100%;
  padding: 0.75rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-primary);
  font-size: 1rem;
  transition: var(--transition-base);
}

.settings-group > :deep(.form-group-modern) {
  margin-bottom: var(--spacing-lg);
}

.form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  background: var(--color-bg-active);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-help {
  display: block;
  margin-top: var(--spacing-2xs);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  line-height: var(--line-height-normal);
}

.color-input-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-sm);
}

.color-swatch-input {
  flex: 0 0 var(--input-height-lg);
  width: var(--input-height-lg);
  height: var(--input-height-md);
  padding: var(--spacing-2xs);
  cursor: pointer;
}

.request-workflow-settings {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--spacing-lg);
}

.workflow-card {
  min-width: 0;
  padding: var(--spacing-lg);
  background: var(--surface-glass-subtle);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.workflow-card--approval {
  background: var(--color-primary-alpha-10);
  border-color: var(--color-primary);
}

.workflow-card__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.workflow-card__icon {
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

.workflow-card__header strong,
.workflow-card__header small {
  display: block;
}

.workflow-card__header strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
}

.workflow-card__header small {
  margin-top: var(--spacing-xs);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-normal);
}

.workflow-card__body {
  display: grid;
  gap: var(--spacing-sm);
}

.workflow-card__body--fields {
  gap: var(--spacing-lg);
}

.workflow-option {
  padding: var(--spacing-md);
  background: var(--surface-raised);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
}

.request-workflow-settings .workflow-setting {
  display: grid;
  gap: var(--spacing-sm);
  margin: 0;
}

.request-workflow-settings .workflow-setting__label {
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-normal);
}

.workflow-setting__label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
}

.workflow-setting__range {
  padding: var(--spacing-2xs) var(--spacing-sm);
  color: var(--color-text-muted);
  background: var(--surface-interactive);
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}

.request-workflow-settings .workflow-setting__help {
  margin: var(--spacing-2xs) 0 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-normal);
}

.request-workflow-settings .form-control,
.request-workflow-settings :deep(.value-text),
.request-workflow-settings :deep(.placeholder-text) {
  font-size: var(--font-size-sm);
}

.request-workflow-settings :deep(.base-checkbox) {
  width: 100%;
}

.section-description {
  margin: 0 0 1rem;
  font-size: 0.9rem;
  color: var(--color-text-muted);
  line-height: 1.5;
}

.configuration-actions {
  display: grid;
  gap: var(--spacing-sm);
}

.configuration-action {
  display: grid;
  grid-template-columns: var(--input-height-md) minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--surface-raised);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.configuration-action:hover {
  background: var(--surface-interactive);
  border-color: var(--color-border-medium);
}

.configuration-action--danger {
  background: var(--color-error-alpha-10);
  border-color: var(--color-error);
}

.configuration-action--danger:hover {
  background: var(--color-error-alpha-20);
  border-color: var(--color-error-light);
}

.configuration-action__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--input-height-md);
  height: var(--input-height-md);
  color: var(--color-primary-light);
  background: var(--surface-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.configuration-action--danger .configuration-action__icon {
  color: var(--color-error-light);
  background: var(--color-error-alpha-10);
  border-color: var(--color-error);
}

.configuration-action__copy strong,
.configuration-action__copy small {
  display: block;
}

.configuration-action__copy strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
}

.configuration-action__copy small {
  margin-top: var(--spacing-xs);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-normal);
}

.configuration-note {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  color: var(--color-text-muted);
  background: var(--surface-interactive);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-normal);
}

.configuration-note i {
  margin-top: var(--spacing-2xs);
  color: var(--color-warning-light);
}

.warning-box {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: var(--border-radius-sm);
  padding: 1rem;
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.warning-box i {
  color: var(--color-warning);
  margin-top: 0.25rem;
  flex-shrink: 0;
}

.warning-box strong {
  color: var(--color-warning);
  display: block;
  margin-bottom: 0.5rem;
}

.warning-box p {
  color: #e5e7eb;
  margin: 0;
  line-height: 1.5;
}

.warning-box--auth {
  margin-top: 0.5rem;
  margin-bottom: 1rem;
  padding: 0.85rem;
}

.loading-users {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--color-text-muted);
  padding: 1rem;
  text-align: center;
}

.user-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 1rem;
  padding: 0.5rem;
  max-height: 400px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--border-radius-sm);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.user-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 1.25rem 1rem;
  background: rgba(255, 255, 255, 0.05);
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--border-radius-md);
  cursor: pointer;
  transition: var(--transition-base);
  position: relative;
  overflow: hidden;
}

.user-card:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: var(--color-border-light);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.user-card.selected {
  background: rgba(59, 130, 246, 0.2);
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.user-card.selected .user-avatar {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.user-card.selected .user-name {
  color: #60a5fa;
}

.user-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--color-bg-interactive);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid transparent;
  transition: var(--transition-base);
}

.user-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar i {
  color: var(--color-text-muted);
  font-size: 1.25rem;
}

.user-info {
  text-align: center;
  flex: 1;
  width: 100%;
}

.user-name {
  color: #e5e7eb;
  font-weight: 500;
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
  word-wrap: break-word;
  white-space: normal;
  line-height: 1.2;
  transition: color 0.3s ease;
}

.user-type {
  color: var(--color-text-muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  font-weight: 500;
}

.user-selection-indicator {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  width: 24px;
  height: 24px;
  background: var(--color-primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transform: scale(0.8);
  transition: var(--transition-base);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
}

.user-card.selected .user-selection-indicator {
  opacity: 1;
  transform: scale(1);
}

.user-selection-indicator i {
  color: white;
  font-size: 0.75rem;
}

.no-users {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  color: var(--color-text-muted);
  text-align: center;
}

.no-users i {
  font-size: 2rem;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.no-users p {
  margin: 0 0 0.5rem 0;
  font-weight: 500;
  color: #e5e7eb;
}

.no-users small {
  font-size: 0.875rem;
  opacity: 0.8;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: var(--border-radius-sm);
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition-base);
  border: none;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  font-size: 0.875rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.btn-outline {
  background: var(--color-bg-interactive);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-medium);
}

/* Disabled feature styling with blur effect */
.feature-disabled {
  opacity: 0.5;
  filter: blur(0.8px);
  pointer-events: none;
  transition: all 0.3s ease;
}

/* Feature wrapper for positioning */
.feature-wrapper {
  position: relative;
}

.btn-outline:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.5);
}

.btn-sm {
  padding: 0.375rem 0.75rem;
  font-size: 0.8125rem;
}

.settings-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  padding-top: 2rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

/* AI Provider card */
.advanced-subsection.ai-group {
  background: var(--color-primary-alpha-10);
  border-color: var(--color-primary);
}

.advanced-subsection.ai-group h3 {
  color: var(--color-primary-light);
}

.advanced-subsection.ai-group h3 i {
  color: var(--color-primary);
}

.ai-advanced-toggle {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  color: var(--color-text-primary);
  cursor: pointer;
  display: flex;
  font-family: var(--font-family-base);
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  text-align: left;
  transition: var(--transition-base);
  width: 100%;
}

.ai-advanced-section {
  background: var(--surface-glass-subtle);
  border: 1px solid var(--surface-glass-light);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-lg);
}

.ai-advanced-toggle:hover {
  background: var(--surface-glass-light);
}

.ai-advanced-icon {
  align-items: center;
  background: var(--color-primary-alpha-10);
  border-radius: var(--radius-sm);
  color: var(--color-primary);
  display: flex;
  justify-content: center;
  padding: var(--spacing-sm);
}

.ai-advanced-copy {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--spacing-2xs);
}

.ai-advanced-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}

.ai-advanced-summary {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.ai-advanced-chevron {
  color: var(--color-text-muted);
  margin-left: auto;
  transition: var(--transition-base);
}

.ai-advanced-chevron.expanded {
  transform: rotate(90deg);
}

.ai-advanced-content {
  padding: 0 var(--spacing-md) var(--spacing-md);
}

.ai-advanced-slide-enter-active,
.ai-advanced-slide-leave-active {
  overflow: hidden;
  transition: max-height var(--transition-base), opacity var(--transition-base), transform var(--transition-base);
}

.ai-advanced-slide-enter-from,
.ai-advanced-slide-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(calc(var(--spacing-sm) * -1));
}

.ai-advanced-slide-enter-to,
.ai-advanced-slide-leave-from {
  max-height: 100vh;
  opacity: 1;
  transform: translateY(0);
}

.optional-tag {
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--color-text-muted);
  background: rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  padding: 0.1rem 0.45rem;
  margin-left: 0.4rem;
  vertical-align: middle;
}

/* Transition for the AI card appearing in the grid */
.ai-card-enter-active,
.ai-card-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.ai-card-enter-from,
.ai-card-leave-to {
  opacity: 0;
  transform: scale(0.97) translateY(-8px);
}

.ai-card-enter-to,
.ai-card-leave-from {
  opacity: 1;
  transform: scale(1) translateY(0);
}

/* Info button next to AI section title */
.info-btn {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  color: #818cf8;
  font-size: 1rem;
  padding: 0.2rem 0.4rem;
  border-radius: 50%;
  transition: color 0.2s, background 0.2s;
  line-height: 1;
}

.info-btn:hover {
  color: #a5b4fc;
  background: rgba(165, 180, 252, 0.12);
}

/* Modal overlay */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 1rem;
}

.modal-box {
  background: #1e1e2e;
  border: 1px solid rgba(165, 180, 252, 0.3);
  border-radius: var(--border-radius-md);
  width: 100%;
  max-width: 700px;
  max-height: min(86vh, 820px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6);
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #a5b4fc;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.modal-close {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-muted);
  font-size: 1rem;
  padding: 0.35rem 0.5rem;
  border-radius: var(--border-radius-sm);
  transition: color 0.2s, background 0.2s;
}

.modal-close:hover {
  color: #e5e7eb;
  background: rgba(255, 255, 255, 0.08);
}

.modal-body {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  overflow-y: auto;
}

.modal-intro {
  color: #e5e7eb;
  line-height: 1.6;
  margin: 0;
  font-size: 0.95rem;
}

.provider-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.provider-tab {
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-muted);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: var(--border-radius-sm);
  padding: 0.4rem 0.7rem;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition-base);
}

.provider-tab:hover {
  color: #e5e7eb;
  border-color: rgba(165, 180, 252, 0.5);
}

.provider-tab.active {
  color: #e5e7eb;
  border-color: rgba(165, 180, 252, 0.65);
  background: rgba(99, 102, 241, 0.2);
}

.provider-panel {
  display: flex;
  flex-direction: column;
}

.provider-list,
.provider-steps {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.provider-steps {
  color: var(--color-text-muted);
  margin: 0 0 0.8rem;
  padding-left: 1.15rem;
  font-size: 0.9rem;
  line-height: 1.45;
}

.provider-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--border-radius-sm);
  padding: 0.9rem 1rem;
}

.provider-card--local {
  border-color: rgba(99, 102, 241, 0.35);
  background: rgba(99, 102, 241, 0.06);
}

.provider-name {
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 0.6rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.95rem;
}

.provider-name i {
  color: #818cf8;
}

.badge-local {
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(99, 102, 241, 0.25);
  color: #a5b4fc;
  border-radius: 8px;
  padding: 0.1rem 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.badge-advanced {
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(245, 158, 11, 0.22);
  color: #fbbf24;
  border-radius: 8px;
  padding: 0.1rem 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.provider-code {
  margin: 0;
  background: rgba(17, 24, 39, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  color: #d1d5db;
  padding: 0.75rem;
  font-size: 0.8rem;
  line-height: 1.4;
  overflow-x: auto;
}

.provider-code + .provider-code {
  margin-top: 0.6rem;
}

.provider-code--scroll {
  max-height: 140px;
  overflow-y: auto;
}

.provider-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.provider-table td {
  padding: 0.2rem 0.4rem;
  color: var(--color-text-muted);
}

.provider-table td:first-child {
  font-weight: 500;
  color: #9ca3af;
  width: 90px;
  white-space: nowrap;
}

.provider-table code {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  padding: 0.1rem 0.35rem;
  font-size: 0.8rem;
  color: #c4b5fd;
  font-family: monospace;
}

.provider-note {
  display: block;
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--color-text-muted);
  font-style: italic;
}

.modal-tip {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.2);
  border-radius: var(--border-radius-sm);
  padding: 0.85rem 1rem;
  font-size: 0.875rem;
  color: #fbbf24;
  line-height: 1.5;
}

.modal-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0.9rem 1.5rem 1.1rem;
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
}

.modal-tip i {
  margin-top: 0.1rem;
  flex-shrink: 0;
}

/* Modal transition */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

@media (max-width: 768px) {
  .settings-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .advanced-subsection-grid,
  .request-workflow-settings {
    grid-template-columns: 1fr;
  }

  .configuration-action {
    grid-template-columns: var(--input-height-md) minmax(0, 1fr);
  }

  .configuration-action .btn {
    grid-column: 2;
    justify-self: start;
  }

  .settings-group {
    padding: 1rem;
  }

  .warning-box {
    flex-direction: column;
    text-align: center;
  }

  .user-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.75rem;
    padding: 0.25rem;
    max-height: 300px;
  }

  .user-card {
    padding: 1rem 0.75rem;
  }

  .user-avatar {
    width: 40px;
    height: 40px;
  }

  .user-avatar i {
    font-size: 1rem;
  }

  .user-name {
    font-size: 0.8125rem;
  }

  .user-type {
    font-size: 0.6875rem;
  }

  .settings-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .modal-box {
    max-height: 92vh;
  }

  .modal-body {
    padding: 1rem;
  }

  .modal-header,
  .modal-footer {
    padding-left: 1rem;
    padding-right: 1rem;
  }
}
</style>
