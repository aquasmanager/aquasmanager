import { t } from 'src/i18n/instance';
import { defineBoot } from '#q-app/wrappers';
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { Notify } from 'quasar';
import { newKey } from 'src/offline/queued';
import { useOfflineStore } from 'src/stores/offlineStore';

/*
 * Écritures hors connexion : chaque écriture porte une clé d'idempotence ;
 * celles marquées « offline » (config axios) sont mises en file d'attente en
 * cas d'échec réseau puis rejouées au retour du réseau. L'appelant reçoit une
 * réponse 202 contenant offline.data (état attendu, affiché en attendant).
 */

declare module 'axios' {
  interface AxiosRequestConfig {
    offline?: { label: string; data?: unknown };
    _offlineReplay?: boolean;
  }
}

const WRITE_METHODS = ['post', 'put', 'patch', 'delete'];
// Écriture pouvant attendre le réseau : au-delà, file d'attente (serveur
// injoignable sans erreur immédiate, ex. hors du réseau local)
const QUEUEABLE_TIMEOUT_MS = 8000;

export default defineBoot(({ store, router }) => {
  const offline = useOfflineStore(store);
  offline.start();

  // Toutes les pages chargées une fois (le service worker les garde) : chacune
  // s'ouvre ensuite sans réseau, même jamais visitée (ex : signature en bourse)
  setTimeout(() => {
    if (!navigator.onLine) return;
    for (const route of router.getRoutes()) {
      const component = route.components?.default;
      if (typeof component === 'function') void (component as () => Promise<unknown>)().catch(() => undefined);
    }
  }, 4000);

  axios.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    if (WRITE_METHODS.includes((config.method ?? 'get').toLowerCase()) && !config.headers['Idempotency-Key']) {
      config.headers['Idempotency-Key'] = newKey();
    }
    if (config.offline && !config._offlineReplay) {
      // Déjà hors connexion : file d'attente sans essayer le réseau
      if (!offline.online) throw new AxiosError('offline', AxiosError.ERR_NETWORK, config);
      config.timeout ||= QUEUEABLE_TIMEOUT_MS;
    }
    return config;
  });

  axios.interceptors.response.use(
    (response) => {
      // Réponse servie par le service worker depuis son cache : serveur injoignable
      if (response.headers['x-aquas-from-cache']) offline.markUnreachable();
      else offline.markReachable();
      return response;
    },
    async (error: AxiosError) => {
      const config = error.config;
      // Réponse du serveur (même une erreur) : il est joignable ; sans réponse
      // (hors annulation) : hors connexion jusqu'à son retour
      if (error.response) offline.markReachable();
      else if (!axios.isCancel(error) && !config?._offlineReplay) offline.markUnreachable();
      if (!config || error.response || !config.offline || config._offlineReplay) return Promise.reject(error);
      // Pas de réponse du serveur : réseau absent ou coupé → file d'attente
      await offline.enqueue({
        id: String(config.headers['Idempotency-Key']),
        method: (config.method ?? 'post').toUpperCase(),
        url: config.url ?? '',
        data: typeof config.data === 'string' ? (JSON.parse(config.data) as unknown) : config.data,
        label: config.offline.label,
      });
      Notify.create({
        type: 'info',
        icon: 'cloud_off',
        message: t('notices.savedOffline'),
        timeout: 2500,
      });
      return { data: config.offline.data ?? null, status: 202, statusText: 'queued', headers: {}, config } as AxiosResponse;
    },
  );
});
