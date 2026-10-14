import { z } from 'zod';
import { t } from 'src/i18n/instance';

// Mêmes limites que l'API (schémas Pydantic) pour afficher l'erreur sous le
// champ plutôt qu'un refus du serveur à l'enregistrement. Messages dans la
// langue courante : construire les schémas dans un computed.
export const nameField = () =>
  z.string().trim().min(4, t('validation.minChars', { n: 4 })).max(30, t('validation.maxChars', { n: 30 }));

export const optionalText = (max = 30) => z.string().trim().max(max, t('validation.maxChars', { n: max }));

export const isoDateField = () => z.string().regex(/^\d{4}-\d{2}-\d{2}$/, t('validation.dateRequired'));

// label : nom du champ déjà traduit
export const positiveInt = (label: string) =>
  z
    .number({ invalid_type_error: t('validation.fieldRequired', { label }), required_error: t('validation.fieldRequired', { label }) })
    .int(t('validation.integer'))
    .positive(t('validation.positive'));
