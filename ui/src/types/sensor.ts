export interface SensorsList {
  total: number;
  sensors: Sensor[];
}

export interface Sensor {
  id: number;
  aquarium_id: number;
  controller_id: number;
  pin_id: number;
  pin_number: number;
  module_id?: number | null;
  module_number?: number | null;
  // Dernière mesure reçue (vide : jamais mesurée)
  last_reading_at?: string | null;
  name: string;
  is_inverted: boolean;
  type: string;
  unit: string;
  at_created: string;
  actions: string;
  last_value?: number | string | boolean | null;
  address?: string | null | undefined;
  interval?: number | null | undefined;
}

export interface SensorCreation {
  aquarium_id: number;
  controller_id: number;
  pin_id: number;
  name: string;
  type: string;
  // « temperature » ou « niveau » (stocké « °C » / « level » par l'API)
  unit: string;
  is_inverted?: boolean;
  address?: string | null | undefined;
  interval?: number | null | undefined;
}

export interface SensorUpdate {
  id: number | undefined;
  aquarium_id: number | undefined;
  controller_id: number | undefined;
  pin_id: number | undefined;
  name: string | undefined;
  type: string | undefined;
}

export type SensorHistoryPeriod = '24h' | '7d' | '30d' | '90d';

export interface SensorHistoryPoint {
  t: string;
  avg: number;
  min: number;
  max: number;
  last: number;
}

export interface SensorHistory {
  sensor_id: number;
  period: SensorHistoryPeriod;
  bucket_seconds: number;
  unit: string | null;
  start: string;
  end: string;
  points: SensorHistoryPoint[];
  stats: { count: number; min: number | null; max: number | null; avg: number | null };
}
