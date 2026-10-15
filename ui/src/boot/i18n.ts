import { defineBoot } from '#q-app';
import { i18n, currentLocale } from 'src/i18n/instance';
import { applyLocale } from 'src/i18n/locale';
import type { MessageSchema } from 'src/i18n';

// Clés typées : t('nav.home') est vérifié à la compilation
/* eslint-disable @typescript-eslint/no-empty-object-type */
declare module 'vue-i18n' {
  export interface DefineLocaleMessage extends MessageSchema {}
}
/* eslint-enable @typescript-eslint/no-empty-object-type */

export default defineBoot(({ app }) => {
  app.use(i18n);
  // Langue de départ appliquée partout (Quasar, attribut lang de la page)
  applyLocale(currentLocale());
});
