import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import {
  type ControllersList,
  type ControllerCreation,
  type ControllerUpdate,
  type Controller,
  type ControllerLog,
  ControllerStatus,
} from '../types/controller';
import { useWebSocketStore } from 'stores/websocket';
import { API_URL } from 'src/utils/runtimeConfig';

const apiUrl = API_URL;

export interface ModuleItem {
  id: number;
  number: number;
  type: string;
  address: string;
  controller_id: number | null;
}

export interface I2cDevice {
  address: string;
  kind: 'module' | 'rtc' | 'rtc_undeclared' | 'eeprom' | 'io_undeclared' | 'pwm_undeclared' | 'pca_allcall' | 'unknown';
  module_number: number | null;
  module_type: string | null;
}

export interface I2cScan {
  enabled: boolean;
  devices: I2cDevice[];
  missing: { address: string; module_number?: number; module_type?: string; rtc?: string }[];
}

export const useControllerStore = defineStore(
  'controller',
  () => {
    const controllers = ref<Controller[]>([]);
    const total = ref<number>();

    // Gestion des modules par contrôleur
    const modulesMap = ref<Record<number, ModuleItem[]>>({});

    async function fetch() {
      const res = await axios.get<ControllersList>(`${apiUrl}/controllers`);
      controllers.value = res.data.controllers;
      total.value = res.data.total;
    }

    async function searchController(timeout = 3) {
      const res = await axios.get(`${apiUrl}/controllers/scan`, {
        params: { timeout },
      });
      return res.data;
    }

    async function add(data: ControllerCreation, targetIp?: string) {
      const wsStore = useWebSocketStore();

      const res = await axios.post<Controller>(`${apiUrl}/controllers/`, data);
      const newController = res.data;
      controllers.value.push(newController);

      // Contrôleur détecté sur le réseau : premier flash OTA immédiat
      if (targetIp && newController.id) {
        newController.status = ControllerStatus.FLASHING;
        wsStore.controllersState[newController.technical_name] = ControllerStatus.FLASHING;
        try {
          await axios.post(`${apiUrl}/controllers/${newController.id}/flash`, null, {
            params: { target_ip: targetIp },
          });
        } catch (error) {
          console.error('Erreur lors du déclenchement du flash OTA :', error);
          wsStore.controllersState[newController.technical_name] = ControllerStatus.OFFLINE;
        }
      }

      return newController;
    }

    async function update(id: number, data: ControllerUpdate) {
      const res = await axios.patch<Controller>(`${apiUrl}/controllers/${id}`, data);
      const i = controllers.value.findIndex((c) => c.id === id);
      if (i !== -1) {
        controllers.value[i] = res.data;
      }
    }

    async function remove(id: number) {
      await axios.delete(`${apiUrl}/controllers/${id}`);
      controllers.value = controllers.value.filter((controller) => controller.id !== id);
    }

    function getById(id: number): Controller | undefined {
      return controllers.value.find((controller) => Number(controller.id) === id);
    }

    function markControllerAsDirty(controllerId?: number) {
      if (controllerId) {
        const ctrl = controllers.value.find((c) => Number(c.id) === Number(controllerId));
        if (ctrl) ctrl.is_dirty = true;
      } else {
        controllers.value.forEach((c) => {
          c.is_dirty = true;
        });
      }
    }

    async function fetchControllerLogs(controllerId: number): Promise<ControllerLog[]> {
      try {
        const response = await axios.get<ControllerLog[]>(`${apiUrl}/logs`, {
          params: { controller_id: controllerId },
        });
        return response.data;
      } catch (error) {
        console.error(
          `Erreur lors de la récupération des logs pour le contrôleur ${controllerId}:`,
          error,
        );
        throw error;
      }
    }

    // --- Gestion des modules I2C ---
    async function fetchModules(ctrlId: number) {
      try {
        const res = await axios.get(`${apiUrl}/controllers/${ctrlId}/modules`);
        let data = res.data;
        if (data && typeof data === 'object' && !Array.isArray(data)) {
          data = data.modules || data.items || Object.values(data);
        }
        modulesMap.value = {
          ...modulesMap.value,
          [ctrlId]: Array.isArray(data) ? data : [],
        };
      } catch {
        modulesMap.value = {
          ...modulesMap.value,
          [ctrlId]: [],
        };
      }
    }

    async function addModule(ctrlId: number, payload: { address: string; type: string; number?: number | null }) {
      await axios.post(`${apiUrl}/controllers/${ctrlId}/modules`, payload);
      await fetchModules(ctrlId);
    }

    async function updateModule(ctrlId: number, moduleId: number, payload: { address?: string; type?: string; number?: number }) {
      await axios.patch(`${apiUrl}/controllers/${ctrlId}/modules/${moduleId}`, payload);
      await fetchModules(ctrlId);
    }

    async function deleteModule(ctrlId: number, moduleId: number) {
      await axios.delete(`${apiUrl}/controllers/${ctrlId}/modules/${moduleId}`);
      await fetchModules(ctrlId);
    }

    // Redémarrage à distance (bouton du firmware) : le contrôleur refait ses scans I2C et 1-Wire
    async function restart(ctrlId: number) {
      await axios.post(`${apiUrl}/controllers/${ctrlId}/restart`);
    }

    /** Redémarre puis attend que le contrôleur réponde de nouveau à `check` (90 s au plus). */
    async function restartAndWait<T>(ctrlId: number, check: () => Promise<T>): Promise<T> {
      await restart(ctrlId);
      const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
      await sleep(8000);
      const deadline = Date.now() + 90000;
      for (;;) {
        try {
          return await check();
        } catch (err) {
          if (Date.now() > deadline) throw err;
          await sleep(3000);
        }
      }
    }

    async function scanI2c(ctrlId: number): Promise<I2cScan> {
      return (await axios.get<I2cScan>(`${apiUrl}/controllers/${ctrlId}/i2c/scan`)).data;
    }

    return {
      controllers,
      total,
      modulesMap,
      fetch,
      add,
      update,
      remove,
      getById,
      searchController,
      markControllerAsDirty,
      fetchControllerLogs,
      fetchModules,
      addModule,
      updateModule,
      scanI2c,
      restart,
      restartAndWait,
      deleteModule,
    };
  },
  {
    persist: {
      key: 'controllers-store',
      storage: localStorage,
    },
  },
);
