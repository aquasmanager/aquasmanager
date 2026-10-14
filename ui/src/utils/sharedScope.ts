import { t } from 'src/i18n/instance';

// Portée d'une tâche ou d'un article de stock : un aquarium, plusieurs ou tous
export type SharedScope = 'single' | 'multiple' | 'all';

export interface ScopedEntity {
  scope: SharedScope;
  aquarium_ids: number[];
}

export interface ScopeValue {
  scope: SharedScope;
  aquarium_ids: number[];
}

export function scopeFrom(entity: ScopedEntity | null | undefined, currentAquariumId: number): ScopeValue {
  if (!entity || entity.scope === 'single') return { scope: 'single', aquarium_ids: [currentAquariumId] };
  return { scope: entity.scope, aquarium_ids: [...entity.aquarium_ids] };
}

// Payload API : « Cet aquarium » est envoyé comme sélection d'un seul bac
export function scopePayload(value: ScopeValue, currentAquariumId: number): ScopeValue {
  if (value.scope === 'single') return { scope: 'single', aquarium_ids: [currentAquariumId] };
  if (value.scope === 'all') return { scope: 'all', aquarium_ids: [] };
  return { scope: 'multiple', aquarium_ids: value.aquarium_ids };
}

export function scopeLabel(entity: ScopedEntity, names: (id: number) => string | undefined): string | null {
  if (entity.scope === 'all') return t('scope.allAquariums');
  if (entity.scope === 'multiple') return entity.aquarium_ids.map((id) => names(id) ?? '?').join(', ');
  return null;
}
