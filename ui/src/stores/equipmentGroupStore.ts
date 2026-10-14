import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import type {
  EquipmentGroup,
  EquipmentGroupCreate,
  EquipmentGroupUpdate,
} from '../types/equipment_group';
import type { EquipmentMode, EquipmentStatus } from '../types/equipment';
import { API_URL } from 'src/utils/runtimeConfig';

const apiUrl = API_URL;

export const useEquipmentGroupStore = defineStore(
  'equipmentGroup',
  () => {
    const groups = ref<EquipmentGroup[]>([]);
    const total = ref<number>();

    async function fetch() {
      const res = await axios.get<EquipmentGroup[] | { groups: EquipmentGroup[]; total: number }>(
        `${apiUrl}/equipment-groups`,
      );

      if (Array.isArray(res.data)) {
        groups.value = res.data;
        total.value = res.data.length;
      } else if (res.data && Array.isArray(res.data.groups)) {
        groups.value = res.data.groups;
        total.value = res.data.total ?? res.data.groups.length;
      } else {
        groups.value = [];
        total.value = 0;
      }
    }

    async function create(data: EquipmentGroupCreate) {
      const res = await axios.post<EquipmentGroup>(`${apiUrl}/equipment-groups/`, data);
      groups.value.push(res.data);
      return res.data;
    }

    async function update(id: number, data: EquipmentGroupUpdate) {
      const res = await axios.patch<EquipmentGroup>(`${apiUrl}/equipment-groups/${id}`, data);
      const i = groups.value.findIndex((g) => Number(g.id) === Number(id));
      if (i !== -1 && res.data) {
        groups.value[i] = res.data;
      }
      return res.data;
    }

    async function remove(id: number) {
      await axios.delete(`${apiUrl}/equipment-groups/${id}`);
      groups.value = groups.value.filter((g) => Number(g.id) !== Number(id));
    }

    async function control(id: number, command: string) {
      const res = await axios.post(`${apiUrl}/equipment-groups/${id}/toggle`, { command });
      return res.data;
    }

    async function controlMode(id: number, mode: EquipmentMode) {
      const res = await axios.post(`${apiUrl}/equipment-groups/${id}/mode`, { mode });
      return res.data;
    }

    function handleEquipmentUpdate(data: {
      equipment_id: number | string;
      mode?: EquipmentMode;
      status?: EquipmentStatus;
    }) {
      const eqId = Number(data.equipment_id);

      groups.value.forEach((group) => {
        if (!group.equipments) return;
        const targetEq = group.equipments.find((eq) => Number(eq.id) === eqId);
        if (targetEq) {
          if (data.mode !== undefined) {
            targetEq.mode = data.mode;
          }
          if (data.status !== undefined) {
            targetEq.status = data.status;
          }
        }
      });
    }

    return {
      groups,
      total,
      fetch,
      create,
      update,
      remove,
      control,
      controlMode,
      handleEquipmentUpdate,
    };
  },
  {
    persist: {
      key: 'equipment-groups-store',
      storage: localStorage,
    },
  },
);
