import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import { photoFormData } from 'src/utils/imageCompress';
import { type FishesList, type FishCreation, type Fish } from '../types/fish';
import { API_URL } from 'src/utils/runtimeConfig';

const apiUrl = API_URL;

export const useFishStore = defineStore(
  'Fish',
  () => {
    const fishes = ref<Fish[]>([]);
    const total = ref<number>();

    // Avec un aquarium : ne recharge que ses fishes (les autres restent en cache)
    async function fetch(aquariumId?: number) {
      const res = await axios.get<FishesList>(`${apiUrl}/fishes`, {
        params: aquariumId ? { aquarium_id: aquariumId } : {},
      });
      fishes.value = aquariumId
        ? [...fishes.value.filter((item) => Number(item.aquarium_id) !== aquariumId), ...res.data.fishes]
        : res.data.fishes;
      if (!aquariumId) total.value = res.data.total;
    }
    async function add(data: FishCreation, file?: File) {
      const res = await axios.post<Fish>(`${apiUrl}/fishes/`, data);

      const Fish = res.data;

      if (file) {
        const formData = await photoFormData(file);

        await axios.post(`${apiUrl}/photos/fishes/${Fish.id}`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      }

      fishes.value.push(res.data);
      return Fish;
    }
    async function update(data: Fish) {
      await axios.patch(`${apiUrl}/fishes/${data.id}`, data);
      const i = fishes.value.findIndex((fish) => fish.id === data.id);
      if (i !== -1) fishes.value[i] = data;
    }
    async function remove(id: number) {
      await axios.delete(`${apiUrl}/fishes/${id}`);
      fishes.value = fishes.value.filter((fish) => fish.id !== id);
    }
    function getById(id: number): Fish | undefined {
      return fishes.value.find((fish) => Number(fish.id) === id);
    }
    function getByAquariumId(aqua_id: number): Fish[] {
      return fishes.value.filter((fish) => Number(fish.aquarium_id) === Number(aqua_id));
    }

    return { fishes, fetch, add, update, remove, getById, getByAquariumId };
  },
  {
    persist: {
      key: 'fishes-store',
      storage: localStorage,
    },
  },
);
