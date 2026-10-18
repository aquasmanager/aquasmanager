// Lignes d'articles d'une demande de commande groupée : saisie, contrôle et envoi
import type { GroupOrderItem } from 'src/types/groupOrder';

export interface EditableItem {
  key: number;
  name: string;
  url: string;
  quantity: number;
}

let itemKey = 0;

export function newItem(from?: GroupOrderItem): EditableItem {
  return { key: ++itemKey, name: from?.name ?? '', url: from?.url ?? '', quantity: from?.quantity ?? 1 };
}

export function urlValid(url: string): boolean {
  return !url.trim() || /^https?:\/\/\S+$/.test(url.trim());
}

/** Lignes nommées, prêtes à envoyer (lien vide → null, quantité bornée à 1..99). */
export function cleanItems(items: EditableItem[]): GroupOrderItem[] {
  return items
    .filter((i) => i.name.trim())
    .map((i) => ({
      name: i.name.trim(),
      url: i.url.trim() || null,
      quantity: Math.min(99, Math.max(1, Math.round(Number(i.quantity) || 1))),
    }));
}
