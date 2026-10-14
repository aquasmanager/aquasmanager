// Image et texte de partage des paramètres d'eau (forum, réseaux, messagerie).
// L'image est dessinée sur un canvas : aucune donnée n'est envoyée au serveur.
import { intlLocale } from 'src/i18n/instance';
import type { SharedParameter, SharedParameters } from 'src/types/parameterShare';

export interface CardLabels {
  title: string; // « Paramètres d'eau »
  optimal: string;
  outOfTarget: string;
  target: string; // « Cible »
  footer: string; // « Suivi avec AquasManager · aquasmanager.fr »
}

const WIDTH = 1080;
const PAD = 40;
const GAP = 24;
const TILE_W = (WIDTH - PAD * 2 - GAP) / 2;
const TILE_H = 250;
const HEADER_H = 190;
const FOOTER_H = 90;
const FONT = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

const COLORS = {
  bg: '#f1f5f9',
  tile: '#ffffff',
  header: '#0284c7',
  text: '#0f172a',
  muted: '#64748b',
  line: '#e2e8f0',
  ok: '#16a34a',
  warn: '#d97706',
  band: 'rgba(22, 163, 74, 0.12)',
  curve: '#0284c7',
};

export function formatValue(value: number | null | undefined): string {
  if (value == null) return '--';
  return value.toLocaleString(intlLocale(), { maximumFractionDigits: 3 });
}

export function formatTarget(p: SharedParameter): string | null {
  if (p.target_min == null && p.target_max == null) return null;
  const range =
    p.target_min != null && p.target_max != null
      ? `${formatValue(p.target_min)}–${formatValue(p.target_max)}`
      : p.target_min != null
        ? `≥ ${formatValue(p.target_min)}`
        : `≤ ${formatValue(p.target_max)}`;
  return p.unit ? `${range} ${p.unit}` : range;
}

