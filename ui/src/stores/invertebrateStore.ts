import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import { photoFormData } from 'src/utils/imageCompress';
import {
  type InvertebratesList,
  type InvertebrateCreation,
  type Invertebrate,
} from '../types/invertebrate';
import { API_URL } from 'src/utils/runtimeConfig';

const apiUrl = API_URL;

export const useInvertebrateStore = defineStore(
  'invertebrate',
  () => {
    const invertebrates = ref<Invertebrate[]>([]);
    const total = ref<number>();

    // Avec un aquarium : ne recharge que ses invertebrates (les autres restent en cache)
    async function fetch(aquariumId?: number) {
      const res = await axios.get<InvertebratesList>(`${apiUrl}/invertebrates`, {
        params: aquariumId ? { aquarium_id: aquariumId } : {},
      });
      invertebrates.value = aquariumId
        ? [...invertebrates.value.filter((item) => Number(item.aquarium_id) !== aquariumId), ...res.data.invertebrates]
        : res.data.invertebrates;
      if (!aquariumId) total.value = res.data.total;
    }
    async function add(data: InvertebrateCreation, file?: File) {
      const res = await axios.post<Invertebrate>(`${apiUrl}/invertebrates/`, data);

      const invertebrate = res.data;

      if (file) {
        const formData = await photoFormData(file);

        await axios.post(`${apiUrl}/photos/invertebrates/${invertebrate.id}`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      }

      invertebrates.value.push(res.data);
      return invertebrate;
    }
    async function update(data: Invertebrate) {
      await axios.patch(`${apiUrl}/invertebrates/${data.id}`, data);
      const i = invertebrates.value.findIndex((invertebrate) => invertebrate.id === data.id);
      if (i !== -1) invertebrates.value[i] = data;
    }
    async function remove(id: number) {
      await axios.delete(`${apiUrl}/invertebrates/${id}`);
      invertebrates.value = invertebrates.value.filter((invertebrate) => invertebrate.id !== id);
    }
    function getById(id: number): Invertebrate | undefined {
      return invertebrates.value.find((invertebrate) => Number(invertebrate.id) === id);
    }
    function getByAquariumId(aqua_id: number): Invertebrate[] {
      return invertebrates.value.filter(
        (invertebrate) => Number(invertebrate.aquarium_id) === Number(aqua_id),
      );
    }

    return { invertebrates, fetch, add, update, remove, getById, getByAquariumId };
  },
  {
    persist: {
      key: 'invertebrates-store',
      storage: localStorage,
    },
  },
);
