<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue';
import { useWebSocketStore } from 'src/stores/websocket';
import { useFaultStore } from 'src/stores/faultStore';
import { useAuthStore } from 'src/stores/authStore';

const wsStore = useWebSocketStore();
const faultStore = useFaultStore();
const authStore = useAuthStore();

onMounted(() => {
  // Pas de compte sur les pages publiques (signature, vitrine) : ni temps réel ni défauts
  if (authStore.accessToken) {
    wsStore.connect();
    void faultStore.fetchOpen();
  }
});

// Connexion / déconnexion : ouverture ou fermeture du flux temps réel
watch(
  () => Boolean(authStore.accessToken),
  (loggedIn, wasLoggedIn) => {
    if (loggedIn && !wasLoggedIn) {
      wsStore.connect();
      void faultStore.fetchOpen();
    } else if (!loggedIn && wasLoggedIn) {
      wsStore.disconnect();
    }
  },
);
</script>
