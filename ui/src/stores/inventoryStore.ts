import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import { t } from 'src/i18n/instance';
import { useOfflineStore } from 'src/stores/offlineStore';
import type {
  InventoryItem,
  InventoryItemCreate,
  InventoryItemUpdate,
  InventoryMovement,
  InventoryMovementCreate,
} from 'src/types/inventory';

export const useInventoryStore = defineStore('inventory', () => {
  const items = ref<InventoryItem[]>([]);
  const loading = ref(false);

  async function fetch(aquariumId: number) {
    loading.value = true;
    try {
      const { data } = await axios.get<InventoryItem[]>('/inventory-items/', {
        params: { aquarium_id: aquariumId },
      });
      items.value = withPendingMovements(data);
    } finally {
      loading.value = false;
    }
  }

  async function create(payload: InventoryItemCreate) {
    const { data } = await axios.post<InventoryItem>('/inventory-items/', payload);
    items.value.push(data);
    return data;
  }

  async function update(id: number, payload: InventoryItemUpdate) {
    const { data } = await axios.patch<InventoryItem>(`/inventory-items/${id}`, payload);
    const index = items.value.findIndex((i) => i.id === id);
    if (index !== -1) items.value[index] = data;
    return data;
  }

  async function remove(id: number) {
    await axios.delete(`/inventory-items/${id}`);
    items.value = items.value.filter((i) => i.id !== id);
  }

  // Hors connexion : les données lues peuvent dater ; on y ajoute les
  // mouvements qui attendent l'envoi
  function withPendingMovements(list: InventoryItem[]): InventoryItem[] {
    const deltas = new Map<number, number>();
    for (const op of useOfflineStore().pending) {
      const match = /^\/inventory-items\/(\d+)\/movements$/.exec(op.url);
      const delta = (op.data as { delta?: unknown } | null)?.delta;
      if (op.method === 'POST' && match && typeof delta === 'number') {
        deltas.set(Number(match[1]), (deltas.get(Number(match[1])) ?? 0) + delta);
      }
    }
    return list.map((item) => (deltas.has(item.id) ? { ...item, quantity: item.quantity + deltas.get(item.id)! } : item));
  }

  async function addMovement(id: number, payload: InventoryMovementCreate) {
    const current = items.value.find((i) => i.id === id);
    const { data } = await axios.post<InventoryItem>(`/inventory-items/${id}/movements`, payload, {
      // Hors connexion : quantité mise à jour à l'écran, envoyée au retour du réseau
      offline: {
        label: t('notices.movementQueued', {
          name: current?.name ?? id,
          delta: `${payload.delta > 0 ? '+' : ''}${payload.delta}`,
          unit: current?.unit ?? '',
        }),
        data: current ? { ...current, quantity: current.quantity + payload.delta } : null,
      },
    });
    const index = items.value.findIndex((i) => i.id === id);
    if (index !== -1 && data) items.value[index] = data;
    return data;
  }

  async function fetchMovements(id: number): Promise<InventoryMovement[]> {
    const { data } = await axios.get<InventoryMovement[]>(`/inventory-items/${id}/movements`);
    return data;
  }

  return { items, loading, fetch, create, update, remove, addMovement, fetchMovements };
});
