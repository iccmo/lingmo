const CACHE = 'lingmo-v2';

self.addEventListener('install', e => {
  e.waitUntil(caches.delete('novel-writer-v1').then(() => caches.open(CACHE).then(c => c.addAll(['/']))));
});

self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).then(res => {
      if (res.ok && e.request.url.includes('/assets/')) {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
      }
      return res;
    }))
  );
});
