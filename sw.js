/* PayCheck service worker — offline shell.
   Caches the app shell so the app opens without a network.
   Never caches gateway API calls; those must always be live. */
const CACHE = 'paycheck-v2';
const SHELL = [
  './',
  './index.html',
  './styles.css',
  './icons.js',
  './app.js',
  './auth.js',
  './gateway.js',
  './share.js',
  './vendor/qrcode.min.js',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-512.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const { request } = e;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  // Only handle same-origin shell assets. Gateway endpoints go straight to the network.
  if (url.origin !== self.location.origin) return;

  // Stale-while-revalidate: serve the cached copy at once, then refresh it in
  // the background so the next load picks up a new deploy without a hard refresh.
  e.respondWith(
    caches.match(request).then((hit) => {
      const network = fetch(request)
        .then((res) => {
          if (res && res.ok && res.type === 'basic') {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(request, copy));
          }
          return res;
        })
        .catch(() => hit || caches.match('./index.html'));
      return hit || network;
    })
  );
});
