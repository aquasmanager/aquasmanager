export interface OverviewCounts {
  aquariums: number;
  equipments: number;
  fishes: number;
  corals: number;
  plants: number;
  invertebrates: number;
  open_alerts: number;
}

export interface OverviewController {
  id: number;
  name: string;
  technical_name: string;
  status: string;
}

export interface OverviewAquarium {
  id: number;
  name: string;
  water_type: string;
  volume: number;
  open_alerts: number;
  out_of_target_parameters: string[];
  overdue_tasks: number;
  low_stock_items: number;
  last_reading_at: string | null;
  livestock: number;
  temperature: { sensor_id: number; name: string; value: number | null } | null;
}

export interface OverviewTask {
  id: number;
  title: string;
  aquarium_id: number;
  aquarium_name: string | null;
  shared?: boolean;
  next_due_at: string;
  overdue: boolean;
}

export interface OverviewLowStock {
  id: number;
  name: string;
  aquarium_id: number;
  aquarium_name: string | null;
  shared?: boolean;
  quantity: number;
  unit: string;
  low_stock_threshold: number | null;
}

import type { MetricAlert } from './metricAlert';

// Alertes ouvertes de « À faire » : mesure hors cible / capteur muet, ou défaut d'équipement
export type OverviewAlert =
  | (MetricAlert & { kind: 'metric'; aquarium_name: string | null })
  | {
      kind: 'fault';
      id: number;
      code: string;
      message: string;
      equipment_name: string | null;
      aquarium_id: number | null;
      aquarium_name: string | null;
      created_at: string;
    };

export interface Overview {
  counts: OverviewCounts;
  controllers: OverviewController[];
  aquariums: OverviewAquarium[];
  todo: { alerts?: OverviewAlert[]; tasks: OverviewTask[]; low_stock: OverviewLowStock[] };
}
