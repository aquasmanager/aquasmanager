import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import type {
  EquipmentsList,
  Equipment,
  EquipmentCreation,
  EquipmentStatus,
  EquipmentMode,
} from '../types/equipment';
import { API_URL } from 'src/utils/runtimeConfig';

const apiUrl = API_URL;

export const useEquipmentStore = defineStore(
  'Equipment',
  () => {
    const equipments = ref<Equipment[]>([]);
    const total = ref<number>();

    async function fetch() {
      const res = await axios.get<EquipmentsList>(`${apiUrl}/equipments`);
      equipments.value = res.data.equipments;
      total.value = res.data.total;
    }
    async function add(data: EquipmentCreation) {
      const res = await axios.post<Equipment>(`${apiUrl}/equipments/`, data);
      const equipment = res.data;
      equipments.value.push(res.data);
      return equipment;
    }
    async function update(data: Partial<Equipment> & { id: number }) {
      const res = await axios.patch<Equipment>(`${apiUrl}/equipments/${data.id}`, data);
      const i = equipments.value.findIndex((equipment) => equipment.id === data.id);
      if (i !== -1) equipments.value[i] = res.data;
      return res.data;
    }
    async function remove(id: number) {
      await axios.delete(`${apiUrl}/equipments/${id}`);
      equipments.value = equipments.value.filter((equipment) => equipment.id !== id);
    }
    function getById(id: number): Equipment | undefined {
      return equipments.value.find((equipment) => Number(equipment.id) === id);
    }
    function getByAquariumId(aqua_id: number): Equipment[] {
      return equipments.value.filter(
        (equipment) => Number(equipment.aquarium_id) === Number(aqua_id),
      );
    }

    async function status(data: { id: number; status: EquipmentStatus | string }) {
      // Marche/arrêt manuel ; l'état renvoyé par l'API complète la mise à jour locale
      const res = await axios.post(`${apiUrl}/equipments/${data.id}/toggle`, {
        status: data.status,
      });

      const i = equipments.value.findIndex((eq) => Number(eq.id) === Number(data.id));
      if (i !== -1 && equipments.value[i]) {
        equipments.value[i].status = data.status as EquipmentStatus;
        if (res.data) {
          equipments.value[i] = { ...equipments.value[i], ...res.data };
        }
      }
      return res.data;
    }

    async function mode(data: { id: number; mode: string }) {
      const res = await axios.patch(`${apiUrl}/equipments/${data.id}/mode`, { mode: data.mode });

      const i = equipments.value.findIndex((eq) => Number(eq.id) === Number(data.id));
      if (i !== -1 && equipments.value[i] && res.data) {
        equipments.value[i] = { ...equipments.value[i], ...res.data };
      }

      return res.data;
    }

    function handleWsUpdate(data: {
      equipment_id: number | string;
      mode?: EquipmentMode | string;
      status?: EquipmentStatus | string;
    }) {
      const eqId = Number(data.equipment_id);
      const i = equipments.value.findIndex((eq) => Number(eq.id) === eqId);

      if (i !== -1 && equipments.value[i]) {
        if (data.mode !== undefined) {
          equipments.value[i].mode = data.mode as EquipmentMode;
        }
        if (data.status !== undefined) {
          equipments.value[i].status = data.status as EquipmentStatus;
        }
      }
    }

    return {
      equipments,
      fetch,
      add,
      update,
      remove,
      getById,
      getByAquariumId,
      status,
      mode,
      handleWsUpdate,
    };
  },
  {
    persist: {
      key: 'equipments-store',
      storage: localStorage,
    },
  },
);
