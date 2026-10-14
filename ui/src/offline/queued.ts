import type { AxiosResponse } from 'axios';

/** Réponse fabriquée quand l'écriture a été mise en file d'attente (hors connexion). */
export function isQueued(response: AxiosResponse): boolean {
  return response.status === 202 && response.statusText === 'queued';
}

export function newKey(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
