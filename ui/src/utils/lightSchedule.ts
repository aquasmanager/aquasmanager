import type { LightChannel, SchedulePoint } from 'src/types/light';

export const DAY_MINUTES = 1440;

// Même calcul que le firmware (services/light_firmware.py) : interpolation
// linéaire entre les points, le dernier rejoignant le premier du lendemain.
export function interpolate(points: SchedulePoint[], minute: number): number {
  const sorted = [...points].sort((a, b) => a.minute - b.minute);
  const n = sorted.length;
  if (n === 0) return 0;
  if (n === 1) return sorted[0]!.intensity;
  for (let i = 0; i < n; i++) {
    const a = sorted[i]!;
    const b = sorted[(i + 1) % n]!;
    const m0 = a.minute;
    let m1 = b.minute;
    let m = minute;
    if (i === n - 1) {
      m1 += DAY_MINUTES;
      if (m < m0) m += DAY_MINUTES;
    }
    if (m >= m0 && m <= m1) {
      return m1 === m0 ? b.intensity : a.intensity + ((b.intensity - a.intensity) * (m - m0)) / (m1 - m0);
    }
  }
  return sorted[0]!.intensity;
}

export function channelTargetLevel(channel: LightChannel, minute: number): number {
  let value: number;
  if (channel.mode === 'OFF') value = 0;
  else if (channel.mode === 'MANUAL') value = channel.current_intensity;
  else {
    value = interpolate(channel.schedule, minute);
    if (value < channel.moonlight_intensity) value = channel.moonlight_intensity;
  }
  return withThreshold(Math.max(0, Math.min(value, channel.max_intensity)), channel);
}

/**
 * Intensité réellement produite par le programme (mode auto) à cette minute, comme le
 * firmware : clair de lune en plancher, plafond, puis seuil d'allumage.
 */
export function programLevel(channel: LightChannel, minute: number): number {
  let value = channel.schedule.length ? interpolate(channel.schedule, minute) : 0;
  if (value < channel.moonlight_intensity) value = channel.moonlight_intensity;
  return withThreshold(Math.max(0, Math.min(value, channel.max_intensity)), channel);
}

/** Sous le seuil d'allumage, le canal est éteint (même règle que le firmware). */
export function withThreshold(value: number, channel: Pick<LightChannel, 'min_intensity'>): number {
  return value < (channel.min_intensity ?? 0) ? 0 : value;
}

export function formatMinute(minute: number): string {
  const m = ((Math.round(minute) % DAY_MINUTES) + DAY_MINUTES) % DAY_MINUTES;
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}

export function parseTime(value: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
  if (!match) return null;
  const h = Number(match[1]);
  const m = Number(match[2]);
  return h < 24 && m < 60 ? h * 60 + m : null;
}

/**
 * Minute de la journée maintenant, dans le fuseau des contrôleurs (celui du firmware) :
 * un appareil réglé sur un autre fuseau (UTC d'un bureau distant...) afficherait sinon
 * le repère « maintenant » décalé par rapport à ce que fait la rampe.
 */
export function nowMinute(timeZone?: string): number {
  const d = new Date();
  if (timeZone) {
    try {
      const parts = new Intl.DateTimeFormat('en-GB', {
        timeZone,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hourCycle: 'h23',
      }).formatToParts(d);
      const part = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
      return part('hour') * 60 + part('minute') + part('second') / 60;
    } catch {
      // Fuseau inconnu du navigateur : heure de l'appareil
    }
  }
  return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60;
}

function hexToRgb(hex: string): [number, number, number] {
  const v = parseInt(hex.replace('#', ''), 16);
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}

// Aperçu de la teinte : somme des couleurs des canaux pondérées par leur intensité
export function mixedColor(channels: LightChannel[], levels: Record<number, number>): { color: string; brightness: number } {
  let r = 0;
  let g = 0;
  let b = 0;
  let total = 0;
  for (const ch of channels) {
    const level = (levels[ch.id] ?? 0) / 100;
    const [cr, cg, cb] = hexToRgb(ch.color);
    r += cr * level;
    g += cg * level;
    b += cb * level;
    total += level;
  }
  if (total === 0) return { color: '#0b1020', brightness: 0 };
  const peak = Math.max(r, g, b, 1);
  const scale = 255 / peak;
  const hex = (x: number) => Math.round(x * scale).toString(16).padStart(2, '0');
  return { color: `#${hex(r)}${hex(g)}${hex(b)}`, brightness: Math.min(1, total / Math.max(1, channels.length / 2)) };
}

function luminance(hex: string): number {
  const match = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!match) return 0.5;
  const value = parseInt(match[1]!, 16);
  const [r, g, b] = [(value >> 16) & 255, (value >> 8) & 255, value & 255];
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
}

/** Couleur trop claire pour un fond blanc (canal « blanc ») : un contour est nécessaire. */
export function isVeryLight(hex: string): boolean {
  return luminance(hex) > 0.8;
}

/**
 * Couleur lisible pour les courbes et jauges : le blanc (ou un jaune très pâle)
 * devient un gris bleuté en thème clair ; en thème sombre il reste tel quel.
 */
export function visibleColor(hex: string, dark: boolean): string {
  if (!dark && isVeryLight(hex)) return '#8a97a6';
  if (dark && luminance(hex) < 0.12) return '#7c8cff';
  return hex;
}
