/**
 * Shared wiring for the service cards of SettingsServices.
 *
 * The page provides itself as `services`; cards read and write the page's `localConfig`
 * (so saving and "unsaved changes" keep working in one place) and report wizard-step
 * validation through the page's events. A card may define `onReset()` to forget
 * connection state when the page resets all services.
 */
export default {
  inject: ['services'],
  computed: {
    localConfig() {
      return this.services.localConfig;
    },
    isLoading() {
      return this.services.isLoading;
    },
    wizardMode() {
      return this.services.wizardMode;
    },
    wizardSection() {
      return this.services.wizardSection;
    },
  },
  watch: {
    'services.resetCount'() {
      this.onReset?.();
    },
  },
  methods: {
    _notifyError(message, opts = { position: 'top-right', duration: 5000 }) {
      this.$toast.error(message, opts);
    },
    /** Tell the setup wizard whether its current step is complete. */
    emitValidation(section, valid) {
      if (this.wizardMode && this.wizardSection === section) {
        this.services.$emit('validation-changed', valid);
      }
    },
  },
};
