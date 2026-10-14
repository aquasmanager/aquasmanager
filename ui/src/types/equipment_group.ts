import type { EquipmentMode, EquipmentStatus } from './equipment';

export interface EquipmentInGroup {
  id: number;
  name: string;
  status: EquipmentStatus;
  mode: EquipmentMode;
}

export interface EquipmentGroup {
  id: number;
  name: string;
  equipments: EquipmentInGroup[];
}

export interface EquipmentGroupCreate {
  name: string;
  equipment_ids: number[];
}

export interface EquipmentGroupUpdate {
  name?: string;
  equipment_ids?: number[];
}
