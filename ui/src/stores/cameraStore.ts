import { defineStore } from 'pinia';
import { ref } from 'vue';
import axios from 'axios';
import type { Camera, CameraForm, CameraQuality, CameraStatus } from 'src/types/camera';
import type { PhotoInfo } from 'src/types/photo';

/**
 * Caméras IP des aquariums (optionnel : désactivé tant que le service vidéo
 * go2rtc n'est pas installé). Images et direct passent toujours par l'API.
 */
export const useCameraStore = defineStore('camera', () => {
  const status = ref<CameraStatus | null>(null);
  const cameras = ref<Camera[]>([]);
  const loading = ref(false);
  let statusRequest: Promise<CameraStatus> | null = null;

  async function fetchStatus(): Promise<CameraStatus> {
    if (status.value) return status.value;
    statusRequest ??= axios
      .get<CameraStatus>('/cameras/status')
      .then(({ data }) => (status.value = data))
      .finally(() => (statusRequest = null));
    return statusRequest;
  }

  async function fetchCameras(aquariumId: number) {
    loading.value = true;
    try {
      cameras.value = (await axios.get<Camera[]>('/cameras/', { params: { aquarium_id: aquariumId } })).data;
    } finally {
      loading.value = false;
    }
  }

  async function createCamera(aquariumId: number, form: CameraForm) {
    const { data } = await axios.post<Camera>('/cameras/', { ...form, aquarium_id: aquariumId });
    cameras.value.push(data);
    return data;
  }

  async function updateCamera(id: number, form: CameraForm) {
    const { data } = await axios.put<Camera>(`/cameras/${id}`, form);
    const index = cameras.value.findIndex((c) => c.id === id);
    if (index >= 0) cameras.value[index] = data;
    return data;
  }

  async function deleteCamera(id: number) {
    await axios.delete(`/cameras/${id}`);
    cameras.value = cameras.value.filter((c) => c.id !== id);
  }

  async function testCamera(payload: {
    camera_id?: number | null;
    host: string;
    port: number;
    username: string;
    password: string;
    path: string;
  }) {
    return (await axios.post<{ ok: boolean; message: string }>('/cameras/test', payload)).data.message;
  }

  /**
   * Image JPEG (adresse locale à libérer avec URL.revokeObjectURL). En cas
   * d'échec, le message de l'API (reçu en blob) est remis dans l'erreur.
   */
  async function snapshotUrl(id: number, quality: CameraQuality = 'sub'): Promise<string> {
    try {
      const { data } = await axios.get<Blob>(`/cameras/${id}/snapshot`, { params: { quality }, responseType: 'blob' });
      return URL.createObjectURL(data);
    } catch (err) {
      const body = (err as { response?: { data?: unknown } }).response?.data;
      if (body instanceof Blob) {
        const detail = await body
          .text()
          .then((text) => (JSON.parse(text) as { detail?: unknown }).detail)
          .catch(() => undefined);
        if (typeof detail === 'string') throw new Error(detail);
      }
      throw err;
    }
  }

  async function capture(id: number) {
    return (await axios.post<PhotoInfo>(`/cameras/${id}/capture`)).data;
  }

  return {
    status,
    cameras,
    loading,
    fetchStatus,
    fetchCameras,
    createCamera,
    updateCamera,
    deleteCamera,
    testCamera,
    snapshotUrl,
    capture,
  };
});
