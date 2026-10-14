import { t } from 'src/i18n/instance';
/**
 * Mode hors connexion : file d'attente des écritures faites sans réseau
 * (IndexedDB), rejouées dans l'ordre au retour du réseau avec leur clé
 * d'idempotence (l'API ne les applique qu'une fois).
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import axios, { type AxiosError } from 'axios';
import { idb } from 'src/offline/idb';
import { offlineSales } from 'src/pro/offline/sales';

export interface OutboxOp {
  id: string; // clé d'idempotence
  method: string;
  url: string;
  data: unknown;
  label: string;
  created_at: string;
  error?: string; // refusée par l'API (conservée pour information)
}

export const SYNCED_EVENT = 'aquas:synced';

export const useOfflineStore = defineStore('offline', () => {
  // Hors connexion : pas de réseau du tout, ou serveur injoignable (réseau
  // présent mais requêtes sans réponse, ex. hors du réseau local)
  const networkUp = ref(typeof navigator === 'undefined' ? true : navigator.onLine);
  const serverReachable = ref(true);
  const online = computed(() => networkUp.value && serverReachable.value);
  const ops = ref<OutboxOp[]>([]);
  const syncing = ref(false);
  const lastSync = ref<string | null>(null);

  const pending = computed(() => ops.value.filter((op) => !op.error));
  const failed = computed(() => ops.value.filter((op) => op.error));

  async function load() {
    try {
      ops.value = (await idb.all<OutboxOp>('outbox')).sort((a, b) => a.created_at.localeCompare(b.created_at));
    } catch {
      ops.value = [];
    }
  }

  async function enqueue(op: Omit<OutboxOp, 'created_at'>) {
    const full: OutboxOp = { ...op, created_at: new Date().toISOString() };
    await idb.put('outbox', JSON.parse(JSON.stringify(full)) as OutboxOp);
    ops.value = [...ops.value.filter((o) => o.id !== full.id), full];
  }

  async function remove(id: string) {
    await idb.delete('outbox', id);
    ops.value = ops.value.filter((o) => o.id !== id);
  }

  /** Envoie les opérations en attente, dans l'ordre ; s'arrête à la première panne réseau. */
  async function flush() {
    if (syncing.value || !pending.value.length) return;
    syncing.value = true;
    let sent = 0;
    try {
      for (const op of [...pending.value]) {
        try {
          await axios.request({
            method: op.method,
            url: op.url,
            data: op.data,
            headers: { 'Idempotency-Key': op.id },
            _offlineReplay: true,
          });
          await remove(op.id);
          // Vente hors connexion envoyée : le certificat existe désormais côté API
          await offlineSales.remove(op.id).catch(() => undefined);
          sent++;
        } catch (err) {
          const status = (err as AxiosError).response?.status;
          if (!status || status >= 500 || status === 401 || status === 429) break; // réessayer plus tard
          const detail = ((err as AxiosError<{ detail?: unknown }>).response?.data?.detail ?? t('notices.error', { status })) as unknown;
          const failedOp = { ...op, error: typeof detail === 'string' ? detail : t('notices.refused', { status }) };
          await idb.put('outbox', failedOp);
          ops.value = ops.value.map((o) => (o.id === op.id ? failedOp : o));
        }
      }
    } finally {
      syncing.value = false;
    }
    if (sent) {
      lastSync.value = new Date().toISOString();
      window.dispatchEvent(new CustomEvent(SYNCED_EVENT, { detail: { sent } }));
    }
    return sent;
  }

  // Requête sans réponse : serveur considéré injoignable, sondé jusqu'à son retour
  let probe: ReturnType<typeof setInterval> | null = null;
  function markUnreachable() {
    if (!serverReachable.value) return;
    serverReachable.value = false;
    probe ??= setInterval(() => {
      axios.get('/health', { timeout: 5000, _offlineReplay: true }).then(markReachable, () => undefined);
    }, 10_000);
  }

  function markReachable() {
    if (probe) clearInterval(probe);
    probe = null;
    if (serverReachable.value) return;
    serverReachable.value = true;
    void flush();
  }

  let started = false;
  function start() {
    if (started) return;
    started = true;
    void load().then(() => (online.value ? flush() : undefined));
    window.addEventListener('online', () => {
      networkUp.value = true;
      void flush();
    });
    window.addEventListener('offline', () => (networkUp.value = false));
    // Réseau revenu sans événement (bourse, réseau instable) : nouvel essai régulier
    setInterval(() => {
      if (pending.value.length) void flush();
    }, 30_000);
  }

  return {
    online,
    ops,
    pending,
    failed,
    syncing,
    lastSync,
    load,
    enqueue,
    remove,
    flush,
    start,
    markUnreachable,
    markReachable,
  };
});
