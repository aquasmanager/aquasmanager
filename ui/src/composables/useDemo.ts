// Instance de démonstration (AQUAS_APP_ENV=demo) : identifiants du compte de
// démo, servis par l'API (GET /public/demo/), chargés une seule fois
import axios from 'axios';
import { ref } from 'vue';
import { APP_ENV } from 'src/utils/runtimeConfig';

export interface DemoInfo {
  username: string;
  password: string;
  reset_hour: number;
  timezone: string;
}

export const IS_DEMO = APP_ENV === 'demo';

const info = ref<DemoInfo | null>(null);
let loading: Promise<void> | null = null;

export function useDemo() {
  if (IS_DEMO && !loading) {
    loading = axios
      .get<DemoInfo>('/public/demo/')
      .then(({ data }) => {
        info.value = data;
      })
      .catch(() => {
        loading = null;
      });
  }
  return { isDemo: IS_DEMO, info };
}
