import { t } from 'src/i18n/instance';

export type CameraBrand = 'reolink' | 'tapo' | 'rtsp';
export type CameraQuality = 'main' | 'sub';

export interface Camera {
  id: number;
  aquarium_id: number;
  name: string;
  brand: CameraBrand;
  host: string;
  port: number;
  username: string;
  main_path: string;
  sub_path: string;
  sort_order: number;
  has_password: boolean;
  created_at: string;
}

export interface CameraForm {
  name: string;
  brand: CameraBrand;
  host: string;
  port: number;
  username: string;
  password: string;
  clear_password: boolean;
  main_path: string;
  sub_path: string;
  sort_order: number;
}

export interface CameraStatus {
  enabled: boolean;
  presets: Record<string, { main: string; sub: string }>;
}

export const CAMERA_BRANDS: CameraBrand[] = ['reolink', 'tapo', 'rtsp'];

export function cameraBrandLabel(brand: CameraBrand): string {
  return t(`cameras.brands.${brand}`);
}

/** Réglage à faire sur la caméra pour activer le RTSP, selon la marque. */
export function cameraBrandHint(brand: CameraBrand): string {
  return t(`cameras.hints.${brand}`);
}
