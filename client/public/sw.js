/*
 * SuggestArr service worker: makes the app installable and shows a short notice when the
 * server cannot be reached. It caches nothing, so an update is visible on the next load
 * and no API data or credentials are ever stored here.
 */
const OFFLINE_PAGE = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>SuggestArr is offline</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0b0d12;color:#e8eaf0;
font:16px system-ui,sans-serif;text-align:center;padding:24px}p{color:#9aa3b5}button{margin-top:12px;
padding:10px 18px;border:0;border-radius:10px;background:#6a5ae0;color:#fff;font-weight:700;cursor:pointer}</style>
</head><body><div><h1>SuggestArr is offline</h1><p>The server cannot be reached right now.</p>
<button onclick="location.reload()">Try again</button></div></body></html>`;

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

self.addEventListener('fetch', (event) => {
  // Only page loads get the offline notice; assets and API calls go straight to the network.
  if (event.request.mode !== 'navigate') return;
  event.respondWith(fetch(event.request).catch(() => new Response(OFFLINE_PAGE, {
    status: 503,
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  })));
});
