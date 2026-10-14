import { t } from 'src/i18n/instance';
import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import type { Message } from '../types/chat';
import { API_URL } from 'src/utils/runtimeConfig';
import { apiErrorMessage } from 'src/utils/apiError';

const apiUrl = API_URL;

export const useChatStore = defineStore(
  'chat',
  () => {
    const messages = ref<Message[]>([
      {
        id: 1,
        author: 'Assistant',
        text: 'Bonjour! Je suis votre assistant. Comment puis-je vous aider ?',
        stamp: new Date(),
      },
    ]);
    const isLoading = ref<boolean>(false);

    async function sendMessage(userText: string) {
      const userMsg: Message = {
        id: Date.now(),
        author: 'Me',
        text: userText,
        stamp: new Date(),
      };

      messages.value.push(userMsg);
      isLoading.value = true;

      try {
        const response = await axios.post(`${apiUrl}/chat/`, { prompt: userText });

        messages.value.push({
          id: Date.now() + 1,
          author: 'Assistant',
          text: response.data.answer,
          stamp: new Date(),
        });
      } catch (error) {
        messages.value.push({
          id: Date.now() + 1,
          author: 'Assistant',
          text: apiErrorMessage(error, t('notices.assistantFailed')),
          stamp: new Date(),
        });
      } finally {
        isLoading.value = false;
      }
    }

    return { messages, isLoading, sendMessage };
  },
  {
    persist: {
      key: 'chat-store',
      storage: localStorage,
    },
  },
);
