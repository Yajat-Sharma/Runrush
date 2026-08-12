/*
 * RunRush Service Worker
 * Provides offline caching and background sync support.
 *
 * Strategy:
 *   - Static assets (CSS, JS, images, fonts): Cache-first
 *   - HTML pages: Network-first, fall back to cache, then offline page
 *   - API calls: Network-only (offline runs use IndexedDB + sync-engine)
 */

const CACHE_VERSION = 'v1';
const STATIC_CACHE = `runrush-static-${CACHE_VERSION}`;
const PAGES_CACHE = `runrush-pages-${CACHE_VERSION}`;

// Core app shell assets to precache on install
const PRECACHE_ASSETS = [
  '/offline',
  '/static/css/landing.css',
  '/static/js/offline-storage.js',
  '/static/js/sync-engine.js',
  '/static/js/offline-ui.js',
  '/static/js/pwa-register.js',
  '/static/js/landing.js',
  '/static/favicon.png',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/manifest.json'
];

// External CDN assets to cache on first use
const CDN_HOSTS = [
  'fonts.googleapis.com',
  'fonts.gstatic.com',
  'cdn.jsdelivr.net',
  'cdnjs.cloudflare.com'
];

// ─── INSTALL ────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('[SW] Precaching app shell');
        return cache.addAll(PRECACHE_ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// ─── ACTIVATE ───────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => {
            // Delete old versioned caches
            return (name.startsWith('runrush-') &&
                    name !== STATIC_CACHE &&
                    name !== PAGES_CACHE);
          })
          .map((name) => {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

// ─── FETCH ──────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests (POST to /add, /api/sync-run, etc.)
  if (request.method !== 'GET') return;

  // Skip chrome-extension and other non-http schemes
  if (!url.protocol.startsWith('http')) return;

  // ── API requests: network-only (offline handled by IndexedDB) ──
  if (url.pathname.startsWith('/api/')) return;

  // ── CDN assets (fonts, Bootstrap, Font Awesome): cache-first ──
  if (CDN_HOSTS.some((host) => url.hostname.includes(host))) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // ── Local static assets: cache-first ──
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // ── HTML pages (navigation): network-first ──
  if (request.mode === 'navigate' || request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirstPage(request));
    return;
  }

  // ── Everything else: network-first with cache fallback ──
  event.respondWith(networkFirst(request, STATIC_CACHE));
});

// ─── STRATEGIES ─────────────────────────────────────────────

/**
 * Cache-first: return cached asset if available, otherwise fetch & cache.
 */
async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    // Return a basic offline response for non-critical assets
    return new Response('', { status: 408, statusText: 'Offline' });
  }
}

/**
 * Network-first for HTML pages: try network, cache the response,
 * fall back to cache, then show offline page.
 */
async function networkFirstPage(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(PAGES_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    // Network failed — try cache
    const cached = await caches.match(request);
    if (cached) return cached;

    // Nothing in cache — serve offline fallback
    const offlinePage = await caches.match('/offline');
    if (offlinePage) return offlinePage;

    // Last resort
    return new Response(
      '<h1>Offline</h1><p>RunRush is offline. Please check your connection.</p>',
      { headers: { 'Content-Type': 'text/html' } }
    );
  }
}

/**
 * Network-first: try network, fall back to cache.
 */
async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response('', { status: 408, statusText: 'Offline' });
  }
}

// ─── BACKGROUND SYNC (future enhancement) ───────────────────
// When the browser supports Background Sync API, the sync-engine
// can register a sync event instead of relying on 'online' listener.
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-offline-runs') {
    console.log('[SW] Background sync triggered for offline runs');
    event.waitUntil(
      self.clients.matchAll().then((clients) => {
        clients.forEach((client) => {
          client.postMessage({ type: 'SYNC_OFFLINE_RUNS' });
        });
      })
    );
  }
});

// ─── PUSH NOTIFICATIONS (future enhancement) ────────────────
self.addEventListener('push', (event) => {
  if (!event.data) return;

  const data = event.data.json();
  event.waitUntil(
    self.registration.showNotification(data.title || 'RunRush', {
      body: data.body || 'You have a new notification',
      icon: '/static/icons/icon-192.png',
      badge: '/static/icons/icon-192.png',
      tag: data.tag || 'runrush-notification'
    })
  );
});
