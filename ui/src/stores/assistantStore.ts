import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import type { AssistantStatus } from 'src/types/assistant';

// État de l'assistant IA (activé ou non) : affiche ou masque son bouton
export const useAssistantStore = defineStore('assistant', () => {
  const status = ref<AssistantStatus>({ enabled: false, provider: null, model: null, external: false });

  async function fetchStatus() {
    try {
      status.value = (await axios.get<AssistantStatus>('/assistant/status')).data;
    } catch {
      status.value = { enabled: false, provider: null, model: null, external: false };
    }
  }

  return { status, fetchStatus };
});
