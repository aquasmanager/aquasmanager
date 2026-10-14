import { t } from 'src/i18n/instance';
import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import axios from 'axios';
import { Notify } from 'quasar';
import { useControllerStore } from './controllerStore';
import { apiErrorMessage } from 'src/utils/apiError';

export type FlashStatus = 'queued' | 'running' | 'success' | 'failed';

export interface FlashProgress {
  controller_id: number;
  controller_name: string;
  status: FlashStatus;
  phase: string;
  percent: number;
  error?: string | null;
}

/**
 * Flashs OTA en cours : progression reçue en direct (websocket FLASH_PROGRESS)
 * et relue au chargement (GET /controllers/flash-status).
 */
export const useFlashStore = defineStore('flash', () => {
  const progress = ref<Record<number, FlashProgress>>({});
  // Filet de sécurité si un message websocket se perd : relecture périodique
  // tant qu'un flash est en cours
  let poll: ReturnType<typeof setInterval> | null = null;

  const active = computed(() =>
    Object.values(progress.value).filter((p) => p.status === 'queued' || p.status === 'running'),
  );

  function isFlashing(controllerId: number): boolean {
    const state = progress.value[controllerId];
    return !!state && (state.status === 'queued' || state.status === 'running');
  }

  function watchActive() {
    if (active.value.length && !poll) {
      poll = setInterval(() => void fetchStatus(true).catch(() => undefined), 15000);
    } else if (!active.value.length && poll) {
      clearInterval(poll);
      poll = null;
    }
  }

  function apply(state: FlashProgress, notify: boolean) {
    const previous = progress.value[state.controller_id];
    progress.value[state.controller_id] = state;
    watchActive();
    const controllerStore = useControllerStore();
    const controller = controllerStore.controllers.find((c) => c.id === state.controller_id);
    if (state.status === 'success' && controller) controller.is_dirty = false;
    if (!notify || previous?.status === state.status) return;
    const name = controller?.name ?? state.controller_name;
    if (state.status === 'success') {
      Notify.create({ type: 'positive', message: t('notices.flashDone', { name }) });
    } else if (state.status === 'failed') {
      Notify.create({
        type: 'negative',
        message: t('notices.flashFailed', { name }),
        timeout: 8000,
      });
    }
  }

  function handleWs(data: Record<string, unknown>) {
    if (typeof data.controller_id !== 'number') return;
    apply(data as unknown as FlashProgress, true);
  }

  async function fetchStatus(notify = false) {
    const { data } = await axios.get<FlashProgress[]>('/controllers/flash-status');
    data.forEach((state) => apply(state, notify));
    // Flash en cours ici mais inconnu de l'API (redémarrée entre-temps) : terminé
    const known = new Set(data.map((state) => state.controller_id));
    for (const state of active.value) {
      if (!known.has(state.controller_id)) apply({ ...state, status: 'failed', phase: 'Interrompu' }, notify);
    }
  }

  async function flash(controllerId: number, targetIp?: string | null) {
    try {
      await axios.post(`/controllers/${controllerId}/flash`, null, {
        params: targetIp ? { target_ip: targetIp } : {},
      });
    } catch (err) {
      Notify.create({ type: 'negative', message: apiErrorMessage(err, t('notices.flashStartFailed')) });
      throw err;
    }
  }

  return { progress, active, isFlashing, handleWs, fetchStatus, flash };
});
