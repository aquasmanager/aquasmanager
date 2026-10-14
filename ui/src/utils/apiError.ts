import type { AxiosError } from 'axios';

/** Message lisible d'une erreur d'API (detail FastAPI), sinon le message par défaut. */
export function apiErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as AxiosError<{ detail?: unknown }>)?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: unknown } | undefined;
    if (typeof first?.msg === 'string') return first.msg.replace(/^Value error, /, '');
  }
  return fallback;
}
