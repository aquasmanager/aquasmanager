import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import { photoFormData } from 'src/utils/imageCompress';
import { type AquariumCreation, type Aquarium, type AquariumsList } from '../types/Aquarium';
import { API_URL } from 'src/utils/runtimeConfig';

const apiUrl = API_URL;

export const useAquariumStore = defineStore(
  'aquarium',
  () => {
    const aquariums = ref<Aquarium[]>([]);
    const total = ref<number>();

    async function fetch() {
      const res = await axios.get<AquariumsList>(`${apiUrl}/aquariums`);
      aquariums.value = res.data.aquariums;
      total.value = res.data.total;
    }

    async function add(data: AquariumCreation, file?: File) {
      // 1. Création de l'aquarium en base
      const res = await axios.post<Aquarium>(`${apiUrl}/aquariums/`, data);
      const aquarium = res.data;

      // 2. Upload de la photo si présente
      if (file) {
        const formData = await photoFormData(file);
        await axios.post(`${apiUrl}/photos/aquariums/${aquarium.id}`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      }

      await fetch(); // Rafraîchir pour avoir les bonnes données
      return aquarium;
    }

    async function update(data: Aquarium, file?: File) {
      // 1. Mise à jour des données texte
      await axios.patch(`${apiUrl}/aquariums/${data.id}`, data);

      // 2. Upload de la nouvelle photo si présente
      if (file) {
        const formData = await photoFormData(file);

        await axios.post(`${apiUrl}/photos/aquariums/${data.id}`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      }

      await fetch(); // Rafraîchir pour mettre à jour la liste et les images
    }

    async function remove(id: number) {
      await axios.delete(`${apiUrl}/aquariums/${id}`);
      await fetch(); // Le backend supprime les photos via `delete_photos_entity`
    }

    function getById(id: number): Aquarium | undefined {
      return aquariums.value.find((aqua) => Number(aqua.id) === id);
    }

    return { aquariums, fetch, add, update, remove, getById };
  },
  {
    persist: {
      key: 'aquariums-store',
      storage: localStorage,
    },
  },
);
