import { defineBoot } from '#q-app';
import { useAuthStore } from 'src/stores/authStore';
import axios from 'axios';
import { Role, type RouteMeta } from 'src/types/auth';
import { API_URL } from 'src/utils/runtimeConfig';
import { currentLocale } from 'src/i18n/instance';
import { useLicenseStore } from 'src/stores/licenseStore';

export default defineBoot(async ({ router }) => {
  const auth = useAuthStore();

  auth.setRouter(router);

  // Charger l'état du localStorage
  auth.loadFromStorage();

  // Définir l'ur axios par défaut
  axios.defaults.baseURL = API_URL;

  axios.defaults.withCredentials = true;

  // Injecter le token JWT dans axios pour tous les appels
  axios.interceptors.request.use((config) => {
    if (auth.accessToken) {
      config.headers.Authorization = `Bearer ${auth.accessToken}`;
    }
    // Langue de l'interface : messages de l'API dans la même langue
    config.headers['Accept-Language'] = currentLocale();
    return config;
  });

  // Autorenouvellement du access token
  axios.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config;

      if (originalRequest._skipAuthInterceptor) {
        return Promise.reject(
          error instanceof Error ? error : new Error(error.message || 'Request failed'),
        );
      }

      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;

        try {
          const data = await auth.refreshToken({ _skipAuthInterceptor: true });

          originalRequest.headers['Authorization'] = `Bearer ${data.access_token}`;

          return axios(originalRequest);
        } catch (refreshError) {
          // Redirige vers la connexion, sauf sur les pages publiques
          await auth.logout({ _skipAuthInterceptor: true });
          return Promise.reject(
            refreshError instanceof Error
              ? refreshError
              : new Error(error.message || 'Request failed'),
          );
        }
      }
      return Promise.reject(
        error instanceof Error ? error : new Error(error.message || 'Request failed'),
      );
    },
  );

  // must_change_password n'est pas encodé dans le JWT : on le récupère
  // depuis l'API (une fois les intercepteurs prêts) pour survivre à un
  // rechargement de page.
  if (auth.accessToken) {
    await auth.fetchMe();
  }

  // Protéger les routes
  const license = useLicenseStore();
  router.beforeEach(async (to, _from, next) => {
    const ROLE_HIERARCHY: Record<string, number> = { consult: 1, seller: 1, caretaker: 1, user: 2, manager: 3, admin: 4 };
    const minRole = (to.meta as RouteMeta).minRole;

    if (to.meta.requiresAuth && !auth.accessToken) {
      // Étiquette de bouture scannée par un visiteur : la vitrine publique
      if (to.path === '/frags' && typeof to.query.ref === 'string') {
        return next({ path: '/vitrine', query: { ref: to.query.ref } });
      }
      return next('/login');
    }

    if (auth.accessToken && auth.mustChangePassword && to.path !== '/change-password') {
      return next('/change-password');
    }

    // Fonctionnalité soumise à licence (bourse) : accueil si elle n'est pas ouverte
    const feature = (to.meta as RouteMeta).feature;
    if (auth.accessToken && feature) {
      await license.ensure();
    }
    if (feature && !license.has(feature)) {
      return next('/home');
    }

    // Compte « bourse » : arrive directement sur les boutures
    if (auth.role === Role.seller && to.path === '/home') {
      return next('/frags');
    }

    if (!minRole) {
      return next();
    }

    if (!auth.role || ROLE_HIERARCHY[auth.role]! < ROLE_HIERARCHY[minRole]!) {
      return next('/errorRights');
    }

    return next();
  });
});
