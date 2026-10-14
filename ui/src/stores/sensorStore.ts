import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import type { SensorsList, Sensor, SensorCreation } from '../types/sensor';
import { API_URL } from 'src/utils/runtimeConfig';

const apiUrl = API_URL;

export const useSensorStore = defineStore(
  'Sensor',
  () => {
    const sensors = ref<Sensor[]>([]);
    const total = ref<number>();

    async function fetch() {
      const res = await axios.get<SensorsList>(`${apiUrl}/sensors`);
      sensors.value = res.data.sensors;
      total.value = res.data.total;
    }
    async function add(data: SensorCreation) {
      const res = await axios.post<Sensor>(`${apiUrl}/sensors/`, data);

      const sensor = res.data;

      sensors.value.push(res.data);
      return sensor;
    }
    async function update(data: Partial<Sensor> & { id: number }) {
      const res = await axios.patch<Sensor>(`${apiUrl}/sensors/${data.id}`, data);
      const i = sensors.value.findIndex((sensor) => sensor.id === data.id);
      // La liste porte aussi pin_number, absent de la réponse du PATCH
      if (i !== -1) sensors.value[i] = { ...sensors.value[i], ...res.data };
      return res.data;
    }
    async function remove(id: number) {
      await axios.delete(`${apiUrl}/sensors/${id}`);
      sensors.value = sensors.value.filter((sensor) => sensor.id !== id);
    }
    function getById(id: number): Sensor | undefined {
      return sensors.value.find((sensor) => Number(sensor.id) === id);
    }
    function getByAquariumId(aqua_id: number): Sensor[] {
      return sensors.value.filter((sensor) => Number(sensor.aquarium_id) === Number(aqua_id));
    }

    return { sensors, fetch, add, update, remove, getById, getByAquariumId };
  },
  {
    persist: {
      key: 'sensors-store',
      storage: localStorage,
    },
  },
);
