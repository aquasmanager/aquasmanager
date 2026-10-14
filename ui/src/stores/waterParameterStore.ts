import { t } from 'src/i18n/instance';
import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import { isQueued } from 'src/offline/queued';
import type {
  WaterParameter,
  WaterParameterCreate,
  WaterParameterUpdate,
  WaterParameterReading,
  WaterParameterReadingCreate,
  WaterParameterReadingBatchCreate,
  WaterParameterReadingUpdate,
  IcpImportRow,
  IcpLab,
  IcpImportBatch,
  IcpImportBatchCreate,
  IcpBatchReading,
  ParameterTargetDefault,
} from 'src/types/waterParameter';
import { findTargetDefault } from 'src/types/waterParameter';

export const useWaterParameterStore = defineStore('waterParameter', () => {
  const parameters = ref<WaterParameter[]>([]);
  const loading = ref(false);

  const targetDefaults = ref<ParameterTargetDefault[]>([]);

  async function fetchTargetDefaults() {
    if (targetDefaults.value.length > 0) return;
    const { data } = await axios.get<ParameterTargetDefault[]>('/water-parameters/target-defaults');
    targetDefaults.value = data;
  }

  function defaultTargetFor(name: string, unit?: string | null) {
    return findTargetDefault(targetDefaults.value, name, unit);
  }

  async function applyDefaultTargets(aquariumId: number): Promise<string[]> {
    const { data } = await axios.post<{ updated: string[]; parameters: WaterParameter[] }>(
      '/water-parameters/apply-default-targets',
      null,
      { params: { aquarium_id: aquariumId } },
    );
    parameters.value = data.parameters;
    return data.updated;
  }

  async function fetch(aquariumId: number) {
    loading.value = true;
    try {
      const { data } = await axios.get<WaterParameter[]>('/water-parameters/', {
        params: { aquarium_id: aquariumId },
      });
      parameters.value = data;
    } finally {
      loading.value = false;
    }
  }

  async function create(payload: WaterParameterCreate) {
    const { data } = await axios.post<WaterParameter>('/water-parameters/', payload);
    parameters.value.push(data);
    return data;
  }

  async function update(id: number, payload: WaterParameterUpdate) {
    const { data } = await axios.patch<WaterParameter>(`/water-parameters/${id}`, payload);
    const index = parameters.value.findIndex((p) => p.id === id);
    if (index !== -1) parameters.value[index] = data;
    return data;
  }

  async function remove(id: number) {
    await axios.delete(`/water-parameters/${id}`);
    parameters.value = parameters.value.filter((p) => p.id !== id);
  }

  async function fetchReadings(paramId: number, limit?: number): Promise<WaterParameterReading[]> {
    const { data } = await axios.get<WaterParameterReading[]>(`/water-parameters/${paramId}/readings`, {
      params: limit ? { limit } : {},
    });
    return data;
  }

  // Dernière valeur et in_target sont calculés par l'API : on relit le
  // paramètre après chaque modification de ses relevés.
  async function refreshParameter(paramId: number) {
    const { data } = await axios.get<WaterParameter>(`/water-parameters/${paramId}`);
    const index = parameters.value.findIndex((p) => p.id === paramId);
    if (index !== -1) parameters.value[index] = data;
  }

  async function addReading(paramId: number, payload: WaterParameterReadingCreate, refresh = true) {
    const name = parameters.value.find((p) => p.id === paramId)?.name ?? t('notices.parameter');
    const response = await axios.post<WaterParameterReading>(`/water-parameters/${paramId}/readings`, payload, {
      offline: { label: t('notices.readingQueued', { name, value: String(payload.value) }) },
    });
    if (refresh && !isQueued(response)) await refreshParameter(paramId);
    return response.data;
  }

  // Plusieurs relevés d'un coup (même date, même note), puis relecture des paramètres
  async function addReadingsBatch(payload: WaterParameterReadingBatchCreate) {
    const response = await axios.post<WaterParameterReading[]>('/water-parameters/readings/batch', payload, {
      offline: { label: t('notices.batchQueued', payload.values.length), data: [] },
    });
    if (!isQueued(response)) await fetch(payload.aquarium_id);
    return response.data;
  }

  async function updateReading(paramId: number, readingId: number, payload: WaterParameterReadingUpdate) {
    const { data } = await axios.patch<WaterParameterReading>(
      `/water-parameters/${paramId}/readings/${readingId}`,
      payload,
    );
    await refreshParameter(paramId);
    return data;
  }

  async function deleteReading(paramId: number, readingId: number) {
    await axios.delete(`/water-parameters/${paramId}/readings/${readingId}`);
    await refreshParameter(paramId);
  }

  async function parseIcpReport(lab: IcpLab, file: File): Promise<IcpImportRow[]> {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await axios.post<IcpImportRow[]>('/water-parameters/icp-import/parse', formData, {
      params: { lab },
    });
    return data;
  }

  async function fetchIcpBatches(aquariumId: number): Promise<IcpImportBatch[]> {
    const { data } = await axios.get<IcpImportBatch[]>('/water-parameters/icp-batches/', {
      params: { aquarium_id: aquariumId },
    });
    return data;
  }

  async function createIcpBatch(payload: IcpImportBatchCreate): Promise<IcpImportBatch> {
    const { data } = await axios.post<IcpImportBatch>('/water-parameters/icp-batches/', payload);
    return data;
  }

  async function fetchIcpBatchReadings(batchId: number): Promise<IcpBatchReading[]> {
    const { data } = await axios.get<IcpBatchReading[]>(`/water-parameters/icp-batches/${batchId}/readings`);
    return data;
  }

  async function uploadIcpBatchPdf(batchId: number, file: File): Promise<IcpImportBatch> {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await axios.post<IcpImportBatch>(`/water-parameters/icp-batches/${batchId}/pdf`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  }

  async function fetchIcpBatchPdf(batchId: number): Promise<Blob> {
    const { data } = await axios.get<Blob>(`/water-parameters/icp-batches/${batchId}/pdf`, { responseType: 'blob' });
    return data;
  }

  async function deleteIcpBatch(batchId: number) {
    await axios.delete(`/water-parameters/icp-batches/${batchId}`);
  }

  return {
    parameters,
    loading,
    targetDefaults,
    fetchTargetDefaults,
    defaultTargetFor,
    applyDefaultTargets,
    refreshParameter,
    fetch,
    create,
    update,
    remove,
    fetchReadings,
    addReading,
    addReadingsBatch,
    updateReading,
    deleteReading,
    parseIcpReport,
    fetchIcpBatches,
    createIcpBatch,
    fetchIcpBatchReadings,
    deleteIcpBatch,
    uploadIcpBatchPdf,
    fetchIcpBatchPdf,
  };
});
