// static/service-worker.js

// 监听 install 事件，缓存静态资源
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open('my-cache').then(cache => {
      return cache.addAll([
        '/templates',
        '/templates/base.html',
        '/static/css/style.css',
        '/static/js/app.js',
        'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css',
        'https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js',
        'https://cdn.jsdelivr.net/npm/plotly.js/dist/plotly-latest.min.js'
      ]);
    })
  );
});

// 监听 fetch 事件，尝试从缓存获取资源
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});

// 清理缓存（可选）
self.addEventListener('activate', event => {
  const cacheWhitelist = ['my-cache'];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (!cacheWhitelist.includes(cacheName)) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});
