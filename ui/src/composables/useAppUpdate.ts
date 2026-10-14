import { ref } from 'vue';

// Version de l'appli en cours d'exécution (injectée à la compilation) :
// numéro SemVer et commit compilé (« dev » en local)
export const APP_VERSION: string = process.env.APP_VERSION ?? '0.0.0';
export const APP_BUILD: string = process.env.APP_BUILD ?? 'dev';
export const APP_BUILT_AT: string = process.env.APP_BUILT_AT ?? '';
// Affichage : « 0.6.1 » en prod, « 0.6.2-dev.12 » en recette
export const APP_VERSION_LABEL = APP_VERSION;

const CHECK_EVERY_MS = 10 * 60 * 1000;
const updateAvailable = ref(false);
const latestVersion = ref<string | null>(null);
let started = false;

async function check(): Promise<void> {
  if (APP_BUILD === 'dev' || !navigator.onLine) return;
  try {
    const response = await fetch('/version.json', { cache: 'no-store' });
    if (!response.ok) return;
    // Nouvelle compilation (même numéro de version possible) : commit différent
    const { version, build } = (await response.json()) as { version?: string; build?: string };
    if (build && build !== APP_BUILD) {
      latestVersion.value = version ?? null;
      updateAvailable.value = true;
    }
  } catch {
    // hors ligne ou serveur indisponible : on réessaiera
  }
}

// Vérifie au démarrage, toutes les 10 minutes et au retour sur l'appli
export function startUpdateChecks(): void {
  if (started || typeof window === 'undefined') return;
  started = true;
  void check();
  setInterval(() => void check(), CHECK_EVERY_MS);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void check();
  });
  window.addEventListener('online', () => void check());
}

// Recharge sur la nouvelle version (le service worker va chercher la page en réseau d'abord)
export async function applyUpdate(): Promise<void> {
  try {
    const registration = await navigator.serviceWorker?.getRegistration();
    await registration?.update();
  } catch {
    // pas de service worker : simple rechargement
  }
  window.location.reload();
}

export function useAppUpdate() {
  return { updateAvailable, latestVersion, version: APP_VERSION_LABEL, builtAt: APP_BUILT_AT, applyUpdate, check };
}
