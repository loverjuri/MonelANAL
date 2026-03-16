/* MonelANAL Service Worker - basic caching */
const CACHE = 'monelanal-v1';

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((cache) => {
      return cache.addAll([
        './static/css/dark.css',
        './static/css/light.css',
        './static/manifest.json'
      ]).catch(() => {});
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (!url.pathname.includes('/static/')) return;
  e.respondWith(
    caches.match(e.request).then((cached) =>
      cached || fetch(e.request).then((r) => {
        const clone = r.clone();
        caches.open(CACHE).then((cache) => cache.put(e.request, clone));
        return r;
      })
    )
  );
});
