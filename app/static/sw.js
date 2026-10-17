/**
 * Service worker: кэширует статическую "оболочку" приложения, чтобы его
 * можно было установить на телефон (PWA) и чтобы иконки/манифест грузились
 * из кэша при плохой связи. Страницы с данными всегда идут в сеть первыми.
 */

const CACHE_NAME = "zhizn-shell-v1";
const SHELL_ASSETS = [
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Статика (/static/...) — сначала кэш, потом сеть
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
    return;
  }

  // Все остальные запросы (страницы, формы) — всегда из сети напрямую
});
