import { t } from 'src/i18n/instance';

export type SpecimenType = 'corals' | 'invertebrates' | 'fish';

export function specimenLabel(type: SpecimenType): string {
  return t(`documents.specimens.${type}`);
}

export interface DocumentFile {
  id: number;
  original_name: string;
  content_type: string;
  size: number;
  created_at: string;
}

export interface DocumentLink {
  entity_type: SpecimenType;
  entity_id: number;
  // null : spécimen supprimé depuis
  label: string | null;
  aquarium_id: number | null;
}

export interface PurchaseDocument {
  id: number;
  title: string;
  supplier: string;
  purchase_date: string | null;
  reference: string;
  cites_number: string;
  // Un ou plusieurs numéros CITES (cites_number : les mêmes, un par ligne)
  cites_numbers: string[];
  // Numéros avec l'espèce de corail associée (proposée à l'ajout d'un corail)
  cites_entries?: { number: string; coral_species_id: number | null; coral_species_name: string | null }[];
  notes: string | null;
  created_at: string;
  files: DocumentFile[];
  links: DocumentLink[];
  // Coraux liés automatiquement par leur numéro CITES lors de l'enregistrement
  auto_linked?: number;
}

export interface LinkableSpecimen {
  entity_type: SpecimenType;
  entity_id: number;
  name: string;
  scientific_name: string;
  cites: string;
  aquarium_id: number;
  aquarium_name: string;
}

export const DOCUMENT_ACCEPT = '.pdf,.jpg,.jpeg,.png,.webp,.heic,.heif,application/pdf,image/*';

export function specimenKey(type: SpecimenType, id: number): string {
  return `${type}:${id}`;
}

export interface CitesSuggestion {
  number: string;
  document_id: number;
  document_title: string;
  supplier: string;
  purchase_date: string | null;
  used_by: string[];
}
