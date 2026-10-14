import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import { photoFormData } from 'src/utils/imageCompress';
import type { PhotoEntityType, PhotoInfo } from 'src/types/photo';
import { API_URL } from 'src/utils/runtimeConfig';

const apiUrl = API_URL;

export function mainPhotoUrl(entityType: PhotoEntityType, entityId: number, cacheBust?: number): string {
  return `${apiUrl}/photos/${entityType}/${entityId}/main?t=${cacheBust ?? Date.now()}`;
}

export function photoFileUrl(entityType: PhotoEntityType, entityId: number, photoId: number): string {
  return `${apiUrl}/photos/${entityType}/${entityId}/${photoId}/file`;
}

export const usePhotoStore = defineStore('photo', () => {
  const photos = ref<PhotoInfo[]>([]);
  const loading = ref(false);

  async function fetchPhotos(entityType: PhotoEntityType, entityId: number) {
    loading.value = true;
    try {
      const { data } = await axios.get<PhotoInfo[]>(`/photos/${entityType}/${entityId}`);
      photos.value = data;
    } finally {
      loading.value = false;
    }
  }

  async function uploadPhoto(entityType: PhotoEntityType, entityId: number, file: File) {
    const formData = await photoFormData(file);
    const { data } = await axios.post<PhotoInfo>(`/photos/${entityType}/${entityId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    photos.value.push(data);
    return data;
  }

  async function deletePhoto(entityType: PhotoEntityType, entityId: number, photoId: number) {
    await axios.delete(`/photos/${entityType}/${entityId}/${photoId}`);
    photos.value = photos.value.filter((p) => p.id !== photoId);
  }

  async function setMainPhoto(entityType: PhotoEntityType, entityId: number, photoId: number) {
    const { data } = await axios.patch<PhotoInfo>(`/photos/${entityType}/${entityId}/${photoId}/main`);
    photos.value = photos.value.map((p) => ({ ...p, is_main: p.id === data.id }));
    return data;
  }

  /** Ajoute la photo et en fait la photo principale (champ « Photo principale » des formulaires). */
  async function uploadMainPhoto(entityType: PhotoEntityType, entityId: number, file: File) {
    const photo = await uploadPhoto(entityType, entityId, file);
    if (!photo.is_main) await setMainPhoto(entityType, entityId, photo.id);
    return photo;
  }

  return { photos, loading, fetchPhotos, uploadPhoto, deletePhoto, setMainPhoto, uploadMainPhoto };
});
