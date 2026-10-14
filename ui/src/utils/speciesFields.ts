/**
 * Libellés et valeurs lisibles des champs du catalogue d'espèces (propositions
 * de correction au catalogue commun).
 */
import type { SpeciesKind } from 'src/utils/hub';
import { toPar } from 'src/utils/format';

type Translate = (key: string) => string;
type Value = string | number | boolean | null | undefined;

const LABEL_KEYS: Record<string, string> = {
  common_name: 'livestock.catalog.commonName',
  scientific_name: 'livestock.scientificName',
  family: 'livestock.familyLabel',
  origin: 'livestock.originLabel',
  type: 'livestock.catalog.columns.type',
  water_type: 'livestock.catalog.columns.water',
  category: 'livestock.catalog.columns.category',
  max_height: 'livestock.catalog.columns.sizeMax',
  min_volume: 'livestock.catalog.columns.volumeMin',
  reef_safe: 'livestock.catalog.columns.reef',
  growing: 'livestock.catalog.columns.growing',
  location: 'livestock.catalog.columns.location',
  aggressiveness_level: 'livestock.aggressiveness',
  resistance_level: 'livestock.resistance',
  location_level: 'livestock.heightInTank',
  notes: 'livestock.catalog.notes',
  link: 'livestock.catalog.link',
};

const RANGE_KEYS: Record<string, string> = {
  light: 'livestock.light',
  brewing: 'livestock.brewing',
  temperature: 'livestock.temperature',
};

export function speciesFieldLabel(t: Translate, field: string): string {
  const range = /^(light|brewing|temperature)_(min|max)$/.exec(field);
  if (range) return `${t(RANGE_KEYS[range[1]!]!)} ${range[2]}`;
  return LABEL_KEYS[field] ? t(LABEL_KEYS[field]) : field;
}

export function speciesFieldValue(t: Translate, kind: SpeciesKind, field: string, value: Value): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? t('actions.yes') : t('actions.no');
  if (kind === 'corals' && (field === 'light_min' || field === 'light_max') && typeof value === 'number') {
    return `${value} (${toPar(value)} PAR)`;
  }
  return String(value);
}
