<template>
  <div :class="wizardMode ? '' : 'min-w-0 px-5 py-4 max-sm:px-4'">
    <ServiceCardHeader v-if="!wizardMode" icon="fas fa-history" title="Trakt" description="Adds Trakt watch history and personal recommendations. Users link their own accounts from their profile." :status="getTraktStatus" :status-text="getTraktStatusText" :folded="isFolded(getTraktStatus)" @toggle="editing = !editing" />
    <div v-show="!isFolded(getTraktStatus)">
      <div class="min-w-0">
        <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
          <label for="traktClientId">Client ID</label>
          <input
            id="traktClientId"
            v-model="localConfig.TRAKT_CLIENT_ID"
            type="text"
            placeholder="Enter your Trakt Client ID"
            class="ui-input"
            :disabled="isLoading"
          />
        </div>
        <div class="mb-4 flex flex-col gap-1.5 last:mb-0 [&>label]:text-[13px] [&>label]:font-semibold [&>label]:text-ink-2">
          <label for="traktClientSecret">Client Secret (optional)</label>
          <div class="flex gap-2">
            <input
              id="traktClientSecret"
              v-model="localConfig.TRAKT_CLIENT_SECRET"
              :type="showTraktClientSecret ? 'text' : 'password'"
              placeholder="Optional for legacy Trakt apps"
              class="ui-input"
              :disabled="isLoading"
            />
            <button @click="showTraktClientSecret = !showTraktClientSecret" type="button" :aria-label="showTraktClientSecret ? 'Hide Trakt client secret' : 'Show Trakt client secret'" :aria-pressed="showTraktClientSecret.toString()" class="ui-btn w-[42px] shrink-0 px-0" :disabled="isLoading">
              <i aria-hidden="true" :class="showTraktClientSecret ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
            </button>
          </div>
          <small class="text-xs leading-normal text-ink-4">
            Create an app at <a href="https://developer.trakt.tv/apps/new" target="_blank" rel="noopener noreferrer" class="text-brand-ink no-underline hover:underline">Trakt Developer</a> with <code>urn:ietf:wg:oauth:2.0:oob</code> as Redirect URI (ignore the insecure-URI warning) and leave Allowed origins empty. New Trakt apps use the Client ID without issuing a Client Secret.
          </small>
        </div>
        <div class="mt-3 flex items-center gap-2 text-[13px] font-semibold text-good" v-if="isTraktAppConfigured">
          <i aria-hidden="true" class="fas fa-check-circle"></i>
          Trakt app credentials configured. Users can link their own Trakt accounts from their profile.
        </div>
        <BaseCheckbox
          v-if="!wizardMode"
          v-model="localConfig.TRAKT_SYNC_SEEN_FEEDBACK"
          class="mt-4"
          label="Send &quot;Seen it&quot; to Trakt"
          description="Users with a linked Trakt account rate titles they have seen with 1 to 10 stars, and the rating and play are added to their Trakt account."
          :disabled="isLoading || !localConfig.TRAKT_CLIENT_ID"
        />
      </div>
    </div>
  </div>
</template>

<script>
import ServiceCardHeader from '../ServiceCardHeader.vue';
import BaseCheckbox from '@/components/common/BaseCheckbox.vue';
import serviceCard from './serviceCard.js';

/**
 * Trakt app credentials; users link their own accounts from their profile.
 * Shares the page's settings through the `serviceCard` mixin; saving stays in SettingsServices.
 */
export default {
  name: 'TraktCard',
  mixins: [serviceCard],
  components: { ServiceCardHeader, BaseCheckbox },
  data() {
    return {
      showTraktClientSecret: false,
    };
  },
  computed: {
    isTraktAppConfigured() {
      return !!this.localConfig.TRAKT_CLIENT_ID;
    },
    getTraktStatus() {
      if (this.isTraktAppConfigured) return 'status-connected';
      if (this.localConfig.TRAKT_CLIENT_ID || this.localConfig.TRAKT_CLIENT_SECRET) return 'status-warning';
      return 'status-disconnected';
    },
    getTraktStatusText() {
      if (this.isTraktAppConfigured) return 'Configured';
      if (this.localConfig.TRAKT_CLIENT_ID || this.localConfig.TRAKT_CLIENT_SECRET) return 'Incomplete';
      return 'Not set';
    },
  },
  watch: {
    isTraktAppConfigured(val) {
      this.emitValidation('trakt', val);
    },
  },
};
</script>
