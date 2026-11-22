// Garde l'outil sur l'appareil pour qu'il fonctionne sans réseau pendant l'AG.
const VERSION = "seance-v1";
const FICHIERS = ["./", "index.html", "style.css", "app.js", "regles.js", "manifest.webmanifest", "icone.svg",
  "icone-192.png", "icone-512.png", "polices/barlow-latin-400-normal.woff2", "polices/barlow-latin-600-normal.woff2",
  "polices/barlow-latin-700-normal.woff2", "polices/barlow-semi-condensed-latin-700-normal.woff2"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(FICHIERS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((cles) => Promise.all(cles.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
// Réseau d'abord quand il y en a (pour recevoir les mises à jour), sinon la copie gardée.
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(fetch(e.request).then((r) => {
    const copie = r.clone();
    caches.open(VERSION).then((c) => c.put(e.request, copie));
    return r;
  }).catch(() => caches.match(e.request).then((r) => r || caches.match("index.html"))));
});
