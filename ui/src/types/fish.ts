export interface FishesList {
  total: number;
  fishes: Fish[];
}

export interface Photo {
  id: number;
  filename: string;
}

export interface Fish {
  photo: Photo;
  id: number;
  aquarium_id: number;
  name: string;
  // Nombre d'individus / de colonies
  quantity: number;
  date_acquisition: string;
  scientific_name: string;
  family: string;
  origin: string;
  max_height: number;
  min_volume: number;
  reef_safe: boolean;
  actions: string;
}

export interface FishCreation {
  aquarium_id: number;
  name: string;
  date_acquisition: string;
  scientific_name: string;
  family: string;
  origin: string;
  max_height: number;
  min_volume: number;
  reef_safe: boolean;
}

export interface FishUpdate {
  name: string | undefined;
  date_acquisition: string | undefined;
  scientific_name: string | undefined;
  family: string | undefined;
  origin: string | undefined;
  max_height: number | undefined;
  min_volume: number | undefined;
  reef_safe: boolean | undefined;
}
