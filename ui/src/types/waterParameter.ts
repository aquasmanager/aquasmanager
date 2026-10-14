export interface WaterParameterReading {
  id: number;
  water_parameter_id: number;
  value: number;
  timestamp: string;
  note?: string | null;
  icp_batch_id?: number | null;
}

export interface WaterParameter {
  id: number;
  aquarium_id: number;
  name: string;
  unit?: string | null;
  target_min?: number | null;
  target_max?: number | null;
  // Favori : en tête de liste, dans la saisie groupée et sur le graphique du tableau de bord
  pinned: boolean;
  last_value?: number | null;
  last_reading_at?: string | null;
  full_name?: string | null;
  in_target?: boolean | null;
}

export interface WaterParameterCreate {
  aquarium_id: number;
  name: string;
  unit?: string | null;
  target_min?: number | null;
  target_max?: number | null;
  pinned?: boolean;
}

export type WaterParameterUpdate = Partial<Omit<WaterParameterCreate, 'aquarium_id'>>;

export interface WaterParameterReadingCreate {
  value: number;
  timestamp?: string | null;
  note?: string | null;
  icp_batch_id?: number | null;
}

export interface WaterParameterReadingBatchCreate {
  aquarium_id: number;
  timestamp?: string | null;
  note?: string | null;
  values: { water_parameter_id: number; value: number }[];
}

export type WaterParameterReadingUpdate = Partial<Omit<WaterParameterReadingCreate, 'icp_batch_id'>>;

export type IcpLab = 'ati' | 'fauna_marin' | 'other';

export interface IcpImportRow {
  name: string;
  label: string;
  value: number;
  unit?: string | null;
  target?: number | null;
  status?: string | null;
}

export interface IcpImportBatch {
  id: number;
  aquarium_id: number;
  lab: string;
  sample_date: string;
  created_at: string;
  pdf_filename?: string | null;
}

export interface IcpImportBatchCreate {
  aquarium_id: number;
  lab: string;
  sample_date: string;
}

export interface IcpBatchReading {
  water_parameter_id: number;
  name: string;
  unit?: string | null;
  value: number;
}

// Sans vert/jaune/rouge : réservés à la bande cible et aux états hors cible.
export const PARAMETER_PALETTE = [
  '#0ea5e9', '#14b8a6', '#a855f7', '#f59e0b', '#6366f1',
  '#f43f5e', '#06b6d4', '#f97316', '#8b5cf6', '#64748b',
];

// Hors palette : teinte par angle d'or, limitée aux plages orange (15-35°)
// et cyan->rose (150-345°), luminosité alternée à chaque tour de palette.
const ALLOWED_HUE_RANGES: [number, number][] = [[15, 35], [150, 345]];
const ALLOWED_HUE_SPAN = ALLOWED_HUE_RANGES.reduce((sum, [a, b]) => sum + b - a, 0);
const LIGHTNESS_STEPS = [45, 33, 57];

function generatedColor(n: number): string {
  let offset = (n * 137.508) % ALLOWED_HUE_SPAN;
  let hue = 0;
  for (const [start, end] of ALLOWED_HUE_RANGES) {
    if (offset < end - start) {
      hue = start + offset;
      break;
    }
    offset -= end - start;
  }
  const lightness = LIGHTNESS_STEPS[Math.floor(n / PARAMETER_PALETTE.length) % LIGHTNESS_STEPS.length]!;
  return hslToHex(hue, 70, lightness);
}

function hslToHex(h: number, s: number, l: number): string {
  const sat = s / 100;
  const light = l / 100;
  const a = sat * Math.min(light, 1 - light);
  const channel = (k: number) => {
    const c = light - a * Math.max(-1, Math.min((k + h / 30) % 12 - 3, 9 - ((k + h / 30) % 12), 1));
    return Math.round(c * 255).toString(16).padStart(2, '0');
  };
  return `#${channel(0)}${channel(8)}${channel(4)}`;
}

// Indexée sur la position du paramètre dans la liste de l'aquarium : stable
// d'une page à l'autre ; les 10 premiers ont la palette choisie à la main.
export function parameterColor(paramId: number | null | undefined, parameters: { id: number }[]): string {
  const idx = Math.max(parameters.findIndex((p) => p.id === paramId), 0);
  return PARAMETER_PALETTE[idx] ?? generatedColor(idx);
}

// Table servie par l'API (GET /water-parameters/target-defaults)
export interface ParameterTargetDefault {
  name: string;
  full_name?: string | null;
  unit: string;
  target_min: number;
  target_max: number;
}

function normalizeUnit(unit: string | null | undefined): string {
  return (unit ?? '').trim().toLowerCase().replace('ug/', 'µg/').replace(/\s+/g, '');
}

// Même règle que services/water_parameter_defaults.py : l'unité, si fournie,
// doit correspondre (une cible en mg/l appliquée à des µg/l serait fausse).
export function findTargetDefault(
  defaults: ParameterTargetDefault[],
  name: string,
  unit?: string | null,
): ParameterTargetDefault | null {
  const preset = defaults.find((d) => d.name === name.trim().toUpperCase());
  if (!preset) return null;
  if (unit && normalizeUnit(unit) !== normalizeUnit(preset.unit)) return null;
  return preset;
}
