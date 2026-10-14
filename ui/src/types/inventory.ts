import type { SharedScope } from 'src/utils/sharedScope';

export interface InventoryMovement {
  id: number;
  item_id: number;
  delta: number;
  note?: string | null;
  created_at: string;
}

export interface InventoryItem {
  id: number;
  aquarium_id: number;
  name: string;
  unit: string;
  quantity: number;
  low_stock_threshold?: number | null;
  // Date d'ouverture du conditionnement en cours (AAAA-MM-JJ)
  opened_on?: string | null;
  scope: SharedScope;
  aquarium_ids: number[];
}

export interface InventoryItemCreate {
  aquarium_id: number;
  name: string;
  unit: string;
  quantity: number;
  low_stock_threshold?: number | null;
  opened_on?: string | null;
  scope?: SharedScope;
  aquarium_ids?: number[];
}

export type InventoryItemUpdate = Partial<Omit<InventoryItemCreate, 'aquarium_id' | 'quantity'>>;

export interface InventoryMovementCreate {
  delta: number;
  note?: string | null;
}
