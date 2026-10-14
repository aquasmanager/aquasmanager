import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import type {
  ChannelMode,
  Light,
  LightChannelInput,
  LightInput,
  LightProfile,
  SchedulePoint,
  Spectrum,
} from 'src/types/light';

export const useLightStore = defineStore('lights', () => {
  const lights = ref<Light[]>([]);
  const spectra = ref<Spectrum[]>([]);
  const profiles = ref<LightProfile[]>([]);
  const loading = ref(false);

  // Chaque route renvoie la lampe complète à jour : on remplace la copie locale
  function upsert(light: Light): Light {
    const index = lights.value.findIndex((l) => l.id === light.id);
    if (index === -1) lights.value.push(light);
    else lights.value[index] = light;
    return light;
  }

  async function fetch(aquariumId: number) {
    loading.value = true;
    try {
      const { data } = await axios.get<Light[]>('/lights/', { params: { aquarium_id: aquariumId } });
      lights.value = data;
    } finally {
      loading.value = false;
    }
  }

  async function fetchCatalog() {
    if (spectra.value.length > 0) return;
    const { data } = await axios.get<{ spectra: Spectrum[]; profiles: LightProfile[] }>('/lights/catalog');
    spectra.value = data.spectra;
    profiles.value = data.profiles;
  }

  async function create(payload: LightInput) {
    return upsert((await axios.post<Light>('/lights/', payload)).data);
  }

  async function update(id: number, payload: Partial<LightInput>) {
    return upsert((await axios.patch<Light>(`/lights/${id}`, payload)).data);
  }

  async function remove(id: number) {
    await axios.delete(`/lights/${id}`);
    lights.value = lights.value.filter((l) => l.id !== id);
  }

  async function addChannel(lightId: number, payload: LightChannelInput) {
    return upsert((await axios.post<Light>(`/lights/${lightId}/channels`, payload)).data);
  }

  async function updateChannel(channelId: number, payload: Partial<LightChannelInput>) {
    return upsert((await axios.patch<Light>(`/lights/channels/${channelId}`, payload)).data);
  }

  async function removeChannel(channelId: number) {
    return upsert((await axios.delete<Light>(`/lights/channels/${channelId}`)).data);
  }

  async function setSchedule(channelId: number, points: SchedulePoint[]) {
    return upsert((await axios.put<Light>(`/lights/channels/${channelId}/schedule`, points)).data);
  }

  async function copySchedule(lightId: number, sourceChannelId: number, targetChannelIds: number[]) {
    const { data } = await axios.post<Light>(`/lights/${lightId}/copy-schedule`, {
      source_channel_id: sourceChannelId,
      target_channel_ids: targetChannelIds,
    });
    return upsert(data);
  }

  async function applyProfile(lightId: number, profile: string, moonlight: boolean, start?: number) {
    return upsert((await axios.post<Light>(`/lights/${lightId}/apply-profile`, { profile, moonlight, start })).data);
  }

  async function control(lightId: number, mode: ChannelMode, channelId?: number, value?: number) {
    const { data } = await axios.post<Light>(`/lights/${lightId}/control`, {
      mode,
      ...(channelId !== undefined ? { channel_id: channelId } : {}),
      ...(value !== undefined ? { value } : {}),
    });
    return upsert(data);
  }

  async function startDemo(lightId: number, durationS: number) {
    await axios.post(`/lights/${lightId}/demo`, { duration_s: durationS });
  }

  async function stopDemo(lightId: number) {
    await axios.delete(`/lights/${lightId}/demo`);
  }

  return {
    lights,
    spectra,
    profiles,
    loading,
    fetch,
    fetchCatalog,
    create,
    update,
    remove,
    addChannel,
    updateChannel,
    removeChannel,
    setSchedule,
    copySchedule,
    applyProfile,
    control,
    startDemo,
    stopDemo,
  };
});
