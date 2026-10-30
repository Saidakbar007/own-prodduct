/**
 * Service worker: кэширует статическую "оболочку" приложения (PWA, §2/§9
 * принципы ТЗ — "ощущение приложения, а не сайта"). Страницы с данными
 * всегда идут в сеть напрямую — честность "сегодня" важнее офлайн-кэша.
 */

const CACHE_NAME = "sezony-shell-v1";
const SHELL_ASSETS = [
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/design/tokens.css",
  "/design/base.css",
  "/design/components.css",
  "/static/app.css",
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

  if (url.pathname.startsWith("/static/") || url.pathname.startsWith("/design/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
    return;
  }

  // Все остальные запросы (страницы, формы, замеры) — всегда из сети напрямую
});
