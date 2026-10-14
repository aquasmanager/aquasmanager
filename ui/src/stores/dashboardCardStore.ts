import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import type { DashboardCardConfig, DashboardCardCreate, DashboardCardUpdate } from 'src/types/dashboard';

export const useDashboardCardStore = defineStore('dashboardCard', () => {
  const cards = ref<DashboardCardConfig[]>([]);
  const loading = ref(false);

  async function fetchCards(aquariumId: number) {
    loading.value = true;
    try {
      const { data } = await axios.get<DashboardCardConfig[]>('/dashboard-cards/', {
        params: { aquarium_id: aquariumId },
      });
      cards.value = data;
    } finally {
      loading.value = false;
    }
  }

  async function createCard(payload: DashboardCardCreate) {
    const { data } = await axios.post<DashboardCardConfig>('/dashboard-cards/', payload);
    cards.value.push(data);
    return data;
  }

  async function updateCard(id: number, payload: DashboardCardUpdate) {
    const { data } = await axios.patch<DashboardCardConfig>(`/dashboard-cards/${id}`, payload);
    const index = cards.value.findIndex((c) => c.id === id);
    if (index !== -1) {
      cards.value[index] = { ...cards.value[index], ...data };
    }
    return data;
  }

  async function deleteCard(id: number) {
    await axios.delete(`/dashboard-cards/${id}`);
    cards.value = cards.value.filter((c) => c.id !== id);
  }

  /** Nouvel ordre (glisser-déposer) : affiché tout de suite, enregistré ensuite. */
  async function reorderCards(aquariumId: number, ids: number[]) {
    const byId = new Map(cards.value.map((c) => [c.id, c]));
    cards.value = ids.map((id) => byId.get(id)).filter((c): c is DashboardCardConfig => !!c);
    const { data } = await axios.put<DashboardCardConfig[]>('/dashboard-cards/order', { aquarium_id: aquariumId, ids });
    cards.value = data.map((c) => ({ ...byId.get(c.id), ...c }));
  }

  return { cards, loading, fetchCards, createCard, updateCard, deleteCard, reorderCards };
});
