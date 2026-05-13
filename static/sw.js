// sw.js — MindMath service worker (cache-first for static assets, network-only for Flask routes)

const CACHE = 'mindmath-v2';

const PRECACHE = [
  '/static/style.css',
  '/static/app.js',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/offline.html',
  '/static/js/rng.js',
  '/static/js/question_engine.js',
  '/static/js/sequence_engine.js',
  '/static/js/association_engine.js',
  '/static/data/associations_en.json',
  '/static/data/associations_de.json',
  '/static/data/associations_fr.json',
];

// ─── Install: pre-cache all static assets ────────────────────────────────────

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE).then(cache =>
      Promise.allSettled(
        PRECACHE.map(url =>
          cache.add(url).catch(err =>
            console.warn('[SW] precache failed:', url, err)
          )
        )
      )
    ).then(() => self.skipWaiting())
  );
});

// ─── Activate: delete old caches ─────────────────────────────────────────────

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE).map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ─── Fetch: cache-first for /static/, network-only for Flask routes ───────────

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Only handle same-origin requests
  if (url.origin !== self.location.origin) return;

  // Network-only for Flask API routes (game endpoints, form submissions)
  if (!url.pathname.startsWith('/static/')) {
    event.respondWith(
      fetch(event.request).catch(() =>
        caches.match('/static/offline.html')
      )
    );
    return;
  }

  // Cache-first for static assets
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(resp => {
        if (resp && resp.status === 200) {
          const clone = resp.clone();
          caches.open(CACHE).then(cache => cache.put(event.request, clone));
        }
        return resp;
      });
    })
  );
});
