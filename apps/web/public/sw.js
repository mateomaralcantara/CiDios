// Service worker mínimo: caché de la "app shell" estática. Las respuestas de la API nunca se cachean.
const CACHE = "cdd-shell-v1";
self.addEventListener("install", (e) => e.waitUntil(caches.open(CACHE).then((c) => c.addAll(["/", "/icon.svg", "/manifest.webmanifest"]))));
self.addEventListener("activate", (e) => e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))));
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/_next/data")) return;
  if (url.pathname.startsWith("/_next/static") || url.pathname === "/icon.svg") {
    e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request).then((res) => {
      const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); return res;
    })));
  }
});
