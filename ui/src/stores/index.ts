import { defineStore } from '#q-app/wrappers';
import { createPinia } from 'pinia';
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate';

// Pinia, avec persistance de certains stores dans le stockage du navigateur
export default defineStore((/* { ssrContext } */) => {
  const pinia = createPinia();
  pinia.use(piniaPluginPersistedstate);

  return pinia;
});