function shortDate(value: string | null | undefined): string {
  if (!value) return '';
  return new Date(value).toLocaleDateString(intlLocale(), { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function fitText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let cut = text;
  while (cut.length > 1 && ctx.measureText(`${cut}…`).width > maxWidth) cut = cut.slice(0, -1);
  return `${cut}…`;
}

function drawSparkline(ctx: CanvasRenderingContext2D, p: SharedParameter, x: number, y: number, w: number, h: number) {
  const values = p.history.map((r) => r.value);
  const all = [...values, ...(p.target_min != null ? [p.target_min] : []), ...(p.target_max != null ? [p.target_max] : [])];
  let min = Math.min(...all);
  let max = Math.max(...all);
  if (max === min) {
    min -= 1;
    max += 1;
  }
  const margin = (max - min) * 0.1;
  min -= margin;
  max += margin;
  const yOf = (v: number) => y + h - ((v - min) / (max - min)) * h;
  if (p.target_min != null || p.target_max != null) {
    const top = yOf(p.target_max ?? max);
    const bottom = yOf(p.target_min ?? min);
    ctx.fillStyle = COLORS.band;
    roundRect(ctx, x, top, w, Math.max(bottom - top, 2), 6);
    ctx.fill();
  }
  if (values.length < 2) return;
  // Abscisse proportionnelle au temps (relevés irréguliers)
  const times = p.history.map((r) => new Date(r.timestamp).getTime());
  const t0 = times[0]!;
  const span = Math.max(times[times.length - 1]! - t0, 1);
  ctx.strokeStyle = COLORS.curve;
  ctx.lineWidth = 4;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.beginPath();
  values.forEach((v, i) => {
    const px = x + ((times[i]! - t0) / span) * w;
    if (i === 0) ctx.moveTo(px, yOf(v));
    else ctx.lineTo(px, yOf(v));
  });
  ctx.stroke();
  const last = values[values.length - 1]!;
  ctx.fillStyle = COLORS.curve;
  ctx.beginPath();
  ctx.arc(x + w, yOf(last), 6, 0, Math.PI * 2);
  ctx.fill();
}

function drawTile(ctx: CanvasRenderingContext2D, p: SharedParameter, x: number, y: number, labels: CardLabels) {
  ctx.fillStyle = COLORS.tile;
  roundRect(ctx, x, y, TILE_W, TILE_H, 20);
  ctx.fill();
  ctx.strokeStyle = COLORS.line;
  ctx.lineWidth = 2;
  ctx.stroke();

  const inner = TILE_W - 56;
  ctx.textBaseline = 'alphabetic';
  // Nom et statut
  ctx.fillStyle = COLORS.text;
  ctx.font = `700 32px ${FONT}`;
  ctx.fillText(fitText(ctx, p.name, inner - 170), x + 28, y + 52);
  if (p.in_target != null) {
    const label = p.in_target ? labels.optimal : labels.outOfTarget;
    ctx.font = `700 22px ${FONT}`;
    const pillW = ctx.measureText(label).width + 28;
    ctx.fillStyle = p.in_target ? COLORS.ok : COLORS.warn;
    roundRect(ctx, x + TILE_W - 28 - pillW, y + 24, pillW, 38, 19);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.fillText(label, x + TILE_W - 28 - pillW + 14, y + 51);
  }
  // Valeur
  ctx.fillStyle = COLORS.text;
  ctx.font = `800 60px ${FONT}`;
  const value = formatValue(p.last_value);
  ctx.fillText(value, x + 28, y + 122);
  if (p.unit) {
    const vw = ctx.measureText(value).width;
    ctx.fillStyle = COLORS.muted;
    ctx.font = `500 26px ${FONT}`;
    ctx.fillText(fitText(ctx, p.unit, inner - vw - 12), x + 28 + vw + 12, y + 122);
  }
  // Courbe et plage cible
  drawSparkline(ctx, p, x + 28, y + 142, inner, 50);
  // Cible et date
  ctx.font = `500 22px ${FONT}`;
  ctx.fillStyle = COLORS.muted;
  const target = formatTarget(p);
  const date = shortDate(p.last_reading_at);
  if (target) ctx.fillText(fitText(ctx, `${labels.target} ${target}`, inner - 140), x + 28, y + TILE_H - 22);
  ctx.textAlign = 'right';
  ctx.fillText(date, x + TILE_W - 28, y + TILE_H - 22);
  ctx.textAlign = 'left';
}

/** Image PNG (1080 px de large) : en-tête, une tuile par paramètre, pied de page. */
export async function drawParameterCard(data: SharedParameters, labels: CardLabels): Promise<Blob> {
  const rows = Math.max(Math.ceil(data.parameters.length / 2), 1);
  const height = HEADER_H + PAD + rows * TILE_H + (rows - 1) * GAP + PAD + FOOTER_H;
  const canvas = document.createElement('canvas');
  canvas.width = WIDTH;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('canvas');
  // Polices de l'appli chargées avant de dessiner
  await document.fonts?.ready;

  ctx.fillStyle = COLORS.bg;
  ctx.fillRect(0, 0, WIDTH, height);
  ctx.fillStyle = COLORS.header;
  ctx.fillRect(0, 0, WIDTH, HEADER_H);
  ctx.fillStyle = '#ffffff';
  ctx.font = `800 56px ${FONT}`;
  ctx.fillText(fitText(ctx, data.aquarium.name, WIDTH - PAD * 2), PAD, 92);
  ctx.font = `500 28px ${FONT}`;
  ctx.globalAlpha = 0.9;
  const subtitle = [labels.title, `${data.aquarium.volume} L`, shortDate(data.generated_at)].join(' · ');
  ctx.fillText(fitText(ctx, subtitle, WIDTH - PAD * 2), PAD, 142);
  ctx.globalAlpha = 1;

  data.parameters.forEach((p, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    drawTile(ctx, p, PAD + col * (TILE_W + GAP), HEADER_H + PAD + row * (TILE_H + GAP), labels);
  });

  ctx.fillStyle = COLORS.muted;
  ctx.font = `500 24px ${FONT}`;
  ctx.textAlign = 'center';
  ctx.fillText(labels.footer, WIDTH / 2, height - FOOTER_H / 2 + 8);

  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('toBlob'))), 'image/png'),
  );
}

export interface TextLabels {
  title: string; // « {aquarium} : paramètres d'eau du {date} »
  outOfTarget: string;
  target: string;
  footer: string;
}

// Espace avant les deux-points en français
const COLON_FR = ' : ';

/** Texte à coller dans un forum ou une messagerie. */
export function parametersText(data: SharedParameters, labels: TextLabels): string {
  const COLON = intlLocale().startsWith('fr') ? COLON_FR : ': ';
  const lines = [labels.title];
  for (const p of data.parameters) {
    const value = `${formatValue(p.last_value)}${p.unit ? ` ${p.unit}` : ''}`;
    const status = p.in_target === true ? ' ✅' : p.in_target === false ? ` ⚠️ ${labels.outOfTarget}` : '';
    const target = formatTarget(p);
    // Date du relevé seulement si elle diffère de celle du titre
    const day = shortDate(p.last_reading_at);
    const date = day && day !== shortDate(data.generated_at) ? ` · ${day}` : '';
    lines.push(`• ${p.name}${COLON}${value}${status}${target ? ` (${labels.target} ${target})` : ''}${date}`);
  }
  lines.push('', labels.footer);
  return lines.join('\n');
}
