const CACHE_NAME = 'perseus-v4';
const urlsToCache = ['/'];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
            .catch(err => console.error('SW install error:', err))
    );
});

self.addEventListener('fetch', event => {
    // No cachear requests POST ni al API
    if (event.request.method !== 'GET') return;
    if (event.request.url.includes('/api/')) return;
    if (event.request.url.includes('/admin/')) return;

    event.respondWith(
        fetch(event.request)
            .catch(() => caches.match(event.request)
                .then(response => response || caches.match('/'))
            )
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames =>
            Promise.all(
                cacheNames
                    .filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))
            )
        )
    );
});
