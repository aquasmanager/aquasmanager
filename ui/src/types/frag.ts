export type FragStatus = 'available' | 'reserved' | 'transferred' | 'empty';

export interface Frag {
  id: number;
  reference: string;
  aquarium_id: number | null;
  mother_coral_id: number | null;
  mother_name: string | null;
  name: string;
  scientific_name: string;
  coral_type: 'SPS' | 'LPS' | 'MOU' | null;
  cites: string;
  origin: string;
  // Provenance du pied mère (acquis auprès de : magasin, bourse, particulier)
  acquired_from?: string | null;
  cut_date: string;
  /** Nombre encore disponible dans le lot */
  quantity: number;
  reserved_quantity: number;
  transferred_quantity: number;
  /** Prix unitaire */
  price: number | null;
  notes: string | null;
  status: FragStatus;
  showcase_hidden: boolean;
  certificate_id: number | null;
  certificate_number: string | null;
  created_at: string;
}

export interface FragCreate {
  mother_coral_id?: number | null;
  aquarium_id?: number | null;
  name?: string | null;
  scientific_name?: string | null;
  coral_type?: 'SPS' | 'LPS' | 'MOU' | null;
  cites?: string | null;
  origin?: string | null;
  acquired_from?: string | null;
  cut_date?: string | null;
  price?: number | null;
  notes?: string | null;
  quantity?: number;
}

export type FragUpdate = Omit<FragCreate, 'mother_coral_id'> & { showcase_hidden?: boolean };

// Libellés : frags.status.*
export const FRAG_STATUS: Record<FragStatus, { color: string; icon: string }> = {
  available: { color: 'positive', icon: 'check_circle' },
  reserved: { color: 'orange-8', icon: 'schedule' },
  transferred: { color: 'blue-grey-6', icon: 'handshake' },
  empty: { color: 'grey-6', icon: 'block' },
};

export type MovementReason = 'created' | 'added' | 'lost' | 'gift' | 'correction' | 'reserved' | 'released' | 'moved';
export type ManualReason = 'added' | 'lost' | 'gift' | 'correction';

// Libellés : frags.reasons.*
export const MOVEMENT_REASONS: Record<MovementReason, { color: string; icon: string }> = {
  created: { color: 'primary', icon: 'content_cut' },
  added: { color: 'positive', icon: 'add_circle' },
  lost: { color: 'negative', icon: 'heart_broken' },
  gift: { color: 'purple-6', icon: 'volunteer_activism' },
  correction: { color: 'grey-7', icon: 'edit' },
  reserved: { color: 'orange-8', icon: 'description' },
  released: { color: 'blue-grey-6', icon: 'undo' },
  moved: { color: 'teal-6', icon: 'move_down' },
};

export interface FragMovement {
  id: number;
  delta: number;
  reason: MovementReason;
  note: string | null;
  certificate_number: string | null;
  created_at: string;
}

export interface FragStatRow {
  key: string;
  name: string;
  scientific_name: string;
  lots: number;
  produced: number;
  transferred: number;
  reserved: number;
  lost: number;
  gift: number;
  available: number;
  survival_rate: number | null;
}

export interface Person {
  first_name: string;
  last_name: string;
  address: string;
  postal_code: string;
  city: string;
  email?: string | null;
  phone?: string | null;
}

export interface SellerProfile extends Person {
  legal_mention: string;
  // RGPD : texte saisi (vide = texte par défaut), texte réellement affiché, durée en années (0 = jamais)
  privacy_notice: string;
  effective_privacy_notice: string;
  buyer_retention_years: number;
  signature: string | null;
  complete: boolean;
}

export interface CertificateItem {
  id: number;
  frag_id: number | null;
  reference: string;
  name: string;
  scientific_name: string;
  cites: string;
  origin: string;
  // Provenance du pied mère (acquis auprès de : magasin, bourse, particulier)
  acquired_from?: string | null;
  // Provenance du pied mère (acquis auprès de), figée à la cession
  mother_acquired_from?: string | null;
  mother_name: string | null;
  cut_date: string | null;
  quantity: number;
  price: number | null;
}

export interface SaleLocation {
  id: number;
  name: string;
  certificate_count: number;
  total_quantity: number;
  total_price: number | null;
  last_transfer_date: string | null;
}

export interface CertificateReport {
  certificate_count: number;
  pending_count: number;
  quantity: number;
  total: number;
  by_species: { name: string; scientific_name: string; quantity: number; amount: number }[];
  stock_lots: number;
  stock_quantity: number;
}

/** Cessions signées d'une année civile (repère d'activité occasionnelle) */
export interface YearlyTransfers {
  year: number;
  certificate_count: number;
  quantity: number;
  total: number;
  location_count: number;
  buyer_count: number;
}

/** Lieu choisi : id d'un lieu existant, ou nom d'un nouveau lieu à créer */
export type LocationChoice = number | string | null;

export function locationPayload(choice: LocationChoice): { location_id?: number; location_name?: string } {
  if (typeof choice === 'number') return { location_id: choice };
  if (typeof choice === 'string' && choice.trim()) return { location_name: choice.trim() };
  return {};
}

export interface CertificateSummary {
  id: number;
  number: string;
  status: 'draft' | 'signed';
  transfer_date: string;
  buyer_name: string | null;
  total_price: number | null;
  item_count: number;
  total_quantity: number;
  location_id: number | null;
  location_name: string | null;
  created_at: string;
  signed_at: string | null;
  token_expires_at: string;
  anonymized_at: string | null;
}

export interface Certificate extends CertificateSummary {
  notes: string | null;
  seller: Person;
  legal_mention: string;
  privacy_notice: string;
  buyer: Person | null;
  items: CertificateItem[];
  sign_token: string;
}

export interface PublicCertificate {
  number: string;
  status: 'draft' | 'signed';
  transfer_date: string;
  location_name: string | null;
  notes: string | null;
  seller: Person;
  legal_mention: string;
  privacy_notice: string;
  buyer: Person | null;
  items: CertificateItem[];
  total_price: number | null;
  total_quantity: number;
  signed_at: string | null;
}
