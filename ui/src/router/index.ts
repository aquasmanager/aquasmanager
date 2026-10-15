import { defineRouter } from '#q-app';
import {
  createMemoryHistory,
  createRouter,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router';
import routes from './routes';

// Routeur : historique HTML5 ou hash selon build.vueRouterMode (quasar.config.ts)
export default defineRouter(function (/* { store, ssrContext } */) {
  const createHistory = import.meta.env.QUASAR_SERVER
    ? createMemoryHistory
    : import.meta.env.QUASAR_VUE_ROUTER_MODE === 'history'
      ? createWebHistory
      : createWebHashHistory;

  const Router = createRouter({
    // Nouvelle page : en haut. Même page avec un autre paramètre (onglet d'un
    // aquarium, filtre) : la page gère elle-même sa position. Retour arrière :
    // position mémorisée.
    scrollBehavior: (to, from, savedPosition) => {
      if (savedPosition) return savedPosition;
      if (to.path === from.path) return false;
      return { left: 0, top: 0 };
    },
    routes,

    history: createHistory(import.meta.env.QUASAR_VUE_ROUTER_BASE),
  });

  return Router;
});
