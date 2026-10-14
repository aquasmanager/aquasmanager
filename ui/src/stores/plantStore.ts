import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import { photoFormData } from 'src/utils/imageCompress';
import { type PlantsList, type PlantCreation, type Plant } from '../types/plant';
import { API_URL } from 'src/utils/runtimeConfig';

const apiUrl = API_URL;

export const usePlantStore = defineStore(
  'plant',
  () => {
    const plants = ref<Plant[]>([]);
    const total = ref<number>();

    // Avec un aquarium : ne recharge que ses plants (les autres restent en cache)
    async function fetch(aquariumId?: number) {
      const res = await axios.get<PlantsList>(`${apiUrl}/plants`, {
        params: aquariumId ? { aquarium_id: aquariumId } : {},
      });
      plants.value = aquariumId
        ? [...plants.value.filter((item) => Number(item.aquarium_id) !== aquariumId), ...res.data.plants]
        : res.data.plants;
      if (!aquariumId) total.value = res.data.total;
    }
    async function add(data: PlantCreation, file?: File) {
      const res = await axios.post<Plant>(`${apiUrl}/plants/`, data);

      const plant = res.data;

      if (file) {
        const formData = await photoFormData(file);

        await axios.post(`${apiUrl}/photos/plants/${plant.id}`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      }

      plants.value.push(res.data);
      return plant;
    }
    async function update(data: Plant) {
      await axios.patch(`${apiUrl}/plants/${data.id}`, data);
      const i = plants.value.findIndex((plant) => plant.id === data.id);
      if (i !== -1) plants.value[i] = data;
    }
    async function remove(id: number) {
      await axios.delete(`${apiUrl}/plants/${id}`);
      plants.value = plants.value.filter((plant) => plant.id !== id);
    }
    function getById(id: number): Plant | undefined {
      return plants.value.find((plant) => Number(plant.id) === id);
    }
    function getByAquariumId(aqua_id: number): Plant[] {
      return plants.value.filter((plant) => Number(plant.aquarium_id) === Number(aqua_id));
    }

    return { plants, fetch, add, update, remove, getById, getByAquariumId };
  },
  {
    persist: {
      key: 'plants-store',
      storage: localStorage,
    },
  },
);
