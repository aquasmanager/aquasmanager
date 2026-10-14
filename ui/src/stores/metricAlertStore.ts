import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import type { MetricAlert } from 'src/types/metricAlert';

export const useMetricAlertStore = defineStore('metricAlert', () => {
  // État partagé (comme faultStore) : n'importe quelle page qui acquitte
  // une alerte met à jour ce même état, donc le badge de l'onglet et la
  // page Alertes restent synchronisés sans dépendre du prochain poll.
  const alerts = ref<MetricAlert[]>([]);
  const openAlerts = computed(() => alerts.value.filter((a) => a.resolved_at == null));

  async function fetchOpen(aquariumId: number) {
    const { data } = await axios.get<MetricAlert[]>('/metric-alerts/', {
      params: { aquarium_id: aquariumId, resolved: false },
    });
    alerts.value = data;
  }

  // Historique (résolues incluses) : vue indépendante, ne remplace pas
  // l'état partagé "ouvertes" utilisé par le badge/la page en direct.
  async function fetchAll(aquariumId: number): Promise<MetricAlert[]> {
    const { data } = await axios.get<MetricAlert[]>('/metric-alerts/', {
      params: { aquarium_id: aquariumId },
    });
    return data;
  }

  async function acknowledge(alertId: number): Promise<MetricAlert> {
    const { data } = await axios.post<MetricAlert>(`/metric-alerts/${alertId}/acknowledge`);
    const idx = alerts.value.findIndex((a) => a.id === alertId);
    if (idx !== -1) alerts.value.splice(idx, 1);
    return data;
  }

  return { alerts, openAlerts, fetchOpen, fetchAll, acknowledge };
});
