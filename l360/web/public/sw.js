// Minimal service worker: makes the app installable and lets it reload
// while briefly offline. Deliberately does NOT cache anything under /api/
// — this is a live booking/billing system, so a stale cached calendar or
// invoice status would be actively misleading, not a convenience.
const CACHE_NAME = "l360-shell-v2";
const SHELL_URLS = ["/", "/manifest.json", "/learning360-logo-white.png", "/learning360-mark-orange.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.pathname.startsWith("/api/")) {
    return; // let the browser handle it normally — never intercept API calls
  }

  // Content-hashed bundles under /assets/ are cached by the HTTP layer
  // (Cache-Control: immutable) — putting them in the SW cache too made it
  // grow without bound across deploys, since CACHE_NAME never knew about
  // new builds. The SW only keeps the tiny app shell for offline reloads.
  if (url.pathname.startsWith("/assets/")) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match("/"))),
  );
});
