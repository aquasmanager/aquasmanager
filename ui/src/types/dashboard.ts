export enum MetricType {
  TEMPERATURE = 'temperature',
  WATER_PARAM = 'water_param',
  RO_RESERVE = 'ro_reserve',
  BINARY_LEVEL = 'binary_level',
  OSMOLATOR_EVENTS = 'osmolator_events',
  // Raccourci de pilotage d'un équipement (marche / arrêt, auto / manuel)
  EQUIPMENT = 'equipment',
  // Évolution combinée des paramètres d'eau (créée d'office, une par aquarium)
  WATER_TREND = 'water_trend',
}

// Période de la courbe d'une carte
export type CardPeriod = '24h' | '7d' | '30d' | '90d';
export type LevelState = 'HIGH' | 'LOW';

export interface EquipmentActivation {
  id: number;
  equipment_id: number;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
}

export interface DashboardCardConfig {
  id: number;
  aquarium_id: number;
  title: string;
  type: MetricType;
  icon: string;
  col_span: number;
  position: number;

  // Capteurs & équipement associés selon le type de carte
  sensor_id?: number | null;
  sensor_high_id?: number | null;
  sensor_low_id?: number | null;
  equipment_id?: number | null;
  // Carte équipement à plusieurs lignes (sinon equipment_id seul)
  equipment_ids?: number[] | null;
  // Alternative à sensor_id pour une carte water_param saisie manuellement
  // (pas de capteur physique) : l'un ou l'autre est renseigné, jamais les deux.
  water_parameter_id?: number | null;
  // Période de la courbe (vide = défaut selon la source) ; état normal d'un niveau
  period?: CardPeriod | null;
  normal_state?: LevelState | null;

  // Métriques & cibles (température / paramètres d'eau)
  unit?: string | null;
  target_min?: number | null;
  target_max?: number | null;

  // Rempli côté client après récupération (pas stocké tel quel en base)
  history?: number[];
  activations?: EquipmentActivation[];
}

export interface DashboardCardCreate {
  aquarium_id: number;
  title: string;
  type: MetricType;
  icon: string;
  unit?: string | null | undefined;
  col_span: number;
  sensor_id?: number | null | undefined;
  sensor_high_id?: number | null | undefined;
  sensor_low_id?: number | null | undefined;
  equipment_id?: number | null | undefined;
  equipment_ids?: number[] | null | undefined;
  water_parameter_id?: number | null | undefined;
  period?: CardPeriod | null | undefined;
  normal_state?: LevelState | null | undefined;
  target_min?: number | null | undefined;
  target_max?: number | null | undefined;
}

export type DashboardCardUpdate = Partial<Omit<DashboardCardCreate, 'aquarium_id'>>;
