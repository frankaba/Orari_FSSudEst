/* Service worker degli orari FSE.
   GENERATO da gen_html.py: non modificarlo a mano, verrebbe sovrascritto.
   La versione e' agganciata al momento della generazione, quindi ogni rigenerazione
   invalida da sola la cache dei telefoni: non c'e' niente da ricordarsi di cambiare. */
const VERSIONE = "orari-fse-20260711-0855";
const RISORSE = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icona-192.png",
  "./icona-512.png",
  "./icona-180.png",
];

self.addEventListener("install", e => {
  /* niente skipWaiting: il nuovo sw resta in attesa e la pagina mostra il banner
     "Aggiorna". Cosi' l'utente non si vede ricaricare l'app sotto le mani. */
  e.waitUntil(caches.open(VERSIONE).then(c => c.addAll(RISORSE)));
});

self.addEventListener("message", e => {
  if (e.data === "aggiorna") self.skipWaiting();
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
