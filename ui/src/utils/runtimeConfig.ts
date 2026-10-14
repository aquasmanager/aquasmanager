/**
 * Adresse de l'API et nom de l'environnement.
 *
 * Priorité à /config.js (window.__AQUAS_CONFIG__), écrit au démarrage du
 * conteneur à partir des variables AQUAS_API_URL / AQUAS_APP_ENV : une même
 * image sert ainsi n'importe quelle installation. À défaut, valeurs fixées à
 * la compilation (VITE_API_URL / VITE_APP_ENV), puis « /api » (API servie par
 * le même nginx, cas de l'installation Docker simple).
 */

interface AquasRuntimeConfig {
  apiUrl?: string;
  env?: string;
  hubUrl?: string;
}

declare global {
  interface Window {
    __AQUAS_CONFIG__?: AquasRuntimeConfig;
  }
}

const runtime: AquasRuntimeConfig = (typeof window !== 'undefined' && window.__AQUAS_CONFIG__) || {};

export const API_URL: string = (runtime.apiUrl || String(import.meta.env.VITE_API_URL ?? '') || '/api').replace(/\/+$/, '');

export const APP_ENV: string = runtime.env ?? String(import.meta.env.VITE_APP_ENV ?? '');

// Service central de l'éditeur (propositions au catalogue commun) ; « none » = désactivé
const HUB_DEFAULT = 'https://hub.aquasmanager.fr';
export const HUB_URL: string | null =
  runtime.hubUrl === 'none' ? null : (runtime.hubUrl || HUB_DEFAULT).replace(/\/+$/, '');

/** URL websocket de l'API (ws:// ou wss:// selon la page), aussi pour une adresse relative. */
export function websocketUrl(path = '/ws'): string {
  const url = new URL(`${API_URL}${path}`, window.location.href);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.toString();
}
