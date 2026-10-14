export type ChannelMode = 'AUTO' | 'MANUAL' | 'OFF';

export interface SchedulePoint {
  minute: number;
  intensity: number;
}

export interface LightChannel {
  id: number;
  light_id: number;
  name: string;
  pin_id: number;
  pin_number?: string | null;
  color: string;
  spectrum: string;
  mode: ChannelMode;
  max_intensity: number;
  // Seuil sous lequel le canal reste éteint (zone instable du driver)
  min_intensity: number;
  current_intensity: number;
  inverted: boolean;
  // Clair de lune : intensité plancher la nuit (0 = éteint la nuit)
  moonlight_intensity: number;
  schedule: SchedulePoint[];
}

export type LightChannelInput = Pick<LightChannel, 'name' | 'pin_id' | 'color' | 'spectrum' | 'max_intensity' | 'min_intensity' | 'inverted'>;

export interface MoonlightChannel {
  channel_id: number;
  intensity: number;
}

export interface Light {
  id: number;
  name: string;
  aquarium_id: number;
  controller_id: number;
  pwm_frequency: number;
  // Canaux allumés la nuit, chacun à son intensité (ex. driver + bleu)
  moonlight: MoonlightChannel[];
  acclimation_start: string | null;
  acclimation_days: number | null;
  acclimation_start_percent: number;
  acclimation_percent: number | null;
  channels: LightChannel[];
}

export type LightInput = Omit<Light, 'id' | 'channels' | 'acclimation_percent'>;

export interface Spectrum {
  key: string;
  label: string;
  color: string;
}

export interface LightProfile {
  key: string;
  label: string;
  description: string;
  /** Début et fin du programme par défaut (minutes depuis minuit) */
  start: number;
  end: number;
}
