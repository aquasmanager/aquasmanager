import type { CoralType } from './coral';
import type { PlantGrowing, PlantLocation } from './plant';

export type SpeciesWaterType = 'sea' | 'pure';

export interface FishSpecies {
  id: number;
  common_name: string;
  scientific_name: string;
  water_type: SpeciesWaterType;
  family?: string | null;
  origin?: string | null;
  max_height: number;
  min_volume: number;
  reef_safe: boolean;
  notes?: string | null;
  link?: string | null;
  builtin: boolean;
  // Fiche du catalogue commun modifiée ici : plus mise à jour par la synchronisation
  customized?: boolean;
  warnings: string[];
}

export type FishSpeciesInput = Omit<FishSpecies, 'id' | 'builtin' | 'warnings'>;

export interface CoralSpecies {
  id: number;
  common_name: string;
  scientific_name: string;
  type: CoralType;
  family?: string | null;
  origin?: string | null;
  light_min: number;
  light_max: number;
  brewing_min: number;
  brewing_max: number;
  aggressiveness_level: number;
  resistance_level: number;
  location_level: number;
  notes?: string | null;
  link?: string | null;
  builtin: boolean;
  // Fiche du catalogue commun modifiée ici : plus mise à jour par la synchronisation
  customized?: boolean;
  warnings: string[];
}

export type CoralSpeciesInput = Omit<CoralSpecies, 'id' | 'builtin' | 'warnings'>;

export interface PlantSpecies {
  id: number;
  common_name: string;
  scientific_name: string;
  family?: string | null;
  origin?: string | null;
  light_min: number;
  light_max: number;
  temperature_min: number;
  temperature_max: number;
  growing: PlantGrowing;
  resistance_level: number;
  max_height: number;
  location: PlantLocation;
  notes?: string | null;
  link?: string | null;
  builtin: boolean;
  // Fiche du catalogue commun modifiée ici : plus mise à jour par la synchronisation
  customized?: boolean;
  warnings: string[];
}

export type PlantSpeciesInput = Omit<PlantSpecies, 'id' | 'builtin' | 'warnings'>;

export type InvertebrateCategory = 'shrimp' | 'crab' | 'snail' | 'clam' | 'starfish' | 'urchin' | 'anemone' | 'other';

export interface InvertebrateSpecies {
  id: number;
  common_name: string;
  scientific_name: string;
  water_type: SpeciesWaterType;
  category: InvertebrateCategory;
  family?: string | null;
  origin?: string | null;
  min_volume: number;
  reef_safe: boolean;
  notes?: string | null;
  link?: string | null;
  builtin: boolean;
  // Fiche du catalogue commun modifiée ici : plus mise à jour par la synchronisation
  customized?: boolean;
  warnings: string[];
}

export type InvertebrateSpeciesInput = Omit<InvertebrateSpecies, 'id' | 'builtin' | 'warnings'>;

export interface SpeciesByKind {
  fishes: FishSpecies;
  corals: CoralSpecies;
  plants: PlantSpecies;
  invertebrates: InvertebrateSpecies;
}

export interface SpeciesInputByKind {
  fishes: FishSpeciesInput;
  corals: CoralSpeciesInput;
  plants: PlantSpeciesInput;
  invertebrates: InvertebrateSpeciesInput;
}

export type SpeciesKind = keyof SpeciesByKind;

// Libellés : livestock.categories.<valeur> (i18n)
export const INVERTEBRATE_CATEGORIES: InvertebrateCategory[] = ['shrimp', 'crab', 'snail', 'clam', 'starfish', 'urchin', 'anemone', 'other'];
