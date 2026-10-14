import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
import type { TokenUser } from 'src/types/auth';
import {
  type RegisterForm,
  Role,
  type User,
  type Login,
  type Me,
  type PasswordChange,
} from 'src/types/auth';
import { jwtDecode } from 'jwt-decode';
import type { AxiosError } from 'axios';
import axios from 'axios';
import type { Router } from 'vue-router';
import { Notify } from 'quasar';
import { currentLocale, t, type AppLocale } from 'src/i18n/instance';
import { applyAccountLocale, applyLocale } from 'src/i18n/locale';

let router: Router;
// Langue choisie sur la page de connexion, à reporter sur le compte
let localeChosenBeforeLogin = false;

// Clés localStorage des autres stores persistés (pinia-plugin-persistedstate).
// À purger au logout pour éviter qu'un compte suivant sur un poste partagé
// voie encore les données métier du compte précédent. Mettre à jour cette
// liste si un nouveau store persisté est ajouté.
const PERSISTED_STORE_KEYS = [
  'chat-store',
  'controller-pins-store',
  'equipment-groups-store',
  'light_schedules-store',
  'rules-store',
  'equipments-store',
  'controllers-store',
  'aquariums-store',
  'fishes-store',
  'corals-store',
  'invertebrates-store',
  'other_alives-store', // ancien nom, nettoyé à la déconnexion
  'light_channels-store',
  'lights-store',
  'plants-store',
  'sensors-store',
];

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | undefined>(undefined);
  const user = ref<User | undefined>(undefined);
  const mustChangePassword = ref<boolean>(false);

  const isAuthenticated = computed(() => !!accessToken.value);
  const role = computed(() => user.value?.role ?? undefined);
  const username = computed(() => user.value?.username ?? undefined);
  const isAdmin = computed(() => user.value?.role === Role.admin);

  const errorMessage = ref<string | undefined>(undefined);

  function setRouter(r: Router) {
    router = r;
  }

  function setAccessToken(newToken: string, remember: boolean) {
    accessToken.value = newToken;
    const decoded = jwtDecode<TokenUser>(newToken);
    user.value = { id: decoded.user_id, username: decoded.username, role: decoded.role };
    if (remember) {
      localStorage.setItem('accessToken', newToken);
      sessionStorage.removeItem('accessToken');
    } else {
      sessionStorage.setItem('accessToken', newToken);
      localStorage.removeItem('accessToken');
    }
  }

  async function register(params: RegisterForm) {
    type RegisterWithoutConfirmPassword = Omit<RegisterForm, 'confirmPassword' | 'mustChangePassword'> & {
      must_change_password: boolean;
    };
    const newData: RegisterWithoutConfirmPassword = {
      username: params.username,
      password: params.password,
      role: params.role,
      must_change_password: params.mustChangePassword,
    };

    const { data } = await axios.post<User>(`/register`, newData);

    Notify.create({
      message: t('auth.userCreated', { name: data.username }),
      color: 'positive',
      position: 'top',
      timeout: 3000,
    });

    return data;
  }

  async function login(username: string, password: string, remember: boolean) {
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);
    try {
      const res = await axios.post<Login>(`/login`, params);

      setAccessToken(res.data.access_token, remember);
      mustChangePassword.value = res.data.must_change_password;
      // Langue choisie sur la page de connexion : gardée sur le compte ; sinon
      // celle du compte (choisie sur un autre appareil) est suivie ici aussi
      if (localeChosenBeforeLogin) {
        localeChosenBeforeLogin = false;
        void axios.put('/me/language', { language: currentLocale() }).catch(() => undefined);
      } else {
        applyAccountLocale(res.data.language);
      }

      if (mustChangePassword.value) {
        await router.push('/change-password');
      } else {
        await router.push('/home');
      }
    } catch (err) {
      const error = err as AxiosError<{ detail: string }>;
      if (error.response) {
        errorMessage.value = error.response.data.detail || t('auth.unknownError');
      } else {
        errorMessage.value = t('auth.serverUnreachable');
      }
      Notify.create({
        message: errorMessage.value,
        color: 'negative',
        position: 'top',
        timeout: 3000,
        icon: 'warning',
      });
    }
  }

  async function logout(options = {}) {
    accessToken.value = undefined;
    user.value = undefined;
    mustChangePassword.value = false;
    localStorage.removeItem('accessToken');
    sessionStorage.removeItem('accessToken');
    for (const key of PERSISTED_STORE_KEYS) {
      localStorage.removeItem(key);
    }
    // Données gardées pour le mode hors connexion : effacées avec la session
    navigator.serviceWorker?.controller?.postMessage('clear-data');

    try {
      await axios.post('/logout', {}, { ...options });
    } catch (err) {
      // Session déjà expirée ou serveur injoignable : la déconnexion locale suffit
      console.warn('Déconnexion côté serveur impossible :', err);
    }
    // Pages publiques (signature, vitrine) : on y reste
    if (router.currentRoute.value.meta.requiresAuth) await router.push('/login');
  }

  function loadFromStorage() {
    const savedToken = localStorage.getItem('accessToken') || sessionStorage.getItem('accessToken');
    if (savedToken) {
      const remember = !!localStorage.getItem('accessToken');
      setAccessToken(savedToken, remember);
    }
  }

  async function refreshToken(options = {}) {
    const { data } = await axios.post('/refresh', {}, { ...options });
    accessToken.value = data.access_token;
    return data;
  }

  // Rafraîchit le statut must_change_password depuis le serveur (la valeur
  // n'est pas encodée dans le JWT, donc perdue au simple rechargement de page).
  async function fetchMe() {
    if (!accessToken.value) return;
    try {
      const { data } = await axios.get<Me>('/me');
      mustChangePassword.value = data.must_change_password;
      applyAccountLocale(data.language);
    } catch (err) {
      console.warn('Profil indisponible :', err);
    }
  }

  async function changePassword(payload: PasswordChange) {
    await axios.post('/change-password', payload);
    mustChangePassword.value = false;
  }

  /** Langue de l'interface : appliquée tout de suite, gardée sur le compte (dès la connexion). */
  async function setLanguage(locale: AppLocale) {
    applyLocale(locale);
    if (accessToken.value) await axios.put('/me/language', { language: locale }).catch(() => undefined);
    else localeChosenBeforeLogin = true;
  }

  return {
    accessToken,
    user,
    mustChangePassword,
    isAuthenticated,
    role,
    username,
    isAdmin,
    errorMessage,
    register,
    login,
    setAccessToken,
    logout,
    loadFromStorage,
    setRouter,
    refreshToken,
    fetchMe,
    changePassword,
    setLanguage,
  };
});
