/**
 * QuantumSafe Optimize - Service Worker
 * Provides offline support, caching, and performance optimization
 */

const CACHE_VERSION = 'qso-v2.0.0';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;
const FONT_CACHE = `${CACHE_VERSION}-fonts`;

// Static assets to pre-cache
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/dashboard.html',
    '/css/style.css',
    '/css/dashboard.css',
    '/css/components.css',
    '/css/icons.css',
    '/js/main.js',
    '/js/dashboard.js',
    '/manifest.json'
];

// API endpoints to cache with network-first strategy
const API_PATTERNS = [
    '/api/v1/health',
    '/api/v1/jobs',
    '/health'
];

/**
 * Install - Pre-cache static assets
 */
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('[SW] Pre-caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => self.skipWaiting())
            .catch(err => {
                console.warn('[SW] Pre-cache failed for some assets:', err);
                return self.skipWaiting();
            })
    );
});

/**
 * Activate - Clean old caches
 */
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then(keys => Promise.all(
                keys
                    .filter(key => key.startsWith('qso-') && key !== STATIC_CACHE && key !== API_CACHE && key !== FONT_CACHE)
                    .map(key => {
                        console.log('[SW] Removing old cache:', key);
                        return caches.delete(key);
                    })
            ))
            .then(() => self.clients.claim())
    );
});

/**
 * Fetch - Smart caching strategy
 */
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') return;

    // Skip WebSocket connections
    if (url.protocol === 'ws:' || url.protocol === 'wss:') return;

    // Font requests - cache-first (long-lived)
    if (url.hostname === 'fonts.googleapis.com' || 
        url.hostname === 'fonts.gstatic.com' ||
        url.hostname === 'cdnjs.cloudflare.com') {
        event.respondWith(cacheFirst(request, FONT_CACHE, 30 * 24 * 60 * 60 * 1000)); // 30 days
        return;
    }

    // API requests - network-first with fallback
    if (API_PATTERNS.some(pattern => url.pathname.startsWith(pattern))) {
        event.respondWith(networkFirst(request, API_CACHE, 5 * 60 * 1000)); // 5 min cache
        return;
    }

    // Static assets - stale-while-revalidate
    if (url.origin === self.location.origin) {
        event.respondWith(staleWhileRevalidate(request, STATIC_CACHE));
        return;
    }
});

/**
 * Cache-first strategy (for fonts and long-lived assets)
 */
async function cacheFirst(request, cacheName, maxAge) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    
    if (cached) {
        const dateHeader = cached.headers.get('date');
        if (dateHeader && (Date.now() - new Date(dateHeader).getTime()) < maxAge) {
            return cached;
        }
    }

    try {
        const response = await fetch(request);
        if (response.ok) {
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        return cached || new Response('Offline', { status: 503 });
    }
}

/**
 * Network-first strategy (for API calls)
 */
async function networkFirst(request, cacheName, maxAge) {
    const cache = await caches.open(cacheName);
    
    try {
        const response = await fetch(request);
        if (response.ok) {
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        const cached = await cache.match(request);
        if (cached) {
            return cached;
        }
        return new Response(JSON.stringify({ 
            error: 'offline',
            message: 'You are currently offline. Cached data may be available.' 
        }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

/**
 * Stale-while-revalidate strategy (for static assets)
 */
async function staleWhileRevalidate(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);

    const fetchPromise = fetch(request)
        .then(response => {
            if (response.ok) {
                cache.put(request, response.clone());
            }
            return response;
        })
        .catch(() => cached);

    return cached || fetchPromise;
}

/**
 * Background sync for job submissions
 */
self.addEventListener('sync', (event) => {
    if (event.tag === 'submit-job') {
        event.waitUntil(submitPendingJobs());
    }
});

async function submitPendingJobs() {
    // Retrieve pending jobs from IndexedDB and submit them
    console.log('[SW] Submitting pending jobs...');
}

/**
 * Push notifications for job completion
 */
self.addEventListener('push', (event) => {
    const data = event.data ? event.data.json() : {};
    
    const options = {
        body: data.message || 'Your optimization job has completed.',
        icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">⚛</text></svg>',
        badge: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">✓</text></svg>',
        tag: data.jobId || 'job-update',
        data: data,
        actions: [
            { action: 'view', title: 'View Results' },
            { action: 'dismiss', title: 'Dismiss' }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(data.title || 'QuantumSafe Optimize', options)
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    if (event.action === 'view' && event.notification.data?.jobId) {
        event.waitUntil(
            self.clients.openWindow(`/dashboard#job-${event.notification.data.jobId}`)
        );
    } else {
        event.waitUntil(
            self.clients.openWindow('/dashboard')
        );
    }
});
