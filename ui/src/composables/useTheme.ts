import { ref } from 'vue';
import { Dark } from 'quasar';

export type ThemePreference = 'auto' | 'light' | 'dark';

const STORAGE_KEY = 'aquasmanager.theme';
const preference = ref<ThemePreference>('auto');

function stored(): ThemePreference {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === 'light' || value === 'dark' ? value : 'auto';
  } catch {
    return 'auto';
  }
}

function apply(value: ThemePreference) {
  Dark.set(value === 'auto' ? 'auto' : value === 'dark');
  const meta = document.querySelector('meta[name="theme-color"]');
  meta?.setAttribute('content', Dark.isActive ? '#101418' : '#1976d2');
}

/** Thème clair / sombre / automatique (réglage du système), mémorisé dans ce navigateur. */
export function initTheme() {
  preference.value = stored();
  apply(preference.value);
}

export function useTheme() {
  function setPreference(value: ThemePreference) {
    preference.value = value;
    apply(value);
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Navigation privée : le choix vaut pour cette session seulement
    }
  }

  return { preference, setPreference };
}
