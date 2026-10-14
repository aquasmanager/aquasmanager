export enum CoralType {
  LPS = 'LPS',
  SPS = 'SPS',
  MOU = 'MOU',
}

export interface Range {
  min: number;
  max: number;
}

export interface CoralsList {
  total: number;
  corals: Coral[];
}

export interface Photo {
  id: number;
  filename: string;
}

export interface Coral {
  photo: Photo;
  id: number;
  aquarium_id: number;
  name: string;
  // Nombre d'individus / de colonies
  quantity: number;
  cites: string;
  type: CoralType;
  scientific_name: string;
  family: string;
  origin: string;
  // Provenance : acquis auprès de (magasin, bourse, particulier)
  acquired_from?: string | null | undefined;
  light_range: Range;
  brewing_range: Range;
  aggressiveness_level: number;
  resistance_level: number;
  location_level: number;
  date_acquisition: string;
  actions: string;
}

export interface CoralCreation {
  aquarium_id: number;
  name: string;
  cites: string;
  type: CoralType;
  scientific_name: string;
  family: string;
  origin: string;
  // Provenance : acquis auprès de (magasin, bourse, particulier)
  acquired_from?: string | null | undefined;
  light_range: Range;
  brewing_range: Range;
  aggressiveness_level: number;
  resistance_level: number;
  location_level: number;
  date_acquisition: string;
}

export interface CoralUpdate {
  name: string | undefined;
  cites: string | undefined;
  type: CoralType | undefined;
  scientific_name: string | undefined;
  family: string | undefined;
  origin: string | undefined;
  acquired_from?: string | null | undefined;
  light_range: Range | undefined;
  brewing_range: Range | undefined;
  aggressiveness_level: number | undefined;
  resistance_level: number | undefined;
  location_level: number | undefined;
  date_acquisition: string | undefined;
}
