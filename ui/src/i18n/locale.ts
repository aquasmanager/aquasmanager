import { Lang } from 'quasar';
import quasarEn from 'quasar/lang/en-GB';
import quasarFr from 'quasar/lang/fr';
import { i18n, isAppLocale, rememberLocale, type AppLocale } from 'src/i18n/instance';

/**
 * Applique une langue à toute l'interface : textes (vue-i18n), libellés
 * intégrés de Quasar (tableaux, calendriers), attribut lang de la page, et
 * choix gardé sur l'appareil. Les dates suivent via intlLocale().
 */
export function applyLocale(locale: AppLocale) {
  i18n.global.locale.value = locale;
  // Types des paquets de langue Quasar incompatibles avec exactOptionalPropertyTypes
  Lang.set((locale === 'en' ? quasarEn : quasarFr) as Parameters<typeof Lang.set>[0]);
  document.documentElement.lang = locale;
  rememberLocale(locale);
}

export function applyAccountLocale(value: unknown) {
  if (isAppLocale(value) && value !== i18n.global.locale.value) applyLocale(value);
}
