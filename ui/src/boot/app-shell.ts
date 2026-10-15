import { defineBoot } from '#q-app';
import { initTheme } from 'src/composables/useTheme';
import { listenInstallPrompt } from 'src/composables/useInstallPrompt';
import { startUpdateChecks } from 'src/composables/useAppUpdate';

const CHUNK_RELOAD_KEY = 'aquas.chunkReload';

// Nouvelle version déployée pendant qu'un onglet était ouvert : les anciens
// fichiers de pages n'existent plus. On recharge une fois vers la page voulue.
function reloadOnStaleChunk(error: unknown, target?: string) {
  const message = error instanceof Error ? error.message : String(error);
  if (!/dynamically imported module|Importing a module script failed|error loading dynamically/i.test(message)) return false;
  try {
    if (sessionStorage.getItem(CHUNK_RELOAD_KEY)) return false;
    sessionStorage.setItem(CHUNK_RELOAD_KEY, '1');
  } catch {
    // stockage indisponible : on recharge quand même
  }
  if (target) window.location.assign(target);
  else window.location.reload();
  return true;
}

// Thème (clair / sombre / automatique) et application installable (PWA)
export default defineBoot(({ router }) => {
  router.onError((error, to) => reloadOnStaleChunk(error, to.fullPath));
  window.addEventListener('vite:preloadError', (event) => {
    if (reloadOnStaleChunk((event as Event & { payload?: unknown }).payload)) event.preventDefault();
  });
  router.afterEach(() => {
    try {
      sessionStorage.removeItem(CHUNK_RELOAD_KEY);
    } catch {
      // stockage indisponible
    }
  });
  initTheme();
  listenInstallPrompt();
  if (import.meta.env.PROD) startUpdateChecks();
  if (import.meta.env.PROD && 'serviceWorker' in navigator) {
    const register = () =>
      navigator.serviceWorker.register('/sw.js').catch((err) => console.warn('Service worker non enregistré', err));
    // L'appli démarre souvent après l'événement « load » : enregistrement immédiat dans ce cas
    if (document.readyState === 'complete') void register();
    else window.addEventListener('load', () => void register());
  }
});
