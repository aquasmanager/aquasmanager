import { createI18n } from 'vue-i18n';
import messages, { type MessageSchema } from 'src/i18n';

export type AppLocale = 'fr' | 'en';

export const LOCALES: { value: AppLocale; label: string; flag: string }[] = [
  { value: 'fr', label: 'Français', flag: '🇫🇷' },
  { value: 'en', label: 'English', flag: '🇬🇧' },
];

const STORAGE_KEY = 'aquas-locale';

export function isAppLocale(value: unknown): value is AppLocale {
  return value === 'fr' || value === 'en';
}

/** Langue gardée sur l'appareil, sinon celle du navigateur (anglais), sinon français. */
export function initialLocale(): AppLocale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (isAppLocale(saved)) return saved;
  } catch {
    /* stockage indisponible (navigation privée) */
  }
  return navigator.language?.toLowerCase().startsWith('en') ? 'en' : 'fr';
}

export function rememberLocale(locale: AppLocale) {
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    /* idem */
  }
}

// Le français est la langue de référence : un texte pas encore traduit reste
// en français (les écrans sont traduits au fur et à mesure)
export const i18n = createI18n<[MessageSchema], AppLocale, false>({
  legacy: false,
  locale: initialLocale(),
  fallbackLocale: 'fr',
  messages,
  missingWarn: false,
  fallbackWarn: false,
});

export function currentLocale(): AppLocale {
  return i18n.global.locale.value;
}

/** Locale Intl des dates et nombres (jour/mois/année et 24 h dans les deux langues). */
export function intlLocale(locale: AppLocale = currentLocale()): string {
  return locale === 'en' ? 'en-GB' : 'fr-FR';
}

/** Traduction hors composant (stores, utilitaires). */
export const t = i18n.global.t;
