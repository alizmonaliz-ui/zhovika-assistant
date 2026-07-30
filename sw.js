const CACHE_NAME = 'zhovika-pa-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  'https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800&display=swap'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // API calls - network first
  if (e.request.url.includes('/api/')) {
    e.respondWith(
      fetch(e.request).catch(() => {
        return new Response(JSON.stringify({offline:true}), {
          headers: {'Content-Type': 'application/json'}
        });
      })
    );
    return;
  }

  // Static assets - cache first
  e.respondWith(
    caches.match(e.request).then((response) => {
      return response || fetch(e.request).then((fetchResponse) => {
        return caches.open(CACHE_NAME).then((cache) => {
          cache.put(e.request, fetchResponse.clone());
          return fetchResponse;
        });
      });
    }).catch(() => {
      // Fallback for HTML pages
      if (e.request.mode === 'navigate') {
        return caches.match('/index.html');
      }
    })
  );
});

// Background sync for offline actions
self.addEventListener('sync', (e) => {
  if (e.tag === 'sync-data') {
    e.waitUntil(syncWithServer());
  }
});

async function syncWithServer() {
  const clients = await self.clients.matchAll();
  clients.forEach(client => client.postMessage({type: 'SYNC_READY'}));
}

// Push notifications
self.addEventListener('push', (e) => {
  const data = e.data.json();
  e.waitUntil(
    self.registration.showNotification(data.title || 'ZHOVIKA', {
      body: data.body || 'یادآوری جدید',
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-72.png',
      tag: data.tag || 'reminder',
      requireInteraction: true,
      actions: [
        {action: 'open', title: 'باز کردن'},
        {action: 'dismiss', title: 'بستن'}
      ]
    })
  );
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  if (e.action === 'open') {
    e.waitUntil(clients.openWindow('/'));
  }
});
