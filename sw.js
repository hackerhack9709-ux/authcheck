/* PayCheck service worker — offline shell.
   Keeps a copy of the app shell so the app still opens without a network.
   Gateway API calls are never cached; those must always be live.

   Strategy: network-first for the shell. The cached copy is only a fallback
   when the network is unavailable. A stale-while-revalidate cache would keep
   serving the previous app.js after a deploy, so a bug fix could take two
   loads to reach users — unacceptable for a payment tool. */
const CACHE = 'paycheck-v3';
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

  // Network-first: always try the network so a fresh deploy is picked up
  // immediately. Fall back to the cache (then the shell) only when offline.
  e.respondWith(
    fetch(request)
      .then((res) => {
        if (res && res.ok && res.type === 'basic') {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(request, copy));
        }
        return res;
      })
      .catch(() => caches.match(request).then((hit) => hit || caches.match('./index.html')))
  );
});
