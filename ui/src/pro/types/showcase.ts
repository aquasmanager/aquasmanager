export interface ShowcaseSettings {
  enabled: boolean;
  title: string;
  intro: string;
  contact: string;
  show_prices: boolean;
  price_label: string;
  allow_reservations: boolean;
}

export interface ShowcaseLot {
  id: number;
  reference: string;
  name: string;
  scientific_name: string;
  coral_type: string | null;
  quantity: number;
  price: number | null;
}

export interface PublicShowcase extends Omit<ShowcaseSettings, 'enabled'> {
  // Lien de partage utilisé (null = lien permanent)
  link_label: string | null;
  ends_on: string | null;
  lots: ShowcaseLot[];
}

export type ShowcaseLinkState = 'active' | 'upcoming' | 'expired' | 'revoked';

export interface ShowcaseLink {
  id: number;
  token: string;
  label: string;
  location_id: number | null;
  location_name: string | null;
  starts_on: string | null;
  ends_on: string | null;
  qr_labels: boolean;
  revoked: boolean;
  view_count: number;
  last_viewed_at: string | null;
  created_at: string;
  state: ShowcaseLinkState;
}

export function showcaseLinkUrl(token: string): string {
  return `${window.location.origin}/vitrine/${token}`;
}

export interface Reservation {
  id: number;
  name: string;
  contact: string;
  message: string | null;
  items: { frag_id: number; quantity: number; reference: string; name: string }[];
  status: 'new' | 'confirmed' | 'declined';
  certificate_id: number | null;
  link_id: number | null;
  link_label: string | null;
  link_location_id: number | null;
  created_at: string;
}
