// Formats d'affichage communs (langue de l'interface, heure locale du navigateur).
import { intlLocale, t } from 'src/i18n/instance';

/** 25/09/2026 — « Jamais » si absent. */
export function formatDate(value?: string | Date | null, empty?: string): string {
  if (!value) return empty ?? t('common.never');
  return new Date(value).toLocaleDateString(intlLocale(), { day: '2-digit', month: '2-digit', year: 'numeric' });
}

/** 25/09/2026 14:32 */
export function formatDateTime(value?: string | Date | null, empty = '—'): string {
  if (!value) return empty;
  return new Date(value).toLocaleString(intlLocale(), {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Date locale au format AAAA-MM-JJ (valeur des champs date). */
export function isoDate(value: Date = new Date()): string {
  const yyyy = value.getFullYear();
  const mm = String(value.getMonth() + 1).padStart(2, '0');
  const dd = String(value.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

/** Nombre dans la langue de l'interface, 3 décimales au plus : « 12,2 » (jamais 12.199999999999). */
export function formatNumber(value?: number | null, empty = '--'): string {
  if (value == null || Number.isNaN(value)) return empty;
  return value.toLocaleString(intlLocale(), { maximumFractionDigits: 3 });
}

/** « 12,50 € » ; « — » si pas de prix. */
export function formatPrice(value?: number | null): string {
  if (value == null) return '—';
  return value.toLocaleString(intlLocale(), { style: 'currency', currency: 'EUR' });
}

// « Chromis × 5 » quand il y a plusieurs individus
export function withQuantity(name: string, quantity?: number | null): string {
  return quantity && quantity > 1 ? `${name} × ${quantity}` : name;
}

/** Échelle de lumière des coraux : 1 à 15, par paliers de 50 PAR (1 = 50 PAR … 15 = 750 PAR). */
export const CORAL_LIGHT_MAX = 15;
export const toPar = (level: number) => level * 50;
