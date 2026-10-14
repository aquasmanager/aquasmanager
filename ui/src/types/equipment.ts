export enum PhysicalContact {
  NC = 'NC',
  NO = 'NO',
}

export enum EquipmentStatus {
  ON = 'ON',
  OFF = 'OFF',
}

export enum EquipmentMode {
  AUTO = 'AUTO',
  MANUAL = 'MANUAL',
}

export enum EquipmentCategory {
  OSMOLATOR = 'OSMOLATOR',
  OSMOSEUR = 'OSMOSEUR',
  PUMP = 'PUMP',
  BRASSAGE = 'BRASSAGE',
  ECUMOR = 'ECUMOR',
  COOLER = 'COOLER',
  HEATER = 'HEATER',
  LIGHT = 'LIGHT',
  OTHER = 'OTHER',
}

export interface EquipmentsList {
  total: number;
  equipments: Equipment[];
}

export interface PayloadTemplate {
  default: string | number;
}

export interface EquipmentToggle {
  id: number;
  new_status: EquipmentStatus;
}

export interface Equipment {
  id: number;
  aquarium_id: number;
  controller_id: number;
  pin_id: number;
  // Broche renvoyée par l'API pour l'affichage
  pin_number?: string | null;
  module_id?: number | null;
  module_number?: number | null;
  name: string;
  status: EquipmentStatus;
  mode: EquipmentMode;
  category?: EquipmentCategory;
  inverted?: boolean;
  physical_contact: PhysicalContact;
  restart_delay: number;
  max_duration_seconds?: number | null | undefined;
  at_created: string;
  actions: string;
}

export interface EquipmentCreation {
  aquarium_id: number;
  controller_id: number;
  pin_id: number;
  name: string;
  status: EquipmentStatus;
  category: EquipmentCategory;
  restart_delay: number;
  max_duration_seconds?: number | null | undefined;
}

export interface EquipmentUpdate {
  aquarium_id: number | undefined;
  controller_id: number | undefined;
  pin_id: number | undefined;
  name: string | undefined;
  status: EquipmentStatus | undefined;
  category: EquipmentCategory | undefined;
  restart_delay: number | undefined;
  max_duration_seconds?: number | null | undefined;
}
