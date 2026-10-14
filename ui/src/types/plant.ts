export enum PlantGrowing {
  slow = 'slow',
  average = 'average',
  fast = 'fast',
}

export enum PlantLocation {
  front = 'front',
  middle = 'middle',
  back = 'back',
}

export interface Range {
  min: number;
  max: number;
}

export interface Photo {
  id: number;
  filename: string;
}

export interface PlantsList {
  total: number;
  plants: Plant[];
}

export interface Plant {
  photo: Photo;
  id: number;
  aquarium_id: number;
  name: string;
  // Nombre d'individus / de colonies
  quantity: number;
  scientific_name: string;
  family: string;
  origin: string;
  light_range: Range;
  temperature_range: Range;
  growing: PlantGrowing;
  resistance_level: number;
  max_height: number;
  location: PlantLocation;
  date_acquisition: string;
  actions: string;
}

export interface PlantCreation {
  aquarium_id: number;
  name: string;
  scientific_name: string;
  family: string;
  origin: string;
  light_range: Range;
  temperature_range: Range;
  growing: PlantGrowing;
  resistance_level: number;
  max_height: number;
  location: PlantLocation;
  date_acquisition: string;
}

export interface PlantUpdate {
  aquarium_id: number | undefined;
  name: string | undefined;
  scientific_name: string | undefined;
  family: string | undefined;
  origin: string | undefined;
  light_range: Range | undefined;
  temperature_range: Range | undefined;
  growing: PlantGrowing | undefined;
  resistance_level: number | undefined;
  max_height: number | undefined;
  location: PlantLocation | undefined;
  date_acquisition: string | undefined;
}
