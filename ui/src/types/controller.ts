export enum ControllerType {
  RPI = 'RPI',
  ESP32 = 'ESP32',
  ESP8266 = 'ESP8266',
  ARDUINO = 'ARDUINO',
}

export enum ControllerStatus {
  ONLINE = 'ONLINE',
  OFFLINE = 'OFFLINE',
  ERROR = 'ERROR',
  FLASHING = 'FLASHING',
  FLASH_FAILED = 'FLASH_FAILED',
  INITIALIZING = 'INITIALIZING',
}

export interface ControllersList {
  total: number;
  controllers: Controller[];
}

export interface Controller {
  id: number;
  name: string;
  technical_name: string;
  type: ControllerType;
  zone: string;
  status?: ControllerStatus;
  ip?: string | undefined;
  created_at: string;
  actions: string;
  rtc_model?: RtcModel | null;
  // Fréquence du bus I2C (kHz) : plus basse pour un câble long
  i2c_frequency_khz?: number;
  is_dirty?: boolean;
  last_sync?: string;
}

export interface ControllerCreation {
  name: string;
  type: ControllerType;
  zone: string;
  ip?: string | undefined;
  created_at?: string | undefined;
  status: ControllerStatus;
  is_dirty?: boolean;
}

export type RtcModel = 'DS3231' | 'DS1307' | 'PCF8563' | 'PCF85063';

export interface ControllerUpdate {
  name?: string | undefined;
  rtc_model?: RtcModel | null;
  // Fréquence du bus I2C (kHz) : plus basse pour un câble long
  i2c_frequency_khz?: number;
  type?: ControllerType | undefined;
  zone?: string | undefined;
  ip?: string | undefined;
  status?: ControllerStatus | undefined;
}

export interface ControllerLog {
  id: number;
  timestamp: string;
  controller_id: number;
  level: string; // 'I', 'W', 'ERROR', etc.
  component: string;
  message: string;
}
