/**
 * Licence de l'installation : fonctionnalités ouvertes (ex. « bourse »).
 * Gardée sur l'appareil pour que menus et pages restent justes hors connexion.
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';

export interface LicenseStatus {
  valid: boolean;
  source: 'app' | 'env' | null;
  features: string[];
  paid_features: Record<string, string>;
  license_id: string | null;
  client: string | null;
  issued: string | null;
  expires: string | null;
  error: string | null;
  instance_id: string;
}

export type Feature = 'bourse' | 'assistant';

export const useLicenseStore = defineStore(
  'license',
  () => {
    const status = ref<LicenseStatus | null>(null);
    let pending: Promise<void> | null = null;

    // Fonctionnalité soumise à licence : ouverte seulement si la clé l'inclut
    function has(feature: Feature): boolean {
      if (!status.value) return false;
      return !(feature in status.value.paid_features) || status.value.features.includes(feature);
    }

    async function refresh() {
      status.value = (await axios.get<LicenseStatus>('/license/')).data;
    }

    /** Chargée une fois (garde des routes) ; la valeur gardée sert en attendant. */
    function ensure(): Promise<void> {
      if (status.value) {
        void refresh().catch(() => undefined);
        return Promise.resolve();
      }
      pending ??= refresh()
        .catch(() => undefined)
        .finally(() => (pending = null));
      return pending;
    }

    async function save(key: string) {
      status.value = (await axios.put<LicenseStatus>('/license/', { key })).data;
    }

    async function remove() {
      status.value = (await axios.delete<LicenseStatus>('/license/')).data;
    }

    const bourse = computed(() => has('bourse'));

    return { status, has, bourse, refresh, ensure, save, remove };
  },
  {
    persist: {
      key: 'license-store',
      storage: localStorage,
      pick: ['status'],
    },
  },
);
