/* WardZero service worker: app-shell cache + stale-while-revalidate for read-only API GETs.
   Writes are NOT handled here: the page queues readings in IndexedDB and replays them idempotently
   (POST /readings/batch), which is testable and works the same on browsers without Background Sync. */
const VERSION = "wz-v1";
const SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icon.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

const READ_API = /\/api\/(patients|alerts|devices|analytics|scenarios)/;

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  const url = new URL(req.url);
  if (url.pathname === "/ws" || url.pathname.startsWith("/ws/")) return;

  if (req.mode === "navigate") {            // SPA navigations: network first, shell when offline
    e.respondWith(fetch(req).catch(() => caches.match("/index.html")));
    return;
  }
  if (READ_API.test(url.pathname)) {        // last-known data when offline (marked via header for the UI)
    e.respondWith(
      fetch(req).then((res) => { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)); return res; })
        .catch(async () => {
          const hit = await caches.match(req);
          if (!hit) return new Response(JSON.stringify({ detail: "offline_no_cache" }), { status: 503, headers: { "Content-Type": "application/json" } });
          const h = new Headers(hit.headers); h.set("X-WZ-Stale", "1");
          return new Response(await hit.blob(), { status: hit.status, headers: h });
        }));
    return;
  }
  e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
    if (res.ok) { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)); }
    return res;
  })));
});
