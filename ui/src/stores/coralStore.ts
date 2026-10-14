import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import { photoFormData } from 'src/utils/imageCompress';
import { type CoralsList, type CoralCreation, type Coral } from '../types/coral';
import { API_URL } from 'src/utils/runtimeConfig';

const apiUrl = API_URL;

export const useCoralStore = defineStore(
  'coral',
  () => {
    const corals = ref<Coral[]>([]);
    const total = ref<number>();

    // Avec un aquarium : ne recharge que ses corals (les autres restent en cache)
    async function fetch(aquariumId?: number) {
      const res = await axios.get<CoralsList>(`${apiUrl}/corals`, {
        params: aquariumId ? { aquarium_id: aquariumId } : {},
      });
      corals.value = aquariumId
        ? [...corals.value.filter((item) => Number(item.aquarium_id) !== aquariumId), ...res.data.corals]
        : res.data.corals;
      if (!aquariumId) total.value = res.data.total;
    }
    async function add(data: CoralCreation, file?: File) {
      const res = await axios.post<Coral>(`${apiUrl}/corals/`, data);

      const coral = res.data;

      if (file) {
        const formData = await photoFormData(file);

        await axios.post(`${apiUrl}/photos/corals/${coral.id}`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      }

      corals.value.push(res.data);
      return coral;
    }
    async function update(data: Coral) {
      await axios.patch(`${apiUrl}/corals/${data.id}`, data);
      const i = corals.value.findIndex((coral) => coral.id === data.id);
      if (i !== -1) corals.value[i] = data;
    }
    async function remove(id: number) {
      await axios.delete(`${apiUrl}/corals/${id}`);
      corals.value = corals.value.filter((coral) => coral.id !== id);
    }
    function getById(id: number): Coral | undefined {
      return corals.value.find((coral) => Number(coral.id) === id);
    }
    function getByAquariumId(aqua_id: number): Coral[] {
      return corals.value.filter((coral) => Number(coral.aquarium_id) === Number(aqua_id));
    }

    return { corals, fetch, add, update, remove, getById, getByAquariumId };
  },
  {
    persist: {
      key: 'corals-store',
      storage: localStorage,
    },
  },
);
