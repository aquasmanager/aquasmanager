// Partage des paramètres d'eau : lien public en lecture seule, image et texte

export type ShareHistoryDays = 0 | 7 | 30 | 90;

export interface ParameterShareLink {
  id: number;
  token: string;
  aquarium_id: number;
  label?: string | null;
  history_days: ShareHistoryDays;
  pinned_only: boolean;
  expires_at?: string | null;
  view_count: number;
  last_viewed_at?: string | null;
  created_at: string;
  state: 'active' | 'expired';
}

export interface SharedParameter {
  name: string;
  full_name?: string | null;
  unit?: string | null;
  target_min?: number | null;
  target_max?: number | null;
  last_value?: number | null;
  last_reading_at?: string | null;
  in_target?: boolean | null;
  history: { timestamp: string; value: number }[];
}

// Même forme pour la page publique (GET /public/parameters/<jeton>) et l'image construite dans l'appli
export interface SharedParameters {
  aquarium: { name: string; volume: number; water_type: string; biotope: string };
  history_days: number;
  expires_at?: string | null;
  generated_at: string;
  parameters: SharedParameter[];
}

export function parameterShareUrl(token: string): string {
  return `${window.location.origin}/partage/parametres/${token}`;
}
