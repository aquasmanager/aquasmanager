export enum WaterType {
  sea = 'sea',
  pure = 'pure',
}

export interface AquariumsList {
  total: number;
  aquariums: Aquarium[];
}

export interface Aquarium {
  id: number;
  name: string;
  volume: number;
  water_type: WaterType;
  biotope: string;
  date_creation: string;
  // Fin prévue du mode maintenance en cours
  maintenance_until?: string | null;
}

export interface AquariumCreation {
  name: string;
  volume: number;
  water_type: WaterType;
  biotope: string;
  date_creation: string;
}

export interface AquariumUpdate {
  name: string | undefined;
  volume: number | undefined;
  water_type: WaterType | undefined;
  biotope: string | undefined;
  date_creation: string | undefined;
}
