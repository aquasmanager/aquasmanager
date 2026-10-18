// Commandes groupées (VPC) entre passionnés d'un même secteur, via le hub de l'éditeur

export type GroupOrderStatus = 'open' | 'closed' | 'cancelled';
export type GroupOrderRole = 'owner' | 'participant' | null;

// Une ligne de demande : corail / produit, lien direct chez le magasin, quantité
export interface GroupOrderItem {
  name: string;
  url?: string | null;
  quantity: number;
}

export interface GroupOrderMember {
  id: string;
  name: string;
  contact: string;
  message?: string | null;
  items?: GroupOrderItem[];
  created_at?: string;
}

export interface GroupOrder {
  id: string;
  title: string;
  shop: string;
  shop_url?: string | null;
  department: string;
  area: string;
  deadline: string;
  organizer: string;
  description?: string | null;
  status: GroupOrderStatus;
  participants: number;
  created_at?: string;
  // Détail : contact de l'organisateur (participants), participants (organisateur)
  contact?: string | null;
  members?: GroupOrderMember[];
  role?: GroupOrderRole;
  my_role: GroupOrderRole;
}

export interface GroupOrderInput {
  title: string;
  shop: string;
  shop_url: string | null;
  department: string;
  area: string;
  deadline: string;
  organizer: string;
  contact: string;
  description: string | null;
}

export interface GroupOrderSettings {
  departments: string[];
  notify: boolean;
}
