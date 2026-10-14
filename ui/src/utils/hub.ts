/**
 * Service central de l'éditeur (hub) : propositions d'espèces pour le
 * catalogue commun. Appels avec fetch et sans identifiants : le jeton de
 * connexion de l'installation (ajouté par axios) ne doit jamais partir vers
 * un service tiers.
 */
import { ref } from 'vue';
import { HUB_URL } from 'src/utils/runtimeConfig';

export type SpeciesKind = 'fishes' | 'corals' | 'plants' | 'invertebrates';

export interface HubStatus {
  suggestions: boolean;
  // Absents des hubs plus anciens : considérés comme fermés
  corrections?: boolean;
  features?: boolean;
  issues_form_url: string | null;
}

type HubValue = string | number | boolean | null;
export type SpeciesChanges = Record<string, { before: HubValue; after: HubValue }>;

export interface SpeciesProposal {
  common_name: string;
  scientific_name: string;
  [field: string]: string | number | boolean | null | undefined;
}

export class HubError extends Error {
  constructor(
    message: string,
    public readonly status: number | null,
  ) {
    super(message);
  }
}

// Statut partagé : lu une fois par session (le hub peut être hors ligne ou absent)
const status = ref<HubStatus | null>(null);
let pending: Promise<HubStatus | null> | null = null;

async function fetchStatus(): Promise<HubStatus | null> {
  if (!HUB_URL) return null;
  try {
    const response = await fetch(`${HUB_URL}/v1/status`, { credentials: 'omit', signal: AbortSignal.timeout(5000) });
    if (!response.ok) return null;
    return (await response.json()) as HubStatus;
  } catch {
    return null;
  }
}

export function useHubStatus() {
  if (!status.value && !pending) {
    pending = fetchStatus().then((value) => {
      status.value = value;
      pending = null;
      return value;
    });
  }
  return status;
}

interface Sent {
  number: number;
  url: string;
}

async function postToHub(path: string, payload: unknown): Promise<Sent> {
  if (!HUB_URL) throw new HubError('hub', null);
  let response: Response;
  try {
    response = await fetch(`${HUB_URL}${path}`, {
      method: 'POST',
      credentials: 'omit',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(20000),
    });
  } catch {
    throw new HubError('network', null);
  }
  if (!response.ok) {
    const detail = ((await response.json().catch(() => null)) as { detail?: unknown } | null)?.detail;
    throw new HubError(typeof detail === 'string' ? detail : 'error', response.status);
  }
  return (await response.json()) as Sent;
}

interface Common {
  author?: string | null;
  app_version?: string;
  locale?: string;
}

export function proposeSpecies(payload: Common & { kind: SpeciesKind; species: SpeciesProposal; note?: string | null }): Promise<Sent> {
  return postToHub('/v1/species-suggestions', payload);
}

export function proposeCorrection(
  payload: Common & { kind: SpeciesKind; common_name: string; scientific_name: string; changes: SpeciesChanges; note?: string | null },
): Promise<Sent> {
  return postToHub('/v1/species-corrections', payload);
}

export function proposeFeature(payload: Common & { title: string; description: string }): Promise<Sent> {
  return postToHub('/v1/feature-requests', payload);
}

/** Message d'erreur (clé i18n livestock.propose.errors.*) selon la réponse du hub. */
export function hubErrorKey(err: unknown): 'rate' | 'closed' | 'network' | 'failed' {
  const status = err instanceof HubError ? err.status : null;
  return status === 429 ? 'rate' : status === 503 ? 'closed' : status === null ? 'network' : 'failed';
}
