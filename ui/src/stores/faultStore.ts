import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import { API_URL } from 'src/utils/runtimeConfig';
import { t } from 'src/i18n/instance';

const apiUrl = API_URL;

export interface EquipmentFault {
  id: number;
  controller_id: number;
  equipment_id: number | null;
  code: string;
  message: string;
  latched: boolean;
  created_at: string;
  resolved_at: string | null;
}

// Titres : alerts.faults.* (codes envoyés par le firmware)
const FAULT_CODES = ['LEVEL_TIMEOUT', 'TOO_MANY_CYCLES', 'SENSOR_INTERLOCK', 'NOTIFY'];

export function faultTitle(fault: EquipmentFault): string {
  return t(`alerts.faults.${FAULT_CODES.includes(fault.code) ? fault.code : 'default'}`);
}

export const useFaultStore = defineStore('fault', () => {
  const faults = ref<EquipmentFault[]>([]);

  const openFaults = computed(() => faults.value.filter((f) => f.resolved_at === null));

  async function fetchOpen() {
    const res = await axios.get<{ total: number; faults: EquipmentFault[] }>(`${apiUrl}/faults/`, {
      params: { resolved: false },
    });
    faults.value = res.data.faults;
  }

  async function fetchAll(): Promise<EquipmentFault[]> {
    const res = await axios.get<{ total: number; faults: EquipmentFault[] }>(`${apiUrl}/faults/`);
    return res.data.faults;
  }

  function handleWsFault(data: {
    id?: number | string | undefined;
    equipment_id?: number | string | null | undefined;
    equipment_name?: string | null | undefined;
    code?: string | undefined;
    message?: string | undefined;
    latched?: boolean | undefined;
    resolved?: boolean | undefined;
  }) {
    if (data.id === undefined) return;
    const id = Number(data.id);

    if (data.resolved) {
      const idx = faults.value.findIndex((f) => f.id === id);
      if (idx !== -1) {
        faults.value.splice(idx, 1);
      }
      return;
    }

    const existing = faults.value.find((f) => f.id === id);
    if (existing) return;

    faults.value.unshift({
      id,
      controller_id: 0,
      equipment_id: data.equipment_id !== undefined && data.equipment_id !== null ? Number(data.equipment_id) : null,
      code: data.code ?? 'UNKNOWN',
      message: data.message ?? `${data.equipment_name ?? ''} ${data.code ?? ''}`.trim(),
      latched: !!data.latched,
      created_at: new Date().toISOString(),
      resolved_at: null,
    });
  }

  async function acknowledge(faultId: number) {
    await axios.post(`${apiUrl}/faults/${faultId}/acknowledge`);
    const idx = faults.value.findIndex((f) => f.id === faultId);
    if (idx !== -1) faults.value.splice(idx, 1);
  }

  async function clearEquipmentFault(equipmentId: number) {
    await axios.post(`${apiUrl}/equipments/${equipmentId}/fault/clear`);
  }

  return {
    faults,
    openFaults,
    fetchOpen,
    fetchAll,
    handleWsFault,
    acknowledge,
    clearEquipmentFault,
  };
});
