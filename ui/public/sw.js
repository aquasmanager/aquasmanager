/*
 * Service worker d'AquasManager : application installable et utilisable
 * hors connexion.
 * - Interface (même origine) : pages réseau d'abord, fichiers versionnés en cache.
 * - API (lectures GET) : réseau d'abord ; sans réseau (ou réseau trop lent),
 *   dernière réponse enregistrée. Après un échec, le cache est servi aussitôt
 *   pendant OFFLINE_HOLD_MS (réseau retenté en arrière-plan) : sans cela, chaque
 *   requête attendrait le délai maximal (serveur injoignable hors du réseau local). Les écritures ne passent jamais par ici :
 *   l'appli les met en file d'attente (src/stores/offlineStore.ts).
 * - Photos : cache d'abord, rafraîchies en arrière-plan.
 * Le cache des données est vidé à la déconnexion (message « clear-data »).
 */
// v4 : purge le worker pdf.js mis en cache avec un mauvais type (octet-stream)
const UI_CACHE = 'aquasmanager-ui-v4';
const API_CACHE = 'aquasmanager-api-v1';
const PHOTO_CACHE = 'aquasmanager-photos-v2';
const KNOWN = [UI_CACHE, API_CACHE, PHOTO_CACHE];
// Délais avant de servir le cache : page et config.js au démarrage, puis l'API
const SHELL_TIMEOUT_MS = 2000;
const NETWORK_TIMEOUT_MS = 3500;
const OFFLINE_HOLD_MS = 30000;
// Hors connexion récente : court sursis au réseau (s'il est revenu, données fraîches)
const OFFLINE_GRACE_MS = 400;
// Dernier échec réseau (délai dépassé ou erreur) : 0 = réseau considéré comme présent
let offlineSince = 0;
// Sursis dépassé à l'instant : absence confirmée, les requêtes suivantes (enchaînées
// au démarrage de l'appli) prennent le cache sans attendre
let confirmedOfflineAt = 0;
const CONFIRMED_MS = 5000;

function looksOffline() {
  return self.navigator.onLine === false || Date.now() - offlineSince < OFFLINE_HOLD_MS;
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(UI_CACHE)
      .then((cache) => cache.addAll(['/', '/manifest.json', '/config.js']))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => !KNOWN.includes(key)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('message', (event) => {
  if (event.data === 'clear-data') {
    event.waitUntil(Promise.all([caches.delete(API_CACHE), caches.delete(PHOTO_CACHE)]));
  }
});

// Réponses « opaques » acceptées : images d'un autre domaine chargées par <img>
function cachePut(cacheName, key, response) {
  if (response && (response.ok || response.type === 'opaque')) {
    const copy = response.clone();
    void caches.open(cacheName).then((cache) => cache.put(key, copy));
  }
  return response;
}

// Réponse servie depuis le cache : marquée pour que l'appli se sache hors connexion
function markCached(response) {
  const headers = new Headers(response.headers);
  headers.set('X-Aquas-From-Cache', '1');
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

// Réseau d'abord avec délai maximal, puis cache. Hors connexion récente :
// cache presque aussitôt s'il existe, le réseau continue en arrière-plan (mise
// à jour du cache, et fin du mode hors connexion dès qu'il répond).
function networkFirst(request, cacheName, key, timeoutMs = NETWORK_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const fromCache = () =>
      caches.match(key, { cacheName }).then((cached) => {
        if (cached && !settled) {
          settled = true;
          resolve(markCached(cached));
        }
        return cached;
      });
    let wait = timeoutMs;
    if (looksOffline()) wait = Date.now() - confirmedOfflineAt < CONFIRMED_MS ? 0 : OFFLINE_GRACE_MS;
    const timer = setTimeout(() => {
      offlineSince = Date.now();
      if (wait > 0) confirmedOfflineAt = Date.now();
      void fromCache();
    }, wait);
    fetch(request)
      .then((response) => {
        clearTimeout(timer);
        offlineSince = 0;
        confirmedOfflineAt = 0;
        cachePut(cacheName, key, response);
        if (!settled) {
          settled = true;
          resolve(response);
        }
      })
      .catch((err) => {
        clearTimeout(timer);
        offlineSince = Date.now();
        if (settled) return;
        void fromCache().then((cached) => {
          if (!cached) reject(err);
        });
      });
  });
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  const sameOrigin = url.origin === self.location.origin;

  if (sameOrigin) {
    // Pages : réseau d'abord, index.html en secours
    if (request.mode === 'navigate') {
      event.respondWith(networkFirst(request, UI_CACHE, '/', SHELL_TIMEOUT_MS));
      return;
    }
    // Adresse de l'API (config.js) : indispensable hors connexion
    if (url.pathname === '/config.js' || url.pathname === '/manifest.json') {
      event.respondWith(networkFirst(request, UI_CACHE, url.pathname, SHELL_TIMEOUT_MS));
      return;
    }
    if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/')) {
      event.respondWith(
        caches.match(request).then((cached) => cached || fetch(request).then((r) => cachePut(UI_CACHE, request, r))),
      );
    }
    // Même origine avec proxy /api : traité comme l'API ci-dessous
    if (!url.pathname.startsWith('/api/')) return;
  }

  // API : pas de cache pour le websocket, l'authentification, les téléchargements
  // ni les images des caméras (toujours en direct, parfois lentes à venir)
  if (/\/(ws|refresh|login|logout|health)(\/|$)/.test(url.pathname) || /\.(pdf|csv)$/.test(url.pathname)) return;
  if (/\/cameras\/\d+\/(snapshot|live)/.test(url.pathname)) return;

  // Photos : cache d'abord (clé sans le paramètre anti-cache), mise à jour en arrière-plan
  if (url.pathname.includes('/photos/')) {
    const key = url.origin + url.pathname;
    event.respondWith(
      caches.match(key, { cacheName: PHOTO_CACHE }).then((cached) => {
        const network = fetch(request)
          .then((response) => cachePut(PHOTO_CACHE, key, response))
          .catch(() => cached);
        return cached || network;
      }),
    );
    return;
  }

  event.respondWith(networkFirst(request, API_CACHE, request.url));
});

// --- Notifications push (alertes, rappels, réservations) ---
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : '' };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || 'AquasManager', {
      body: data.body || '',
      icon: '/icons/icon-192.png',
      badge: '/icons/favicon-96x96.png',
      data: { url: data.url || '/home' },
    }),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/home';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      const open = windows.find((w) => new URL(w.url).origin === self.location.origin);
      if (open) {
        open.focus();
        return open.navigate(url);
      }
      return self.clients.openWindow(url);
    }),
  );
});
