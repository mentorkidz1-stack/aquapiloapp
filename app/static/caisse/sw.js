/* Service worker — caisse Aquapilo uniquement (scope /ventes/).
 *
 * Phase 1 (fondations PWA) : rend la page caisse et ses ressources
 * disponibles hors-ligne. Ne gère PAS encore la création de ventes
 * hors-ligne (file d'attente / synchronisation = phases suivantes) :
 * toute requête non-GET (validation d'une vente, annulation...) passe
 * directement au réseau, sans interception.
 *
 * Stratégies :
 * - Page caisse (navigation HTML) : réseau d'abord, secours sur le
 *   cache si hors-ligne (les données embarquées — catalogue, CSRF —
 *   datent alors du dernier chargement en ligne).
 * - Ressources statiques (CSS/JS/fonts/icônes) : cache d'abord, quasi
 *   jamais de raison de changer entre deux déploiements sans purge de
 *   version.
 */
const VERSION = "v4";
const CACHE_STATIQUE = `aquapilo-caisse-statique-${VERSION}`;
const CACHE_PAGE = `aquapilo-caisse-page-${VERSION}`;

const RESSOURCES_STATIQUES = [
  "/static/vendor/bootstrap/bootstrap.min.css",
  "/static/vendor/bootstrap/bootstrap.bundle.min.js",
  "/static/vendor/bootstrap-icons/bootstrap-icons.min.css",
  "/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2",
  "/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff",
  "/static/css/custom.css",
  "/static/vendor/manifest/manifest.json",
  "/static/vendor/manifest/icone-192.png",
  "/static/vendor/manifest/icone-512.png",
  "/static/caisse/db.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_STATIQUE).then((cache) => cache.addAll(RESSOURCES_STATIQUES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((noms) => Promise.all(
      noms
        .filter((nom) => nom.startsWith("aquapilo-caisse-") &&
                         nom !== CACHE_STATIQUE && nom !== CACHE_PAGE)
        .map((nom) => caches.delete(nom))
    ))
  );
  self.clients.claim();
});

// Marqueur "d'où vient la dernière réponse de /ventes/caisse" écrit
// directement en Cache Storage plutôt qu'envoyé par postMessage : un
// message peut arriver avant que le script de la page (en bas du
// body) ait fini de s'exécuter et posé son écouteur — perdu, sans
// jamais qu'on s'en aperçoive. Le Cache Storage, lui, est disponible
// dès que la page le lit, aucune course possible.
const URL_MARQUEUR = "/__aquapilo_source__";

function ecrireMarqueur(source) {
  const corps = JSON.stringify({ source, ts: Date.now() });
  const reponse = new Response(corps, { headers: { "Content-Type": "application/json" } });
  return caches.open(CACHE_PAGE).then((cache) => cache.put(URL_MARQUEUR, reponse));
}

self.addEventListener("fetch", (event) => {
  const req = event.request;

  // Seules les lectures (GET) sont interceptées. Les écritures
  // (POST vente/annulation) passent directement au réseau : la file
  // d'attente hors-ligne arrive en phase suivante.
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Page caisse elle-même : réseau d'abord, cache en secours. Le
  // client est prévenu par message (réseau/cache) : navigator.onLine
  // ne dit que si la carte réseau est active, pas si CE chargement a
  // réellement atteint le serveur — on ne peut pas s'y fier pour
  // décider si le catalogue embarqué vient d'être resynchronisé.
  if (url.pathname === "/ventes/caisse") {
    event.respondWith(
      fetch(req)
        .then((reponse) => {
          const copie = reponse.clone();
          event.waitUntil(
            caches.open(CACHE_PAGE)
              .then((cache) => cache.put(req, copie))
              .then(() => ecrireMarqueur("network"))
          );
          return reponse;
        })
        .catch(() => {
          event.waitUntil(ecrireMarqueur("cache"));
          return caches.match(req);
        })
    );
    return;
  }

  // Ressources statiques connues : cache d'abord, réseau en secours.
  if (RESSOURCES_STATIQUES.some((chemin) => url.pathname === chemin)) {
    event.respondWith(
      caches.match(req).then((reponse) => reponse || fetch(req))
    );
  }
});
