const CACHE_NAME = "hybridbox-pwa-v24";
const ASSETS = [
  "/",
  "/manifest.json",
  "/static/styles.css?v=24",
  "/static/app.js?v=24",
  "/static/icons/icon.svg",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/snes-controller-photo.jpg",
  "/static/icons/snes-us-controller-photo.jpg",
  "/static/icons/arcade-controller-photo.jpg",
  "/static/icons/megadrive-controller-photo.jpg"
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
          return null;
        })
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }
  const url = new URL(event.request.url);
  if (
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/ws") ||
    url.pathname.startsWith("/roms/")
  ) {
    return;
  }
  event.respondWith(
    fetch(event.request, { cache: "no-store" })
      .then((res) => {
        if (res && res.ok) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone)).catch(() => {});
        }
        return res;
      })
      .catch(async () => {
        const cached = await caches.match(event.request);
        return cached || (await caches.match("/")) || Response.error();
      })
  );
});
