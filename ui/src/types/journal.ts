// Journal de bord d'un aquarium : notes datées, aussi affichées sur les courbes des paramètres

export type JournalCategory = 'note' | 'livestock' | 'maintenance' | 'water_change' | 'dosing' | 'problem';

export interface JournalEntry {
  id: number;
  aquarium_id: number;
  occurred_at: string;
  category: JournalCategory;
  text: string;
  auto: boolean;
  created_at: string;
}

export const JOURNAL_CATEGORIES: { key: JournalCategory; icon: string; color: string }[] = [
  { key: 'note', icon: 'edit_note', color: '#64748b' },
  { key: 'water_change', icon: 'water_drop', color: '#0284c7' },
  { key: 'dosing', icon: 'science', color: '#7c3aed' },
  { key: 'livestock', icon: 'set_meal', color: '#16a34a' },
  { key: 'maintenance', icon: 'construction', color: '#d97706' },
  { key: 'problem', icon: 'report_problem', color: '#dc2626' },
];

export function journalCategory(key: string) {
  return JOURNAL_CATEGORIES.find((c) => c.key === key) ?? JOURNAL_CATEGORIES[0]!;
}
