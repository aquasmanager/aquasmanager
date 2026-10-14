export enum ControllerPinMode {
  IN = 'IN',
  OUT = 'OUT',
  SENSOR = 'SENSOR',
  FREE = 'FREE',
}

export enum ControllerPinBus {
  GPIO = 'ONLINE',
  PWM = 'OFFLINE',
  I2C = 'I2C',
  SPI = 'SPI',
  ONEWIRE = 'ONWIRE',
  ADC = 'ADC',
  UART = 'UART',
  FREE = 'FREE',
}

export interface ControllersPinsList {
  total: number;
  controllers_pins: ControllerPin[];
}

export interface ControllerPin {
  id: number;
  controller_id: number;
  module_id: number;
  // Numéro affiché du module d'extension sur son contrôleur (« Module 1 »)
  module_number?: number | null;
  module_type?: string | null;
  pin_number: string;
  bus: ControllerPinBus;
  mode: ControllerPinMode;
  label: string;
  actions: string;
  // Avec include_used : broche libre ou non, et ce qui l'occupe (« Écumeur · Récif »)
  free?: boolean;
  // Bus 1-Wire déjà utilisé par des sondes : encore possible pour une sonde de température
  one_wire?: boolean;
  used_by?: string | null;
}

export interface ControllerPinCreation {
  controller_id: number;
  pin_number: string;
  bus: ControllerPinBus;
  mode: ControllerPinMode;
  label: string;
}

export interface ControllerPinUpdate {
  controller_id: number | undefined;
  pin_number: string | undefined;
  bus: ControllerPinBus | undefined;
  mode: ControllerPinMode | undefined;
  label: string | undefined;
}

export interface OneWireScan {
  // Configuration renvoyée par le contrôleur ; bus 1-Wire du firmware et nombre de sondes qui répondent
  config_received: boolean;
  buses: { pin_number: number | null; devices: number }[];
  devices: OneWireDevice[];
}

export interface OneWireDevice {
  address: string;
  model: string;
  pin_number: number | null;
  sensor_id: number | null;
  sensor_name: string | null;
  // Capteur qui utilise déjà cette sonde : son aquarium et sa dernière mesure
  aquarium_name?: string | null;
  last_value?: number | string | null;
}
