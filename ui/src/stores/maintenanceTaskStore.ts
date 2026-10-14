import { t } from 'src/i18n/instance';
import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import type {
  CalendarEvent,
  MaintenanceTask,
  MaintenanceTaskCreate,
  MaintenanceTaskUpdate,
  MaintenanceTaskCompletion,
  MaintenanceTaskCompletionCreate,
} from 'src/types/maintenanceTask';

export const useMaintenanceTaskStore = defineStore('maintenanceTask', () => {
  const tasks = ref<MaintenanceTask[]>([]);
  const loading = ref(false);

  async function fetch(aquariumId: number) {
    loading.value = true;
    try {
      const { data } = await axios.get<MaintenanceTask[]>('/maintenance-tasks/', {
        params: { aquarium_id: aquariumId },
      });
      tasks.value = data;
    } finally {
      loading.value = false;
    }
  }

  async function create(payload: MaintenanceTaskCreate) {
    const { data } = await axios.post<MaintenanceTask>('/maintenance-tasks/', payload);
    tasks.value.push(data);
    return data;
  }

  async function update(id: number, payload: MaintenanceTaskUpdate) {
    const { data } = await axios.patch<MaintenanceTask>(`/maintenance-tasks/${id}`, payload);
    const index = tasks.value.findIndex((t) => t.id === id);
    if (index !== -1) tasks.value[index] = data;
    return data;
  }

  async function remove(id: number) {
    await axios.delete(`/maintenance-tasks/${id}`);
    tasks.value = tasks.value.filter((t) => t.id !== id);
  }

  async function complete(id: number, payload: MaintenanceTaskCompletionCreate) {
    const current = tasks.value.find((t) => t.id === id);
    const response = await axios.post<MaintenanceTask>(`/maintenance-tasks/${id}/complete`, payload, {
      // Hors connexion : tâche marquée faite à l'écran, envoyée au retour du réseau
      offline: {
        label: t('notices.taskDoneQueued', { title: current?.title ?? id }),
        data: current ? { ...current, last_completed_at: payload.completed_at ?? new Date().toISOString() } : null,
      },
    });
    const data = response.data ?? current;
    const index = tasks.value.findIndex((t) => t.id === id);
    if (index !== -1 && data) tasks.value[index] = data;
    return data;
  }

  async function fetchCompletions(id: number): Promise<MaintenanceTaskCompletion[]> {
    const { data } = await axios.get<MaintenanceTaskCompletion[]>(`/maintenance-tasks/${id}/completions`);
    return data;
  }

  async function fetchCalendar(start: string, end: string, aquariumId?: number | null): Promise<CalendarEvent[]> {
    const { data } = await axios.get<CalendarEvent[]>('/maintenance-tasks/calendar', {
      params: { start, end, ...(aquariumId ? { aquarium_id: aquariumId } : {}) },
    });
    return data;
  }

  async function deleteCompletion(taskId: number, completionId: number) {
    await axios.delete(`/maintenance-tasks/${taskId}/completions/${completionId}`);
  }

  return { tasks, loading, fetch, create, update, remove, complete, fetchCompletions, deleteCompletion, fetchCalendar };
});
