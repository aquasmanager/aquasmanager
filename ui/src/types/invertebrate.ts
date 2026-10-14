export interface InvertebratesList {
  total: number;
  invertebrates: Invertebrate[];
}

export interface Photo {
  id: number;
  filename: string;
}

export interface Invertebrate {
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
  actions: string;
}

export interface InvertebrateCreation {
  aquarium_id: number;
  name: string;
  date_acquisition: string;
  scientific_name: string;
  family: string;
  origin: string;
}

export interface InvertebrateUpdate {
  name: string | undefined;
  date_acquisition: string | undefined;
  scientific_name: string | undefined;
  family: string | undefined;
  origin: string | undefined;
}
