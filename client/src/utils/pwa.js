/**
 * Register the service worker that makes SuggestArr installable as an app.
 * The path is relative so it also works under a configured subpath; development
 * builds skip it so Vite's hot reload is never intercepted.
 */
export function registerServiceWorker() {
  if (import.meta.env.DEV || !('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch((error) => {
      console.warn('Service worker registration failed:', error);
    });
  });
}
