export enum PhotoEntityType {
  aquariums = 'aquariums',
  corals = 'corals',
  fishes = 'fishes',
  plants = 'plants',
  invertebrates = 'invertebrates',
  frags = 'frags',
}

export interface PhotoInfo {
  id: number;
  entity_type: PhotoEntityType;
  entity_id: number;
  filename: string;
  is_main: boolean;
  created_at: string;
}
