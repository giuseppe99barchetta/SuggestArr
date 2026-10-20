import { createApp, h, ref } from 'vue';
import AppDialog from '@/components/ui/AppDialog.vue';

/**
 * Asks a yes/no question in an AppDialog instead of the browser's native confirm().
 * Resolves true when the user confirms; Escape, the backdrop and Cancel resolve false.
 *
 * @param {Object} options
 * @param {string} options.title - Dialog heading.
 * @param {string} [options.message] - Body text.
 * @param {string} [options.confirmLabel='Confirm'] - Label of the confirming button.
 * @param {string} [options.cancelLabel='Cancel'] - Label of the dismissing button.
 * @param {boolean} [options.danger=false] - Red styling for destructive actions.
 * @returns {Promise<boolean>}
 */
export function confirmDialog({ title, message = '', confirmLabel = 'Confirm', cancelLabel = 'Cancel', danger = false }) {
  return new Promise((resolve) => {
    const host = document.createElement('div');
    document.body.appendChild(host);
    let answer = false;

    const app = createApp({
      setup() {
        const dialog = ref(null);
        const choose = (value) => {
          answer = value;
          dialog.value.close();
        };
        const onClose = () => {
          app.unmount();
          host.remove();
          resolve(answer);
        };
        return () => h(AppDialog, {
          ref: dialog,
          title,
          icon: danger ? 'fas fa-exclamation-triangle' : 'fas fa-question-circle',
          tone: danger ? 'danger' : '',
          onClose,
        }, {
          default: () => (message ? h('p', { class: 'm-0 text-sm leading-relaxed text-ink-2' }, message) : null),
          footer: () => [
            h('button', { type: 'button', class: 'ui-btn', onClick: () => choose(false) }, cancelLabel),
            h('button', { type: 'button', class: danger ? 'ui-btn-danger' : 'ui-btn-primary', onClick: () => choose(true) }, confirmLabel),
          ],
        });
      },
    });
    app.mount(host);
  });
}
