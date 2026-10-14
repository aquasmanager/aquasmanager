import { defineStore } from 'pinia';
import { useAuthStore } from 'src/stores/authStore';
import { ref } from 'vue';
import { useControllerStore } from './controllerStore'; // 💡 Import du store des contrôleurs
import { useEquipmentStore } from './equipmentStore';
import { useFaultStore } from './faultStore';
import { useFlashStore } from './flashStore';
import { websocketUrl } from 'src/utils/runtimeConfig';

export interface WsMessage {
  type: string;
  sensor_id?: number | string;
  controller_id?: number | string;
  controller_name?: string;
  sensor_name?: string;
  sensor_technical_name?: string;
  value?: number | string;
  status?: string; // Pour les statuts de contrôleur ou équipement
  equipment_id?: number | string;
  state?: string;
  [key: string]: unknown;
}

export const useWebSocketStore = defineStore('websocket', () => {
  const isConnected = ref<boolean>(false);

  // Dictionnaires réactifs pour stocker les états en direct
  // null : la sonde ne répond plus (ESPHome publie « nan »)
  const sensorsState = ref<Record<number, number | null>>({});
  const controllersState = ref<Record<string, string>>({}); // controller_name -> status ("ONLINE", "FLASHING", etc.)
  const equipmentsState = ref<Record<number, string | number | boolean>>({});
  // État réel des lampes : intensité (%) par canal, démo en cours, minute jouée
  const lightsState = ref<
    Record<number, { channels: Record<number, number>; demo: boolean; minute: number | null; at: number }>
  >({});

  let socket: WebSocket | null = null;
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  let reconnectAttempts = 0;
  let connectedOnce = false;

  // Après une coupure (téléphone en veille, réseau), les messages diffusés
  // entre-temps sont perdus : fin de flash, retour en ligne d'un contrôleur.
  // On relit donc l'état depuis l'API à chaque reconnexion.
  async function resync(): Promise<void> {
    const controllerStore = useControllerStore();
    await Promise.all([controllerStore.fetch(), useFlashStore().fetchStatus()]);
    for (const ctrl of controllerStore.controllers) {
      if (!ctrl.status) continue;
      controllersState.value[ctrl.technical_name] = ctrl.status;
      controllersState.value[ctrl.id] = ctrl.status;
    }
  }

  const RECONNECT_BASE_DELAY_MS = 1000;
  const RECONNECT_MAX_DELAY_MS = 30000;

  // Fermeture par l'API : jeton absent, invalide ou expiré
  const WS_UNAUTHORIZED = 4401;

  function connect(): void {
    const auth = useAuthStore();
    // États en direct réservés aux comptes connectés (pages publiques : rien)
    if (!auth.accessToken) return;
    if (
      socket &&
      (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }

    // Même base que l'API REST (adresse absolue ou relative), ws/wss selon la page
    const wsUrl = websocketUrl();

    try {
      socket = new WebSocket(wsUrl);

      socket.onopen = (): void => {
        // Premier message : le jeton (jamais dans l'URL, qui finirait dans les journaux)
        socket?.send(JSON.stringify({ type: 'auth', token: auth.accessToken }));
        isConnected.value = true;
        reconnectAttempts = 0;
        if (connectedOnce) void resync().catch(() => undefined);
        connectedOnce = true;
      };

      socket.onmessage = (event: MessageEvent): void => {
        try {
          const data = JSON.parse(event.data) as WsMessage;
          if (import.meta.env.DEV) {
            console.log('📩 Message WS reçu :', data);
          }

          if (data.type === 'LIGHT_STATE' && typeof data.light_id === 'number') {
            const channels: Record<number, number> = {};
            for (const [id, value] of Object.entries((data.channels as Record<string, number>) ?? {})) {
              channels[Number(id)] = Number(value);
            }
            lightsState.value[data.light_id] = {
              channels,
              demo: Boolean(data.demo),
              minute: typeof data.minute === 'number' ? data.minute : null,
              at: Date.now(),
            };
          }

          // 1. Gestion des relevés de capteurs
          if (
            data.type === 'SENSOR_READING' &&
            data.sensor_id !== undefined &&
            data.value !== undefined
          ) {
            const sensorId = Number(data.sensor_id);
            const val = data.value === null ? null : Number(data.value);

            if (!isNaN(sensorId) && (val === null || !isNaN(val))) {
              sensorsState.value[sensorId] = val;
            }
          }

          // Progression d'un flash OTA (pas un statut de contrôleur)
          if (data.type === 'FLASH_PROGRESS') {
            useFlashStore().handleWs(data);
            return;
          }

          // 2. Gestion des statuts de contrôleurs (FLASHING, ONLINE, OFFLINE, etc.)
          if (
            (data.type === 'CONTROLLER_STATUS' || data.status) &&
            typeof data.controller_name === 'string' &&
            typeof data.status === 'string'
          ) {
            const ctrlName = data.controller_name;
            const newStatus = data.status;

            const controllerStore = useControllerStore();
            const targetCtrl = controllerStore.controllers.find(
              (c) =>
                c.name.toLowerCase() === ctrlName.toLowerCase() ||
                (c.technical_name && c.technical_name.toLowerCase() === ctrlName.toLowerCase()) ||
                (data.controller_id !== undefined &&
                  c.id.toString() === data.controller_id.toString()),
            );

            // 🌟 Mise à jour de toutes les clés possibles dans controllersState
            controllersState.value[ctrlName] = newStatus;
            if (targetCtrl) {
              delete controllersState.value[`controller_${targetCtrl.id}`];
              controllersState.value[targetCtrl.id] = newStatus;

              // Mise à jour de l'objet dans le store principal. Un contrôleur qui
              // revient en ligne (redémarrage) n'est pas pour autant à jour : c'est
              // la fin d'un flash réussi (FLASH_PROGRESS) qui retire « à reflasher ».
              (targetCtrl as { status: string }).status = newStatus;
            }
          }

          // 3. Gestion des états d'équipements en temps réel
          if (
            (data.type === 'EQUIPMENT_STATUS' ||
              data.type === 'EQUIPMENT_MODE_UPDATE' ||
              data.equipment_id !== undefined) &&
            data.equipment_id !== undefined
          ) {
            const eqId = Number(data.equipment_id);
            // Le mode (AUTO/MANUAL) n'est pas un état marche/arrêt : il ne doit pas
            // écraser l'état en direct (sinon l'équipement s'affiche « éteint »).
            const eqVal = data.status ?? data.state ?? data.value;

            if (!isNaN(eqId)) {
              // Stockage brut dans le dictionnaire WS existant
              if (eqVal !== undefined) {
                equipmentsState.value[eqId] = eqVal;
              }

              // 🔥 Mise à jour directe du store Equipment pour répercuter sur les objets (mode, status)
              const equipmentStore = useEquipmentStore();
              equipmentStore.handleWsUpdate({
                equipment_id: eqId,
                mode: data.mode as string,
                status: (data.status ?? data.state ?? data.value) as string,
              });
            }
          } // <- 💡 Accolade fermante ajoutée ici

          // 4. Gestion des défauts/alertes (osmolateur, interlocks capteurs, notifications)
          if (data.type === 'EQUIPMENT_FAULT') {
            const faultStore = useFaultStore();
            faultStore.handleWsFault({
              id: data.id as number | string | undefined,
              equipment_id: data.equipment_id,
              equipment_name: data.equipment_name as string | null | undefined,
              code: data.code as string | undefined,
              message: data.message as string | undefined,
              latched: data.latched as boolean | undefined,
              resolved: data.resolved as boolean | undefined,
            });
          }
        } catch (err) {
          console.error('❌ Erreur décodage message WS:', err);
        }
      };

      socket.onclose = (event: CloseEvent): void => {
        if (event.code === WS_UNAUTHORIZED) {
          // Jeton expiré : on le renouvelle puis on se reconnecte ; échec = déconnecté
          isConnected.value = false;
          socket = null;
          auth
            .refreshToken({ _skipAuthInterceptor: true })
            .then(() => connect())
            .catch(() => undefined);
          return;
        }
        const delay = Math.min(
          RECONNECT_BASE_DELAY_MS * 2 ** reconnectAttempts,
          RECONNECT_MAX_DELAY_MS,
        );
        reconnectAttempts += 1;
        console.warn(`⚠️ WebSocket déconnecté. Reconnexion automatique dans ${delay}ms...`);
        isConnected.value = false;
        socket = null;
        reconnectTimeout = setTimeout(() => {
          connect();
        }, delay);
      };

      socket.onerror = (err: Event): void => {
        console.error('❌ Erreur WebSocket:', err);
        socket?.close();
      };
    } catch (err) {
      console.error('❌ Erreur création WebSocket:', err);
      isConnected.value = false;
    }
  }

  function disconnect(): void {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
    if (socket) {
      socket.close();
      socket = null;
    }
    isConnected.value = false;
    reconnectAttempts = 0;
  }

  return {
    isConnected,
    sensorsState,
    controllersState,
    equipmentsState,
    lightsState,
    connect,
    disconnect,
  };
});
