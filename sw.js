/* Service worker: precache totale, strategia cache-first.
   Dopo la prima apertura l'app funziona senza rete.
   Cambia VERSIONE a ogni rigenerazione dell'orario: forza l'aggiornamento. */
const VERSIONE = "orari-fse-20260711-0828";";
const RISORSE = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icona-192.png",
  "./icona-512.png",
  "./icona-180.png",
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSIONE).then(c => c.addAll(RISORSE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(k => Promise.all(k.filter(x => x !== VERSIONE).map(x => caches.delete(x))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then(hit => hit || fetch(e.request).then(r => {
      const copia = r.clone();
      caches.open(VERSIONE).then(c => c.put(e.request, copia)).catch(() => {});
      return r;
    }).catch(() => caches.match("./index.html")))
  );
});
