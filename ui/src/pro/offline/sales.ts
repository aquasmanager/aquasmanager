/**
 * Ventes préparées sans réseau (bourse) : gardées dans IndexedDB jusqu'à leur
 * envoi. Une fois signée, la vente part dans la file d'attente (même
 * identifiant = clé d'idempotence) vers POST /transfer-certificates/offline.
 */
import type { CertificateItem, Person } from 'src/types/frag';
import { idb } from 'src/offline/idb';

export interface OfflineSalePayload {
  items: { frag_id: number; quantity: number; price: number | null }[];
  transfer_date: string | null;
  notes: string | null;
  location_id?: number;
  location_name?: string;
}

export interface OfflineSaleRecord {
  id: string;
  created_at: string;
  status: 'awaiting_signature' | 'signed';
  payload: OfflineSalePayload;
  location_label: string | null;
  seller: Person;
  legal_mention: string;
  // Mention d'information RGPD (profil en cache ; absente sur les ventes plus anciennes)
  privacy_notice?: string;
  items: CertificateItem[];
  buyer?: Person;
  signed_at?: string;
}

export const offlineSales = {
  all: async () => (await idb.all<OfflineSaleRecord>('sales')).sort((a, b) => b.created_at.localeCompare(a.created_at)),
  get: (id: string) => idb.get<OfflineSaleRecord>('sales', id),
  save: (sale: OfflineSaleRecord) => idb.put('sales', JSON.parse(JSON.stringify(sale)) as OfflineSaleRecord),
  remove: (id: string) => idb.delete('sales', id),
};

/** Quantités retirées des lots par les ventes pas encore envoyées */
export async function unsyncedSaleQuantities(): Promise<Map<number, number>> {
  const totals = new Map<number, number>();
  try {
    for (const sale of await offlineSales.all()) {
      for (const item of sale.payload.items) totals.set(item.frag_id, (totals.get(item.frag_id) ?? 0) + item.quantity);
    }
  } catch {
    // IndexedDB indisponible : rien à retirer
  }
  return totals;
}
