import { defineStore } from 'pinia';
import axios from 'axios';
import type { SensorHistory, SensorHistoryPeriod } from 'src/types/sensor';
import type { EquipmentActivation } from 'src/types/dashboard';

interface SensorReading {
  id: number;
  sensor_id: number;
  value: number;
  timestamp: string;
}

interface SensorReadingListResponse {
  total: number;
  sensors_reading: SensorReading[];
}

export const useMetricsStore = defineStore('metrics', () => {
  async function fetchSensorHistory(sensorId: number, limit = 20): Promise<number[]> {
    const { data } = await axios.get<SensorReadingListResponse>('/sensors-reading/', {
      params: { sensor_id: sensorId, limit },
    });
    return data.sensors_reading.map((r) => r.value);
  }

  async function fetchEquipmentActivations(equipmentId: number, limit = 20): Promise<EquipmentActivation[]> {
    const { data } = await axios.get<EquipmentActivation[]>(`/equipments/${equipmentId}/activations`, {
      params: { limit },
    });
    // L'API renvoie du plus récent au plus ancien ; on remet en ordre
    // chronologique pour l'affichage (graphique / liste dans le temps).
    return [...data].reverse();
  }

  // Historique regroupé par intervalles (moyenne / min / max) pour les graphiques
  async function fetchSensorPeriodHistory(sensorId: number, period: SensorHistoryPeriod): Promise<SensorHistory> {
    const { data } = await axios.get<SensorHistory>(`/sensors/${sensorId}/history`, { params: { period } });
    return data;
  }

  return { fetchSensorHistory, fetchEquipmentActivations, fetchSensorPeriodHistory };
});
