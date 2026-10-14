import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import { type ControllersPinsList, type ControllerPin, type OneWireScan } from '../types/controller_pin';
import { API_URL } from 'src/utils/runtimeConfig';

const apiUrl = API_URL;

export const useControllerPinStore = defineStore(
  'controller_pin',
  () => {
    const controllers_pins = ref<ControllerPin[]>([]);
    const controllers_availables_pins = ref<ControllerPin[]>([]);
    const total = ref<number>();

    async function fetch() {
      const res = await axios.get<ControllersPinsList>(`${apiUrl}/controllers`);
      controllers_pins.value = res.data.controllers_pins;
      total.value = res.data.total;
    }

    // includePinId : broche actuelle de l'élément modifié (sinon absente, car occupée) ;
    // includeUsed : broches occupées aussi (free: false, used_by), pour les afficher grisées
    async function getAvailablesPins(id: number, includePinId?: number | null, includeUsed = false) {
      const res = await axios.get(`${apiUrl}/controllers/${id}/pins`, {
        params: { ...(includePinId ? { include_pin_id: includePinId } : {}), ...(includeUsed ? { include_used: true } : {}) },
      });

      if (res.data && res.data.controller_pins) {
        // GPIO de l'ESP32 d'abord, puis chaque module dans l'ordre (Module 1 · broches 0 à 7, Module 2…)
        const rank = (p: ControllerPin) => (p.module_id ? (p.module_number ?? 99) : 0);
        const sortedPins = (res.data.controller_pins as ControllerPin[]).sort(
          (a, b) => rank(a) - rank(b) || parseInt(a.pin_number, 10) - parseInt(b.pin_number, 10),
        );

        controllers_availables_pins.value = sortedPins;
      }
    }

    async function scanOneWire(controllerId: number): Promise<OneWireScan> {
      const res = await axios.get<OneWireScan>(`${apiUrl}/controllers/${controllerId}/one-wire/scan`);
      return res.data;
    }

    return { controllers_pins, controllers_availables_pins, fetch, getAvailablesPins, scanOneWire };
  },
  {
    persist: {
      key: 'controller-pins-store',
      storage: localStorage,
    },
  },
);
