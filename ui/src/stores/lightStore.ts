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
import { useControllerStore } from 'src/stores/controllerStore';

export const useLightStore = defineStore('lights', () => {
  const lights = ref<Light[]>([]);
  const spectra = ref<Spectrum[]>([]);
  const profiles = ref<LightProfile[]>([]);
  // Fuseau des contrôleurs (firmware), pour le repère « maintenant »
  const timezone = ref<string | undefined>(undefined);
  const loading = ref(false);

  // Chaque route renvoie la lampe complète à jour : on remplace la copie locale
  function upsert(light: Light): Light {
    const index = lights.value.findIndex((l) => l.id === light.id);
    if (index === -1) lights.value.push(light);
    else lights.value[index] = light;
    return light;
  }

  // Câblage modifié (lampe, canal, broche) : l'API marque le contrôleur « à reflasher ».
  // On relit les contrôleurs pour afficher le bandeau de flash sans recharger la page.
  function refreshControllers() {
    void useControllerStore().fetch().catch(() => undefined);
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
    const { data } = await axios.get<{ spectra: Spectrum[]; profiles: LightProfile[]; timezone?: string }>('/lights/catalog');
    spectra.value = data.spectra;
    profiles.value = data.profiles;
    timezone.value = data.timezone;
  }

  async function create(payload: LightInput) {
    const light = upsert((await axios.post<Light>('/lights/', payload)).data);
    refreshControllers();
    return light;
  }

  async function update(id: number, payload: Partial<LightInput>) {
    const light = upsert((await axios.patch<Light>(`/lights/${id}`, payload)).data);
    refreshControllers();
    return light;
  }

  async function remove(id: number) {
    await axios.delete(`/lights/${id}`);
    refreshControllers();
    lights.value = lights.value.filter((l) => l.id !== id);
  }

  async function addChannel(lightId: number, payload: LightChannelInput) {
    const light = upsert((await axios.post<Light>(`/lights/${lightId}/channels`, payload)).data);
    refreshControllers();
    return light;
  }

  async function updateChannel(channelId: number, payload: Partial<LightChannelInput>) {
    const light = upsert((await axios.patch<Light>(`/lights/channels/${channelId}`, payload)).data);
    refreshControllers();
    return light;
  }

  async function removeChannel(channelId: number) {
    const light = upsert((await axios.delete<Light>(`/lights/channels/${channelId}`)).data);
    refreshControllers();
    return light;
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
    timezone,
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
