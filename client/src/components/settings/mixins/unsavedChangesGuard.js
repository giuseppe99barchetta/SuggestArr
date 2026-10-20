import { confirmDialog } from '@/utils/confirmDialog';

/**
 * Asks before leaving a settings page whose `hasChanges` computed is true.
 * Dashboard tabs switch by route param, so router navigation is guarded as well as closing the tab.
 * Inactive in the setup wizard, which keeps its own state across steps.
 */
export default {
  data() {
    return { removeLeaveGuard: null };
  },
  mounted() {
    if (this.wizardMode) return;
    window.addEventListener('beforeunload', this.warnBeforeUnload);
    // Mounted outside the app (component previews) there is no router to guard.
    if (!this.$router) return;
    this.removeLeaveGuard = this.$router.beforeEach(async () => {
      if (!this.hasChanges) return;
      const leave = await confirmDialog({
        title: 'Leave without saving?',
        message: 'Your changes on this page have not been saved.',
        confirmLabel: 'Discard changes',
        cancelLabel: 'Keep editing',
        danger: true,
      });
      if (!leave) return false;
    });
  },
  beforeUnmount() {
    if (this.removeLeaveGuard) this.removeLeaveGuard();
    window.removeEventListener('beforeunload', this.warnBeforeUnload);
  },
  methods: {
    warnBeforeUnload(event) {
      if (this.hasChanges) event.preventDefault();
    },
  },
};
