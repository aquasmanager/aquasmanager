export type AssistantProvider = 'ollama' | 'openai';

export interface AssistantStatus {
  enabled: boolean;
  provider: AssistantProvider | null;
  model: string | null;
  // Questions et données envoyées à un service hors du réseau local
  external: boolean;
}

export interface AssistantSettings {
  enabled: boolean;
  provider: AssistantProvider;
  base_url: string;
  model: string;
  api_key_set: boolean;
  timeout_seconds: number;
  data_access: boolean;
}

export interface AssistantTestResult {
  ok: boolean;
  message: string;
  seconds: number | null;
}

// Adresses usuelles, pré-remplies d'un clic
// local : service sur le réseau de la maison (gratuit), sinon externe avec clé d'API
export const ASSISTANT_PRESETS: { label: string; provider: AssistantProvider; base_url: string; local: boolean }[] = [
  { label: 'Ollama', provider: 'ollama', base_url: 'http://localhost:11434', local: true },
  { label: 'LM Studio', provider: 'openai', base_url: 'http://localhost:1234/v1', local: true },
  { label: 'Mistral AI', provider: 'openai', base_url: 'https://api.mistral.ai/v1', local: false },
  { label: 'OpenAI', provider: 'openai', base_url: 'https://api.openai.com/v1', local: false },
  { label: 'OpenRouter', provider: 'openai', base_url: 'https://openrouter.ai/api/v1', local: false },
];

// Même règle que l'API : IP privée, nom sans point ou suffixe de réseau local = local
export function isExternalUrl(url: string): boolean {
  let host: string;
  try {
    host = new URL(url).hostname.replace(/^\[|\]$/g, '').toLowerCase();
  } catch {
    return false;
  }
  if (/^(127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host) || host === '::1' || /^f[cd]/.test(host)) return false;
  if (!host.includes('.')) return false;
  return !/\.(local|lan|home|internal|localdomain|cluster\.local)$/.test(host);
}
